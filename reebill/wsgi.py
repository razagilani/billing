from cherrypy.lib import auth_basic

import cherrypy
import ConfigParser
import os
import logging
import pymongo
import mongoengine

from nexusapi.nexus_util import NexusUtil
from billing.processing.users import UserDAO
from skyliner.splinter import Splinter
from skyliner import mock_skyliner
from billing.util import json_util as ju
from billing.util.dateutils import ISO_8601_DATE, ISO_8601_DATETIME_WITHOUT_ZONE
from nexusapi.nexus_util import NexusUtil
from billing.util.dictutils import deep_map, dict_merge
from billing.processing import mongo, excel_export
from billing.processing.bill_mailer import Mailer
from billing.processing import process, state, fetch_bill_data as fbd,\
        rate_structure2 as rs
from billing.processing.state import UtilBill
from billing.processing.billupload import BillUpload
from billing.processing import journal
from billing.processing import render
from billing.processing.users import UserDAO
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import Unauthenticated, IssuedBillError

class RESTResource(object):
   """
   Base class for providing a RESTful interface to a resource.

   To use this class, simply derive a class from it and implement the methods
   you want to support.  The list of possible methods are:
   handle_GET
   handle_PUT
   handle_POST
   handle_DELETE
   """
   @cherrypy.expose
   def default(self, *vpath, **params):
      method = getattr(self, "handle_" + cherrypy.request.method, None)
      if not method:
         methods = [x.replace("handle_", "")
            for x in dir(self) if x.startswith("handle_")]
         cherrypy.response.headers["Allow"] = ",".join(methods)
         raise cherrypy.HTTPError(405, "Method not implemented.")
      return method(*vpath, **params);

class Accounts(RESTResource):
    def handle_GET(self, *vpath, **params):
        retval = "Path Elements:<br/>" + '<br/>'.join(vpath)
        query = ['%s=>%s' % (k,v) for k,v in params.items()]
        retval += "<br/>Query String Elements:<br/>" + \
            '<br/>'.join(query)
        return retval

