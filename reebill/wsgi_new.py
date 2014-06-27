'''
File: wsgi.py
'''
from billing import initialize
initialize()
from billing import config

import sys
import os
import pprint

# TODO: 64957006
# Dislike having this exceptionally useful code here, whose purpose is to
# display the runtime  configuration to the operator of the software for
# troubleshooting.  Not having this code here, renders it useless.
sys.stdout = sys.stderr
pprint.pprint(os.environ)
pprint.pprint(sys.path)
pprint.pprint(sys.prefix)

import traceback
import json
import cherrypy
import os
import ConfigParser
from datetime import datetime, date, timedelta
import inspect
import logging
import time
import functools
import md5
from operator import itemgetter
from StringIO import StringIO
import pymongo
import mongoengine
from billing.skyliner.splinter import Splinter
from billing.skyliner import mock_skyliner
from billing.util import json_util as ju
from billing.util.dateutils import ISO_8601_DATE, ISO_8601_DATETIME_WITHOUT_ZONE
from billing.nexusapi.nexus_util import NexusUtil
from billing.util.dictutils import deep_map
from billing.processing import mongo, excel_export
from billing.processing.bill_mailer import Mailer
from billing.processing import process, state, fetch_bill_data as fbd,\
        rate_structure2 as rs
from billing.processing.state import UtilBill, Session
from billing.processing.billupload import BillUpload
from billing.processing import journal
from billing.processing import render
from billing.processing.users import UserDAO
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import Unauthenticated, IssuedBillError

pp = pprint.PrettyPrinter(indent=4).pprint


def authenticate():
    try:
        check_authentication()
    except Unauthenticated:
        raise cherrypy.HTTPRedirect('login.html')
cherrypy.tools.authenticate = cherrypy.Tool('before_handler', authenticate)


def authenticate_ajax():
    try:
        check_authentication()
    except Unauthenticated:
        raise cherrypy.HTTPError(401, "Unauthorized")
cherrypy.tools.authenticate_ajax = cherrypy.Tool(
    'before_handler', authenticate_ajax)


def check_authentication():
    logger = logging.getLogger('reebill')
    print '\n\n\n'
    print config.get('authentication','authenticate')
    if not config.get('authentication','authenticate'):
        if 'user' not in cherrypy.session:
            cherrypy.session['user'] = UserDAO.default_user
    if 'user' not in cherrypy.session:
        # the server did not have the user in session
        # log that user back in automatically based on
        # the credentials value found in the cookie
        # if this user is remembered?
        cookie = cherrypy.request.cookie
        credentials = cookie['c'].value if 'c' in cookie else None
        username = cookie['username'].value if 'username' in cookie else None

        user = self.user_dao.load_by_session_token(credentials)
        if user is None:
            logger.info(('Remember Me login attempt failed: username "%s"') % (username))
        else:
            logger.info(('Remember Me login attempt success: username "%s"') % (username))
            cherrypy.session['user'] = user
            return True
        raise Unauthenticated("No Session")
    return True