class BillToolBridge(object):
    accounts = Accounts()

    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'reebill.cfg')
        if not self.config.read(config_file_path):
            # TODO: 64958246
            # can't log this because logger hasn't been created yet (log file
            # name & associated info comes from config file)
            print >> sys.stderr, 'Config file "%s" not found'%config_file_path
            sys.exit(1)

        self.config.read(config_file_path)

        # logging:
        # get log file name and format from config file
        # TODO: if logging section of config file is malformed, choose default
        # values and report the error to stderr
        log_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                self.config.get('log', 'log_file_name'))
        log_format = self.config.get('log', 'log_format')
        # make sure log file is writable
        try:
            open(log_file_path, 'a').close() # 'a' for append
        except Exception as e:
            # logging this error is impossible, so print to stderr
            print >> sys.stderr, 'Log file path "%s" is not writable.' \
                    % log_file_path
            raise
        # create logger
        self.logger = logging.getLogger('reebill')
        formatter = logging.Formatter(log_format)
        handler = logging.FileHandler(log_file_path)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        # loggers are created with level 'NOTSET' by default, except the root
        # logger (this one), which is created with level 'WARNING'. to include
        # messages like the initialization message at the end of this function,
        # the level has to be changed.
        self.logger.setLevel(logging.DEBUG)

        # create a NexusUtil
        self.nexus_util = NexusUtil(self.config.get('skyline_backend', 'nexus_web_host'))

        # load users database
        self.user_dao = UserDAO(**dict(self.config.items('usersdb')))

        # create an instance representing the database
        self.statedb_config = dict(self.config.items("statedb"))
        self.state_db = state.StateDB(
            host=self.statedb_config['host'],
            password=self.statedb_config['password'],
            database=self.statedb_config['database'],
            user=self.statedb_config['user'],
            logger=self.logger,
        )

        # create one BillUpload object to use for all BillUpload-related methods
        self.billUpload = BillUpload(self.config, self.logger)

        # create a MongoReeBillDAO
        self.billdb_config = dict(self.config.items("billdb"))
        self.reebill_dao = mongo.ReebillDAO(self.state_db,
                pymongo.Connection(self.billdb_config['host'],
                int(self.billdb_config['port']))[self.billdb_config['database']])

        # create a RateStructureDAO
        rsdb_config_section = dict(self.config.items("rsdb"))
        mongoengine.connect(rsdb_config_section['database'],
                host=rsdb_config_section['host'],
                port=int(rsdb_config_section['port']),
                alias='ratestructure')
        self.ratestructure_dao = rs.RateStructureDAO(logger=self.logger)

        # configure journal:
        # create a MongoEngine connection "alias" named "journal" with which
        # journal.Event subclasses (in journal.py) can associate themselves by
        # setting meta = {'db_alias': 'journal'}.
        journal_config = dict(self.config.items('journaldb'))
        mongoengine.connect(journal_config['database'],
                host=journal_config['host'], port=int(journal_config['port']),
                alias='journal')
        self.journal_dao = journal.JournalDAO()


        # set the server sessions key which is used to return credentials
        # in a client side cookie for the 'rememberme' feature
        if self.config.get('runtime', 'sessions_key'):
            self.sessions_key = self.config.get('runtime', 'sessions_key')

        # create a Splinter
        if self.config.getboolean('runtime', 'mock_skyliner'):
            self.splinter = mock_skyliner.MockSplinter()
        else:
            self.splinter = Splinter(
                self.config.get('skyline_backend', 'oltp_url'),
                skykit_host=self.config.get('skyline_backend', 'olap_host'),
                skykit_db=self.config.get('skyline_backend', 'olap_database'),
                olap_cache_host=self.config.get('skyline_backend', 'olap_host'),
                olap_cache_db=self.config.get('skyline_backend', 'olap_database'),
                monguru_options={
                    'olap_cache_host': self.config.get('skyline_backend', 'olap_host'),
                    'olap_cache_db': self.config.get('skyline_backend', 'olap_database'),
                    'cartographer_options': {
                        'olap_cache_host': self.config.get('skyline_backend', 'olap_host'),
                        'olap_cache_db': self.config.get('skyline_backend', 'olap_database'),
                        'measure_collection': 'skymap',
                        'install_collection': 'skyit_installs',
                        'nexus_host': self.config.get('skyline_backend', 'nexus_db_host'),
                        'nexus_db': 'nexus',
                        'nexus_collection': 'skyline',
                    },
                },
                cartographer_options={
                    'olap_cache_host': self.config.get('skyline_backend', 'olap_host'),
                    'olap_cache_db': self.config.get('skyline_backend', 'olap_database'),
                    'measure_collection': 'skymap',
                    'install_collection': 'skyit_installs',
                    'nexus_host': self.config.get('skyline_backend', 'nexus_db_host'),
                    'nexus_db': 'nexus',
                    'nexus_collection': 'skyline',
                },
            )

        self.integrate_skyline_backend = self.config.getboolean('runtime',
                'integrate_skyline_backend')

        # create a ReebillRenderer
        self.renderer = render.ReebillRenderer(
            dict(self.config.items('reebillrendering')), self.state_db,
            self.reebill_dao, self.logger)

        self.bill_mailer = Mailer(dict(self.config.items("mailer")))

        self.ree_getter = fbd.RenewableEnergyGetter(self.splinter,
                self.reebill_dao, self.logger)
        # create one Process object to use for all related bill processing
        self.process = process.Process(self.state_db, self.reebill_dao,
                self.ratestructure_dao, self.billUpload, self.nexus_util,
                self.bill_mailer, self.renderer, self.ree_getter, logger=self
                .logger)


        # determine whether authentication is on or off
        self.authentication_on = self.config.getboolean('authentication', 'authenticate')

        self.reconciliation_log_dir = self.config.get('reebillreconciliation', 'log_directory')
        self.reconciliation_report_dir = self.config.get('reebillreconciliation', 'report_directory')

        self.estimated_revenue_log_dir = self.config.get('reebillestimatedrevenue', 'log_directory')
        self.estimated_revenue_report_dir = self.config.get('reebillestimatedrevenue', 'report_directory')

        self.logger.info('BillToolBridge initialized')

    @cherrypy.expose
    def index(self):
        # delete remember me
        # This is how cookies are deleted? the key in the response cookie must
        # be set before expires can be set
        cherrypy.response.cookie['username'] = ""
        cherrypy.response.cookie['username'].expires = 0
        cherrypy.response.cookie['c'] = ""
        cherrypy.response.cookie['c'].expires = 0

        # delete the current server session
        if 'user' in cherrypy.session:
            self.logger.info('user "%s" logged out' % (cherrypy.session['user'].username))
            del cherrypy.session['user']

        raise cherrypy.HTTPRedirect('/index.html')

    @cherrypy.expose
    def login(username, password, rememberme='off', **kwargs):
        user = self.user_dao.load_user(username, password)
        if user is None:
            self.logger.info(('login attempt failed: username "%s"'
                ', remember me: %s') % (username, rememberme))
            return self.dumps({'success': False, 'errors':
                {'username':'Incorrect username or password', 'reason': 'No Session'}})

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ui_configuration(self, **kwargs):
        '''Returns the UI javascript file.'''
        ui_config_file_path = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), 'ui', 'ui.cfg')
        ui_config = ConfigParser.RawConfigParser()
        # NB: read() takes a list of file paths, not a file.
        # also note that ConfigParser converts all keys to lowercase
        ui_config.read([ui_config_file_path])

        # currently we have only one section
        config_dict = dict(ui_config.items('tabs'))

        # convert "true"/"false" strings to booleans
        config_dict = deep_map(
                lambda x: {'true':True, 'false':False}.get(x,x),
                config_dict)
        #config_dict['default_account_sort_field'] = cherrypy.session[
        # 'user'].preferences.get(
        #    'default_account_sort_field','account')
        #config_dict['default_account_sort_dir'] = cherrypy.session[
        # 'user'].preferences.get(
        #    'default_account_sort_direction','DESC')
        return config_dict

cherrypy_config = {
    '/': {
        'tools.sessions.on': True,
        'tools.staticdir.root': os.path.dirname(
            os.path.realpath(__file__))+'/ui'
    },
    '/login.html': {
        'tools.staticfile.on': True,
        'tools.staticfile.filename': os.path.dirname(
            os.path.realpath(__file__))+"/ui/login.html"
    },
    '/index.html': {
        'tools.staticfile.on': True,
        'tools.staticfile.filename': os.path.dirname(
            os.path.realpath(__file__))+"/ui/index.html"
    },
    '/static': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'static'
    }

}

if __name__ == '__main__':
    cherrypy.quickstart(BillToolBridge(), '/', cherrypy_config)