class WebResource(object):

    def __init__(self):
        self.config = config
        self.logger = logging.getLogger('reebill')

        self.session = Session

        # create a NexusUtil
        self.nexus_util = NexusUtil(self.config.get('skyline_backend', 'nexus_web_host'))

        # load users database
        self.user_dao = UserDAO(**dict(self.config.items('usersdb')))

        # create an instance representing the database
        self.statedb_config = dict(self.config.items("statedb"))
        self.state_db = state.StateDB(Session, logger=self.logger)

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
        if self.config.get('runtime', 'mock_skyliner'):
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

        self.integrate_skyline_backend = self.config.get('runtime',
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
        self.authentication_on = self.config.get('authentication', 'authenticate')

        self.reconciliation_log_dir = self.config.get('reebillreconciliation', 'log_directory')
        self.reconciliation_report_dir = self.config.get('reebillreconciliation', 'report_directory')

        self.estimated_revenue_log_dir = self.config.get('reebillestimatedrevenue', 'log_directory')
        self.estimated_revenue_report_dir = self.config.get('reebillestimatedrevenue', 'report_directory')


class RESTResource(WebResource):
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
    @cherrypy.tools.authenticate_ajax()
    def default(self, *vpath, **params):
        print "\n", vpath, "\n", params, "\n"
        method = getattr(self, "handle_" + cherrypy.request.method, None)

        if not method:
            methods = [x.replace("handle_", "")
                       for x in dir(self) if x.startswith("handle_")]
            cherrypy.response.headers["Allow"] = ",".join(methods)
            raise cherrypy.HTTPError(405, "Method not implemented.")

        response = method(*vpath, **params)

        try:
            success, response = response
        except TypeError:
            if cherrypy.request.method:
                raise cherrypy.HTTPError(404, "Not Found")
            raise cherrypy.HTTPError(500, "Internal Server Error")

        if cherrypy.request.method == 'POST' and success is True:
            cherrypy.response.status = "201 Created"

        if cherrypy.request.method == 'GET' and not response:
            cherrypy.response.status = "204 No Content"

        return json.dumps(response)


class AccountsListResource(RESTResource):

    def handle_GET(self, *vpath, **params):
        accounts = self.state_db.listAccounts(self.session)
        rows = [{'account': account, 'name': full_name} for account,
                full_name in zip(accounts,
                self.process.full_names_of_accounts(self.session, accounts))]
        return True, {'rows': rows, 'results': len(rows)}


class AccountsResource(RESTResource):
    list = AccountsListResource()

    def handle_GET(self, *vpath, **params):

        '''Handles AJAX request for "Account Processing Status" grid in
        "Accounts" tab.'''

        start, limit = int(params.get('start')), int(params.get('limit'))

        filtername = params.get('filtername', None)
        #if filtername is None:
        #    filtername = cherrypy.session['user'].preferences.get(
        # 'filtername','')

        sortcol = params.get('sort', None)
        #if sortcol is None:
        #    sortcol = cherrypy.session['user'].preferences.get(
        # 'default_account_sort_field',None)

        sortdir = params.get('dir', None)
        #if sortdir is None:
        #    sortdir = cherrypy.session['user'].preferences.get(
        # 'default_account_sort_direction',None)

        sortcol = 'account'
        sortdir = 'ASC'

        if sortdir == 'ASC':
            sortreverse = False
        else:
            sortreverse = True

        count, rows = self.process.list_account_status(
            self.session, start, limit, filtername, sortcol, sortreverse)

        #cherrypy.session['user'].preferences[
        #    'default_account_sort_field'] = sortcol
        #cherrypy.session['user'].preferences[
        # 'default_account_sort_direction'] = sortdir
        #self.user_dao.save_user(cherrypy.session['user'])

        return True, {'rows': rows, 'results': count}


class IssuableReebills(RESTResource):

    def handle_GET(self, *vpath, **params):
        '''Return a list of the issuable reebills'''
        start, limit = int(params['start']), int(params['limit'])
        sort = params.get('sort', 'account')
        direction = params.get('dir', 'DESC')
        try:
            allowable_diff = cherrypy.session['user'].preferences['difference_threshold']
        except:
            allowable_diff = UserDAO.default_user.preferences['difference_threshold']

        issuable_reebills = self.process.get_issuable_reebills_dict(
            self.session)
        for reebill_info in issuable_reebills:
            reebill_info['id'] = reebill_info['account'],
            reebill_info['difference'] = abs(reebill_info['reebill_total']-reebill_info['util_total'])
            reebill_info['matching'] = reebill_info['difference'] < allowable_diff

        issuable_reebills.sort(key=lambda d: d[sort],
                               reverse=(direction == 'DESC'))
        issuable_reebills.sort(key=lambda d: d['matching'], reverse=True)
        return True, {'rows': issuable_reebills[start:start+limit],
                      'results': len(issuable_reebills)}


class ReebillsResource(RESTResource):
    issuable = IssuableReebills()

    def handle_GET(self, *vpath, **params):
        start, limit = int(params['start']), int(params['limit'])
        sort = params.get('sort', 'account')
        direction = params.get('dir', 'DESC')

        '''Handles GET requests for reebill grid data.'''
        # this is inefficient but length is always <= 120 rows
        rows = sorted(self.process.get_reebill_metadata_json(
            self.session, account), key=itemgetter(sort))
        if direction == 'DESC':
            rows.reverse()

        # "limit" means number of rows to return, so the real limit is
        # start + limit
        result = rows[start: start + limit]
        return True, {'rows': result, 'results':len(rows)}


class BillToolBridge(WebResource):
    accounts = AccountsResource()
    reebills = ReebillsResource()

    @cherrypy.expose
    @cherrypy.tools.authenticate()
    def index(self):
        raise cherrypy.HTTPRedirect('index.html')

    @cherrypy.expose
    def login(self, username=None, password=None, rememberme='off', **kwargs):
        if cherrypy.request.method == "GET":
            raise cherrypy.HTTPRedirect('login.html')

        if cherrypy.request.method != "POST":
            raise cherrypy.HTTPError(403, "Forbidden")

        user = self.user_dao.load_user(username, password)
        if user is None:
            self.logger.info(('login attempt failed: username "%s"'
                ', remember me: %s') % (username, rememberme))
            return json.dumps(
                {'success': False,
                 'error': 'Incorrect username or password'
                })

        cherrypy.session['user'] = user

        if rememberme == 'on':
            # Create a random session string
            credentials = ''.join('%02x' % ord(x) for x in os.urandom(16))

            user.session_token = credentials
            self.user_dao.save_user(user)

            # this cookie has no expiration, so lasts as long as the browser is open
            cherrypy.response.cookie['username'] = user.username
            cherrypy.response.cookie['c'] = credentials

        self.logger.info(('user "%s" logged in: remember '
            'me: "%s" type is %s') % (username, rememberme,
            type(rememberme)))
        return json.dumps({'success': True})

    @cherrypy.expose
    def logout(self):
       # delete remember me
        # The key in the response cookie must be set before expires can be set
        cherrypy.response.cookie['username'] = ""
        cherrypy.response.cookie['username'].expires = 0
        cherrypy.response.cookie['c'] = ""
        cherrypy.response.cookie['c'].expires = 0

        # delete the current server session
        if 'user' in cherrypy.session:
            self.logger.info('user "%s" logged out' % (cherrypy.session['user'].username))
            del cherrypy.session['user']

        raise cherrypy.HTTPRedirect('login')


    @cherrypy.expose
    @cherrypy.tools.authenticate_ajax()
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
            lambda x: {'true': True, 'false': False}.get(x, x), config_dict)
        #config_dict['default_account_sort_field'] = cherrypy.session[
        # 'user'].preferences.get(
        #    'default_account_sort_field','account')
        #config_dict['default_account_sort_dir'] = cherrypy.session[
        # 'user'].preferences.get(
        #    'default_account_sort_direction','DESC')
        return config_dict


if __name__ == '__main__':
    bridge = BillToolBridge()
    local_conf = {
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
    cherrypy.config.update({
        'server.socket_host': bridge.config.get("http", "socket_host"),
        'server.socket_port': bridge.config.get("http", "socket_port")})
    cherrypy.quickstart(bridge, "/reebill", config = local_conf)
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, False)
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, True,
            stream=sys.stdout)
else:
    # WSGI Mode
    cherrypy.config.update({
        'environment': 'embedded',
        'tools.sessions.on': True,
        'tools.sessions.timeout': 240
    })

    if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
        cherrypy.engine.start(blocking=False)
        atexit.register(cherrypy.engine.stop)
    bridge = BillToolBridge()
    application = cherrypy.Application(bridge, script_name=None, config=None)

