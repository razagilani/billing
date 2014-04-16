'''
File: wsgi.py
'''
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
import jinja2, os
import string, re
import ConfigParser
from datetime import datetime, date, timedelta
import itertools as it
import uuid as UUID # uuid collides with locals so both module and locals are renamed
import inspect
import logging
import csv
import random
import time
import copy
import functools
import re
import md5
from operator import itemgetter
import errno
from StringIO import StringIO
from itertools import chain
import pymongo
import mongoengine
from skyliner.splinter import Splinter
from skyliner import mock_skyliner
from billing.util import json_util as ju
from billing.util.dateutils import ISO_8601_DATE, ISO_8601_DATETIME_WITHOUT_ZONE
from nexusapi.nexus_util import NexusUtil
from billing.util.dictutils import deep_map
from billing.processing import mongo, excel_export
from billing.processing.bill_mailer import Mailer
from billing.processing import process, state, fetch_bill_data as fbd, rate_structure2 as rs
from billing.processing.state import UtilBill, Customer
from billing.processing.billupload import BillUpload
from billing.processing import journal
from billing.processing import render
from billing.processing.users import UserDAO, User
from billing.processing import calendar_reports
from billing.processing.estimated_revenue import EstimatedRevenue
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import Unauthenticated, IssuedBillError, NoSuchBillException

pp = pprint.PrettyPrinter(indent=4).pprint

# from http://code.google.com/p/modwsgi/wiki/DebuggingTechniques#Python_Interactive_Debugger
class Debugger:
    def __init__(self, object):
        self.__object = object

    def __call__(self, *args, **kwargs):
        import pdb, sys
        debugger = pdb.Pdb()
        debugger.use_rawinput = 0
        debugger.reset()
        sys.settrace(debugger.trace_dispatch)

        try:
            return self.__object(*args, **kwargs)
        finally:
            debugger.quitting = 1
            sys.settrace(None)

# decorator for stressing ajax asynchronicity
def random_wait(target):
    @functools.wraps(target)
    def random_wait_wrapper(*args, **kwargs):
        #t = random.random()
        t = 0
        time.sleep(t)
        return target(*args, **kwargs)
    return random_wait_wrapper

def authenticate_ajax(method):
    '''Wrapper for AJAX-request-handling methods that require a user to be
    logged in. This should go "inside" (i.e. after) the cherrypy.expose
    decorator.'''
    # wrapper function takes a BillToolBridge object as its first argument, and
    # passes that as the "self" argument to the wrapped function. so this
    # decorator, which runs before any instance of BillToolBridge exists,
    # doesn't need to know about any BillToolBridge instance data. the wrapper
    # is executed when an HTTP request is received, so it can use BTB instance
    # data.
    @functools.wraps(method)
    def wrapper(btb_instance, *args, **kwargs):
        try:
            btb_instance.check_authentication()
            return method(btb_instance, *args, **kwargs)
        except Unauthenticated as e:
            return btb_instance.dumps({'success': False, 'code':1})
    return wrapper

def authenticate(method):
    '''Like @authenticate_ajax, but redirects non-logged-in users to
    /login.html. This should be used for "regular" HTTP requests (like file
    downloads), in which a redirect can be returned directly to the browser.'''
    # note: if you want to add a redirect_url argument to the decorator (so
    # it's not always '/login.html'), you need 3 layers: outer function
    # (authenticate) takes redirect_url argument, intermediate wrapper takes
    # method argument and returns inner wrapper, which takes the method itself
    # as its argument and returns the wrapped version.
    @functools.wraps(method)
    def wrapper(btb_instance, *args, **kwargs):
        try:
            btb_instance.check_authentication()
            return method(btb_instance, *args, **kwargs)
        except Unauthenticated:
            # Non-Ajax requests can't handle json responses
            #return ju.dumps({'success': False, 'code': 1, 'errors':
            #    {'reason': 'Authenticate: No Session'}})
            cherrypy.response.status = 403
            raise cherrypy.HTTPRedirect('/login.html')
    return wrapper

def json_exception(method):
    '''Decorator for exception handling in methods trigged by Ajax requests.'''
    @functools.wraps(method)
    def wrapper(btb_instance, *args, **kwargs):
        #print >> sys.stderr, '*************', method, args
        try:
            return method(btb_instance, *args, **kwargs)
        except Exception as e:
            return btb_instance.handle_exception(e)
    return wrapper


# TODO 11454025 rename to ProcessBridge or something
# TODO (object)?
class BillToolBridge:
    # TODO: clean up this comment on how to use sessions.
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill processing code.  No business logic should reside here."""

    """
    Notes on using SQLAlchemy.  Since the ORM sits on top of the MySQL API, care must
    be given to the underlying resource utilization.  Namely, sessions have to be
    closed via a commit or rollback.

    Also, SQLAlchemy may be lazy in the way it executes database operations.  Primary
    keys may not be returned and set in an instance unless commit is called.  Therefore,
    ensure that a commit is issued before using newly inserted instances.

    The pattern of usage is as follows:
    - declare a local variable that will point to a session at the top of a try block
    - initialize this variable to None, so that if an exception is subsequently raised
      the local will not be undefined.
    - pass the session into a statedb function.
    - commit the session once, immediately before returning out of the WSGI function
    - if an exception was raised, and the local variable pointing to the session is
      initialized, then rollback.
    """

    config = None

    # TODO: refactor config and share it between btb and bt 15413411
    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'reebill.cfg')
        if not self.config.read(config_file_path):
            # TODO: 64958246
            # can't log this because logger hasn't been created yet (log file
            # name & associated info comes from config file)
            print >> sys.stderr, 'Config file "%s" not found; creating it with default values'
            self.config.add_section('runtime')
            self.config.set('runtime', 'integrate_skyline_backend', 'true')
            self.config.set('runtime', 'integrate_nexus', 'true')
            self.config.set('runtime', 'sessions_key', 'some random bytes to all users to automatically reauthenticate')
            self.config.set('runtime', 'mock_skyliner', 'false')

            self.config.add_section('skyline_backend')
            self.config.set('skyline_backend', 'oltp_url', 'http://duino-drop.appspot.com/')
            self.config.set('skyline_backend', 'olap_host', 'tyrell')
            self.config.set('skyline_backend', 'olap_database', 'dev')
            self.config.set('skyline_backend', 'nexus_db_host', '[specify nexus mongo host for direct conns from skyliner]')
            self.config.set('skyline_backend', 'nexus_web_host', '[specify nexus web host for NexusAPI/NexusUtil]')

            self.config.add_section('journaldb')
            self.config.set('journaldb', 'host', 'localhost')
            self.config.set('journaldb', 'port', '27017')
            self.config.set('journaldb', 'database', 'skyline')

            self.config.add_section('http')
            self.config.set('http', 'socket_port', '8185')
            self.config.set('http', 'socket_host', '10.0.0.250')

            self.config.add_section('rsdb')
            self.config.set('rsdb', 'host', 'localhost')
            self.config.set('rsdb', 'port', '27017')
            self.config.set('rsdb', 'database', 'skyline')

            self.config.add_section('billdb')
            self.config.set('billdb', 'utilitybillpath', '[root]db/skyline/utilitybills/')
            self.config.set('billdb', 'billpath', '[root]db/skyline/bills/')
            self.config.set('billdb', 'host', 'localhost')
            self.config.set('billdb', 'port', '27017')
            self.config.set('billdb', 'database', 'skyline')
            self.config.set('billdb', 'utility_bill_trash_directory', '[root]db/skyline/utilitybills-deleted')

            self.config.add_section('statedb')
            self.config.set('statedb', 'host', 'localhost')
            self.config.set('statedb', 'database', 'skyline')
            self.config.set('statedb', 'user', '[your mysql user]')
            self.config.set('statedb', 'password', '[your mysql password]')

            self.config.add_section('usersdb')
            self.config.set('usersdb', 'host', 'localhost')
            self.config.set('usersdb', 'database', 'skyline')
            self.config.set('usersdb', 'port', '27017')

            self.config.add_section('mailer')
            self.config.set('mailer', 'smtp_host', 'smtp.gmail.com')
            self.config.set('mailer', 'smtp_port', '587')
            self.config.set('mailer', 'originator', 'jwatson@skylineinnovations.com')
            self.config.set('mailer', 'from', '"Jules Watson" <jwatson@skylineinnovations.com>')
            self.config.set('mailer', 'bcc_list', '')
            self.config.set('mailer', 'password', 'password')

            self.config.add_section('authentication')
            self.config.set('authentication', 'authenticate', 'true')

            # For BillUpload
            # default name of log file (config file can override this)
            DEFAULT_LOG_FILE_NAME = 'reebill.log'

            # default format of log entries (config file can override this)
            DEFAULT_LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

            # directory where bill images are temporarily stored
            DEFAULT_BILL_IMAGE_DIRECTORY = '/tmp/billimages'

            # directory to store temporary files for pdf rendering
            DEFAULT_RENDERING_TEMP_DIRECTORY = '/tmp'
            DEFAULT_TEMPLATE = 'skyline'

            # log file info
            self.config.add_section('log')
            self.config.set('log', 'log_file_name', DEFAULT_LOG_FILE_NAME)
            self.config.set('log', 'log_format', DEFAULT_LOG_FORMAT)

            # bill image rendering
            self.config.add_section('billimages')
            self.config.set('billimages', 'bill_image_directory', DEFAULT_BILL_IMAGE_DIRECTORY)
            self.config.set('billimages', 'show_reebill_images', 'true')

            # reebill pdf rendering
            self.config.add_section('reebillrendering')
            self.config.set('reebillrendering', 'temp_directory', DEFAULT_RENDERING_TEMP_DIRECTORY)
            self.config.set('reebillrendering', 'template_directory', "absolute path to reebill_templates/")
            self.config.set('reebillrendering', 'default_template', DEFAULT_TEMPLATE)
            self.config.set('reebillrendering', 'teva_accounts', '')

            # reebill reconciliation
            # TODO 54911020 /tmp is a really bad default
            DEFAULT_RECONCILIATION_LOG_DIRECTORY = '/tmp'
            DEFAULT_RECONCILIATION_REPORT_DIRECTORY = '/tmp'
            self.config.add_section('reebillreconciliation')
            self.config.set('reebillreconciliation', 'log_directory', DEFAULT_RECONCILIATION_LOG_DIRECTORY)
            self.config.set('reebillreconciliation', 'report_directory', DEFAULT_RECONCILIATION_REPORT_DIRECTORY)


            # TODO default config file is incomplete

            # Writing our configuration file to 'example.cfg'
            with open(config_file_path, 'wb') as new_config_file:
                self.config.write(new_config_file)

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
                self.reebill_dao)
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

        # print a message in the log--TODO include the software version
        self.logger.info('BillToolBridge initialized')

    def dumps(self, data):

        # accept only dictionaries so that additional keys may be added
        if type(data) is not dict: raise ValueError("Dictionary required.")

        if 'success' in data: 
            if data['success']: 
                # nothing else required
                pass
            else:
                if 'errors' not in data:
                    self.logger.warning('JSON response require errors key.')
        else:
            self.logger.warning('JSON response require success key.')

        # diagnostic information for client side troubleshooting
        data['server_url'] = cherrypy.url()
        data['server_time'] = datetime.now()

        # round datetimes to nearest second so Ext-JS JsonReader can parse them
        def round_datetime(x):
            if isinstance(x, datetime):
                return datetime(x.year, x.month, x.day, x.hour, x.minute,
                        x.second)
            return x
        data = deep_map(round_datetime, data)

        return ju.dumps(data)
    
    @cherrypy.expose
    @random_wait
    @authenticate
    def index(self, **kwargs):
        raise cherrypy.HTTPRedirect('/billentry.html')

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def get_reconciliation_data(self, start, limit, **kwargs):
        '''Handles AJAX request for data to fill reconciliation report grid.'''
        start, limit = int(start), int(limit)
        # TODO 45793319: hardcoded file name
        with open(os.path.join(self.reconciliation_report_dir,'reconciliation_report.json')) as json_file:
            # load all data from json file: it's one JSON dictionary per
            # line (for reasons explained in reconciliation.py) but should
            # be interpreted as a JSON list
            # TODO 45793037: not really a json file until now
            items = ju.loads('[' + ', '.join(json_file.readlines()) + ']')
            return self.dumps({
                'success': True,
                'rows': items[start:start+limit],
                'results': len(items) # total number of items
            })

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def get_estimated_revenue_data(self, start, limit, **kwargs):
        '''Handles AJAX request for data to fill estimated revenue report grid.'''
        start, limit = int(start), int(limit)
        # TODO 45793319: hardcoded file name
        with open(os.path.join(self.estimated_revenue_report_dir,'estimated_revenue_report.json')) as json_file:
            items = ju.loads(json_file.read())['rows']
            return self.dumps({
                'success': True,
                'rows': items[start:start+limit],
                'results': len(items) # total number of items
            })
    
    @cherrypy.expose
    @random_wait
    @authenticate
    @json_exception
    def estimated_revenue_xls(self, **kwargs):
        '''Responds with the data from the estimated revenue report in the form
        of an Excel spreadsheet.'''
        spreadsheet_name =  'estimated_revenue.xls'

        # TODO 45793319: hardcoded file name
        with open(os.path.join(self.estimated_revenue_report_dir,'estimated_revenue_report.xls')) as xls_file:
            # set headers for file download
            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % spreadsheet_name

            return xls_file.read()

    ###########################################################################
    # authentication functions

    @cherrypy.expose
    @random_wait
    def login(self, username, password, rememberme='off', **kwargs):
        user = self.user_dao.load_user(username, password)
        if user is None:
            self.logger.info(('login attempt failed: username "%s"'
                ', remember me: %s') % (username, rememberme))
            return self.dumps({'success': False, 'errors':
                {'username':'Incorrect username or password', 'reason': 'No Session'}})

        # successful login:

        # create session object
        # if 'rememberme' is true, timeout is 1 week (10080 minutes) and
        # 'persistent' argument is true; if not, persistent is false and
        # timeout has no effect (cookie expires when browser is closed)
        # the functions below cause an error
        #cherrypy.lib.sessions.expire()
        #cherrypy.lib.sessions.init(timeout=1,
        #        persistent=(rememberme == 'on'))
        #cherrypy.session.regenerate()

        # store identifier & user preferences in cherrypy session object &
        # redirect to main page
        cherrypy.session['user'] = user

        if rememberme == 'on':
            # The user has elected to be remembered
            # so create credentials based on a server secret, the user's IP address and username.
            # Some other reasonably secret, ephemeral, information could also be included such as 
            # current date.
            credentials = "%s-%s-%s" % (username, cherrypy.request.headers['Remote-Addr'], self.sessions_key)
            m = md5.new()
            m.update(credentials)
            digest = m.hexdigest()

            # Set this token in the persistent user object
            # then, if returned to the server it can be looked up in the user
            # and the user can be automatically logged in.
            # This giving the user who has just authenticated a credential that
            # can be later used for automatic authentication.
            user.session_token = digest
            self.user_dao.save_user(user)

            # this cookie has no expiration, so lasts as long as the browser is open
            cherrypy.response.cookie['username'] = user.username
            cherrypy.response.cookie['c'] = digest

        self.logger.info(('user "%s" logged in: remember '
            'me: "%s" type is %s') % (username, rememberme,
            type(rememberme)))
        return self.dumps({'success': True});

    def check_authentication(self):
        '''Function to check authentication for HTTP request functions: if user
        is not logged in, raises Unauthenticated exception. If authentication
        is turned off, ensures that the default user's data are in the cherrypy
        session. Does not redirect to the login page, because it gets called in
        AJAX requests, which must return actual data instead of a redirect.
        This is not meant to be called directly, but via the @authenticate_ajax or
        @authenticate decorators.'''
        if not self.authentication_on:
            if 'user' not in cherrypy.session:
                cherrypy.session['user'] = UserDAO.default_user
        if 'user' not in cherrypy.session:
            # is this user rememberme'd?
            cookie = cherrypy.request.cookie
            username = cookie['username'].value if 'username' in cookie else None
            credentials = cookie['c'].value if 'c' in cookie else None

            # the server did not have the user in session
            # log that user back in automatically based on 
            # the credentials value found in the cookie
            credentials = "%s-%s-%s" % (username, cherrypy.request.headers['Remote-Addr'], self.sessions_key)
            m = md5.new()
            m.update(credentials)
            digest = m.hexdigest()
            user = self.user_dao.load_by_session_token(digest)
            if user is None:
                self.logger.info(('Remember Me login attempt failed: username "%s"') % (username))
            else:
                self.logger.info(('Remember Me login attempt success: username "%s"') % (username))
                cherrypy.session['user'] = user
                return

            # TODO show the wrapped function name here instead of "wrapper"
            # (probably inspect.stack is too smart to be fooled by
            # functools.wraps)
            self.logger.info(("Non-logged-in user was denied access"
                    " to: %s") % inspect.stack()[1][3])
            raise Unauthenticated("No Session")

    def handle_exception(self, e):
        if type(e) is cherrypy.HTTPRedirect:
            # don't treat cherrypy redirect as an error
            raise
        elif type(e) is Unauthenticated:
            return self.dumps({'success': False, 'errors':{ 'reason': str(e),
                    'details': ('if you are reading this message a client'
                    ' request did not properly handle an invalid session'
                    ' response.')}})
        else:
            # normal exception
            try:
                self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            except:
                print >> sys.stderr, "Logger not functioning\n%s:\n%s" % (
                        e, traceback.format_exc())
            return self.dumps({'success': False, 'code':2, 'errors':{'reason': str(e),
                    'details':traceback.format_exc()}})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getUsername(self, **kwargs):
        '''This returns the username of the currently logged-in user--not to be
        confused with the identifier. The identifier is a unique id but the
        username is not.'''
        with DBSession(self.state_db) as session:
            return self.dumps({'success':True,
                    'username': cherrypy.session['user'].username})

    @cherrypy.expose
    @random_wait
    def logout(self):

        # delete remember me
        # This is how cookies are deleted? the key in the response cookie must be set before
        # expires can be set
        cherrypy.response.cookie['username'] = ""
        cherrypy.response.cookie['username'].expires = 0
        cherrypy.response.cookie['c'] = ""
        cherrypy.response.cookie['c'].expires = 0

        # delete the current server session
        if hasattr(cherrypy, 'session') and 'user' in cherrypy.session:
            self.logger.info('user "%s" logged out' % (cherrypy.session['user'].username))
            del cherrypy.session['user']

        raise cherrypy.HTTPRedirect('/login.html')

    ###########################################################################
    # UI configuration

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
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
        config_dict['default_account_sort_field'] = cherrypy.session['user'].preferences.get(
            'default_account_sort_field','account')
        config_dict['default_account_sort_dir'] = cherrypy.session['user'].preferences.get(
            'default_account_sort_direction','DESC')
        return json.dumps(config_dict)

    ###########################################################################
    # bill processing

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def get_next_account_number(self, **kwargs):
        '''Handles AJAX request for what the next account would be called if it
        were created (highest existing account number + 1--we require accounts
        to be numbers, even though we always store them as arbitrary
        strings).'''
        with DBSession(self.state_db) as session:
            next_account = self.state_db.get_next_account_number(session)
            return self.dumps({'success': True, 'account': next_account})
            
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def new_account(self, name, account, discount_rate, late_charge_rate,
            template_account, ba_addressee, ba_street, ba_city, ba_state,
            ba_postal_code, sa_addressee, sa_street, sa_city, sa_state,
            sa_postal_code, **kwargs):
        with DBSession(self.state_db) as session:
            billing_address = {
                'addressee': ba_addressee,
                'street': ba_street,
                'city': ba_city,
                'state': ba_state,
                'postal_code': ba_postal_code,
            }
            service_address = {
                'addressee': sa_addressee,
                'street': sa_street,
                'city': sa_city,
                'state': sa_state,
                'postal_code': sa_postal_code,
            }

            self.process.create_new_account(session, account, name,
                    discount_rate, late_charge_rate, billing_address,
                    service_address, template_account)

            # record account creation
            # (no sequence associated with this)
            journal.AccountCreatedEvent.save_instance(cherrypy.session['user'],
                    account)

            # get next account number to send it back to the client so it
            # can be shown in the account-creation form
            next_account = self.state_db.get_next_account_number(session)
            return self.dumps({'success': True, 'nextAccount': next_account})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def roll(self, account, **kwargs):
        start_date = kwargs.get('start_date')
        if start_date is not None:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        with DBSession(self.state_db) as session:
            reebill = self.process.roll_reebill(session,account,
                    start_date=start_date,
                    integrate_skyline_backend=self.integrate_skyline_backend)

            journal.ReeBillRolledEvent.save_instance(cherrypy.session['user'],
                    account, reebill.sequence)
            # Process.roll includes attachment
            # TODO "attached" is no longer a useful event;
            # see https://www.pivotaltracker.com/story/show/55044870
            journal.ReeBillAttachedEvent.save_instance(cherrypy.session['user'],
                account, reebill.sequence, reebill.version)
            journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, reebill.sequence, reebill.version)

        return self.dumps({'success': True, 'account':account,
                           'sequence': reebill.sequence})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def bindree(self, account, sequence, **kwargs):
        '''Puts energy from Skyline OLTP into shadow registers of the reebill
        given by account, sequence.'''
        if self.config.getboolean('runtime', 'integrate_skyline_backend') is False:
            raise ValueError("OLTP is not integrated")
        if self.config.getboolean('runtime', 'integrate_nexus') is False:
            raise ValueError("Nexus is not integrated")
        sequence = int(sequence)

        with DBSession(self.state_db) as session:
            self.process.bind_renewable_energy(session, account, sequence)
            reebill = self.state_db.get_reebill(session, account, sequence)
            journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                    account, sequence, reebill.version)
        return self.dumps({'success': True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def upload_interval_meter_csv(self, account, sequence, csv_file,
            timestamp_column, timestamp_format, energy_column, energy_unit, register_identifier, **args):
        '''Takes an upload of an interval meter CSV file (cherrypy file upload
        object) and puts energy from it into the shadow registers of the
        reebill given by account, sequence.'''
        reebill = self.process.upload_interval_meter_csv(account, sequence,
                        csv_file,timestamp_column, timestamp_format,
                        energy_column, energy_unit, register_identifier, args)
        journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, sequence, reebill.version)
        return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    # TODO clean this up and move it out of BillToolBridge
    # https://www.pivotaltracker.com/story/show/31404685
    def compute_bill(self, account, sequence, **args):
        '''Handler for the front end's "Compute Bill" operation.'''
        sequence = int(sequence)
        with DBSession(self.state_db) as session:
            self.process.compute_reebill(session,account,sequence,'max')
            return self.dumps({'success': True})
    
        
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def mark_utilbill_processed(self, utilbill, processed, **kwargs):
        '''Takes a utilbill id and a processed-flag and applies they flag to the bill '''
        utilbill, processed = int(utilbill), bool(int(processed))
        with DBSession(self.state_db) as session:
            self.process.update_utilbill_metadata(session, utilbill, processed=processed)
            return self.dumps({'success': True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def compute_utility_bill(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            self.process.compute_utility_bill(session, utilbill_id)
            return self.dumps({'success': True})
    
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def has_utilbill_predecessor(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            predecessor=self.process.has_utilbill_predecessor(session, utilbill_id)
            return self.dumps({'success': True, 'has_predecessor':predecessor})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def refresh_charges(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            self.process.refresh_charges(session, utilbill_id)
            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def regenerate_rs(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            self.process.regenerate_uprs(session, utilbill_id)
            # NOTE utility bill is not automatically computed after rate
            # structure is changed. nor are charges updated to match.
            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def render(self, account, sequence, **args):
        sequence = int(sequence)
        if not self.config.getboolean('billimages', 'show_reebill_images'):
            return self.dumps({'success': False, 'code':2, 'errors': {'reason':
                    ('"Render" does nothing because reebill images have '
                    'been turned off.'), 'details': ''}})
        with DBSession(self.state_db) as session:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            # TODO 22598787 - branch awareness
            self.renderer.render(
                session,
                account,
                sequence,
                self.config.get("billdb", "billpath")+ "%s" % account,
                "%.5d_%.4d.pdf" % (int(account), int(sequence)),
                #"EmeraldCity-FullBleed-1v2.png,EmeraldCity-FullBleed-2v2.png",
                False
            )
            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def issue_and_mail(self, account, sequence, recipients, apply_corrections,
                       **kwargs):
        sequence = int(sequence)
        apply_corrections = (apply_corrections == 'true')

        with DBSession(self.state_db) as session:
            # If there are unissued corrections and the user has not confirmed
            # to issue them, we will return a list of those corrections and the
            # sum of adjustments that have to be made so the client can create
            # a confirmation message
            unissued_corrections = self.process.get_unissued_corrections(session, account)
            if len(unissued_corrections) > 0 and not apply_corrections:
                    return self.dumps({'success': False,
                        'corrections': [c[0] for c in unissued_corrections],
                        'adjustment': sum(c[2] for c in unissued_corrections)})

            # The user has confirmed to issue unissued corrections.
            # Let's issue
            if len(unissued_corrections) > 0:
                assert apply_corrections is True
                self.process.issue_corrections(session, account, sequence)
                for cor in unissued_corrections:
                    journal.ReeBillIssuedEvent.save_instance(
                        cherrypy.session['user'],account, sequence,
                        self.state_db.max_version(session, account, cor),
                        applied_sequence=sequences[0])
            self.process.compute_reebill(session, account, sequence)
            self.process.issue(session, account, sequence)
            journal.ReeBillIssuedEvent.save_instance(cherrypy.session['user'],
                                                     account, sequence, 0)

            # Let's mail!
            # Recepients can be a comma seperated list of email addresses
            recipient_list = [rec.strip() for rec in recipients.split(',')]
            self.process.mail_reebills(session, account, [sequence],
                                       recipient_list)
            journal.ReeBillMailedEvent.save_instance(cherrypy.session['user'],
                                                account, sequence, recipients)

        return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def mail(self, account, sequences, recipients, **kwargs):
        # Go from comma-separated e-mail addresses to a list of e-mail addresses
        recipient_list = [rec.strip() for rec in recipients.split(',')]

        # sequences will come in as a string if there is one element in post data.
        # If there are more, it will come in as a list of strings
        if type(sequences) is list:
            sequences = sorted(map(int, sequences))
        else:
            sequences = [int(sequences)]

        with DBSession(self.state_db) as session:
            self.process.mail_reebills(session, account, sequences,
                    recipient_list)

            # journal mailing of every bill
            for sequence in sequences:
                journal.ReeBillMailedEvent.save_instance(
                        cherrypy.session['user'], account, sequence, recipients)

            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def listAccounts(self, **kwargs):
        with DBSession(self.state_db) as session:
            accounts = self.state_db.listAccounts(session)
            rows = [{'account': account, 'name': full_name} for account,
                    full_name in zip(accounts,
                    self.process.full_names_of_accounts(session, accounts))]
            return self.dumps({'success': True, 'rows':rows})

    # It is believed that this code is not used anymore. If there are no
    # complaints concerning this export after release 19,
    # this code can be removed.
    # @cherrypy.expose
    # @random_wait
    # @authenticate_ajax
    # @json_exception
    # def listSequences(self, account, **kwargs):
    #     '''Handles AJAX request to get reebill sequences for each account and
    #     whether each reebill has been committed.'''
    #     with DBSession(self.state_db) as session:
    #         sequences = []
    #         # eventually, this data will have to support pagination
    #         sequences = self.state_db.listSequences(session, account)
    #         # TODO "issued" is used for the value of "committed" here because
    #         # committed is ill-defined: currently StateDB.is_committed()
    #         # returns true iff the reebill has attached utilbills, which
    #         # doesn't make sense.
    #         # https://www.pivotaltracker.com/story/show/24382885
    #         rows = [{'sequence': sequence,
    #             'committed': self.state_db.is_issued(session, account, sequence)}
    #             for sequence in sequences]
    #         return self.dumps({'success': True, 'rows':rows})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def retrieve_account_status(self, start, limit ,**kwargs):
        '''Handles AJAX request for "Account Processing Status" grid in
        "Accounts" tab.'''

        with DBSession(self.state_db) as session:
            start, limit = int(start), int(limit)

            filtername = kwargs.get('filtername', None)
            if filtername is None:
                filtername = cherrypy.session['user'].preferences.get('filtername','')

            sortcol = kwargs.get('sort', None)
            if sortcol is None:
                sortcol = cherrypy.session['user'].preferences.get('default_account_sort_field',None)

            sortdir = kwargs.get('dir', None)
            if sortdir is None:
                sortdir = cherrypy.session['user'].preferences.get('default_account_sort_direction',None)

            if sortdir == 'ASC':
                sortreverse = False
            else:
                sortreverse = True

            count, rows = self.process.list_account_status(session,start,limit,filtername,sortcol,sortreverse)

            cherrypy.session['user'].preferences['default_account_sort_field'] = sortcol
            cherrypy.session['user'].preferences['default_account_sort_direction'] = sortdir
            self.user_dao.save_user(cherrypy.session['user'])

            return self.dumps({'success': True, 'rows':rows, 'results':count})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def reebill_details_xls(self, begin_date=None, end_date=None, **kwargs):
        '''
        Responds with an excel spreadsheet containing all actual charges, total
        energy and rate structure for all utility bills for the given account,
        or every account (1 per sheet) if 'account' is not given,
        '''
        #write out spreadsheet(s)
        with DBSession(self.state_db) as session:
            buf = StringIO()
            exporter = excel_export.Exporter(self.state_db, self.reebill_dao)

            # write excel spreadsheet into a StringIO buffer (file-like)
            buf = StringIO()
            exporter.export_reebill_details(session, buf)

            # set MIME type for file download
            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = \
                'attachment; filename=%s.xls' % \
                datetime.now().strftime("%Y%m%d")
            return buf.getvalue()

    # It is believed that this code is not used anymore. If there are no
    # complaints concerning this export after release 19,
    # this code can be removed.
    # @cherrypy.expose
    # @random_wait
    # @authenticate_ajax
    # @json_exception
    # def all_ree_charges_csv_altitude(self, **args):
    #     with DBSession(self.state_db) as session:
    #         rows, total_count = self.process.reebill_report_altitude(session)
    #
    #         import csv
    #         import StringIO
    #
    #         buf = StringIO.StringIO()
    #
    #         writer = csv.writer(buf)
    #
    #         writer.writerow(['Account-Sequence', 'Period End', 'RE&E Charges'])
    #
    #         for row in rows:
    #             ba = row['billing_address']
    #             bill_addr_str = "%s %s %s %s %s" % (
    #                 ba['addressee'] if 'addressee' in ba and ba['addressee'] is not None else "",
    #                 ba['street'] if 'street' in ba and ba['street'] is not None else "",
    #                 ba['city'] if 'city' in ba and ba['city'] is not None else "",
    #                 ba['state'] if 'state' in ba and ba['state'] is not None else "",
    #                 ba['postal_code'] if 'postal_code' in ba and ba['postal_code'] is not None else "",
    #             )
    #             sa = row['service_address']
    #             service_addr_str = "%s %s %s %s %s" % (
    #                 sa['addressee'] if 'addressee' in sa and sa['addressee'] is not None else "",
    #                 sa['street'] if 'street' in sa and sa['street'] is not None else "",
    #                 sa['city'] if 'city' in sa and sa['city'] is not None else "",
    #                 sa['state'] if 'state' in sa and sa['state'] is not None else "",
    #                 sa['postal_code'] if 'postal_code' in sa and sa['postal_code'] is not None else "",
    #             )
    #
    #             writer.writerow(["%s-%s" % (row['account'], row['sequence']), row['period_end'], row['ree_charges']])
    #
    #             cherrypy.response.headers['Content-Type'] = 'text/csv'
    #             cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s.csv' % datetime.now().strftime("%Y%m%d")
    #
    #
    #         data = buf.getvalue()
    #         return data

    # It is believed that this code is not used anymore. If there are no
    # complaints concerning this export after release 19,
    # this code can be removed.
    # @cherrypy.expose
    # @random_wait
    # @authenticate_ajax
    # @json_exception
    # def discount_rates_csv_altitude(self, **args):
    #     with DBSession(self.state_db) as session:
    #         rows, total_count = self.process.reebill_report_altitude(session)
    #
    #         import csv
    #         import StringIO
    #
    #         buf = StringIO.StringIO()
    #
    #         writer = csv.writer(buf)
    #
    #         writer.writerow(['Account', 'Discount Rate'])
    #
    #         for account, group in it.groupby(rows, lambda row: row['account']):
    #             for row in group:
    #                 if row['discount_rate']:
    #                     writer.writerow([account, row['discount_rate']])
    #                     break
    #
    #         cherrypy.response.headers['Content-Type'] = 'text/csv'
    #         cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=reebill_discount_rates_%s.csv' % datetime.now().strftime("%Y%m%d")
    #
    #         data = buf.getvalue()
    #         return data


    @cherrypy.expose
    @random_wait
    @authenticate
    @json_exception
    def excel_export(self, account=None, start_date=None, end_date=None, **kwargs):
        '''
        Responds with an excel spreadsheet containing all actual charges for all
        utility bills for the given account, or every account (1 per sheet) if
        'account' is not given, or all utility bills for the account(s) filtered
        by time, if 'start_date' and/or 'end_date' are given.
        '''
        with DBSession(self.state_db) as session:
            if account is not None:
                spreadsheet_name = account + '.xls'
            else:
                spreadsheet_name = 'all_accounts.xls'

            exporter = excel_export.Exporter(self.state_db, self.reebill_dao)

            # write excel spreadsheet into a StringIO buffer (file-like)
            buf = StringIO()
            exporter.export_account_charges(session, buf, account, start_date=start_date,
                            end_date=end_date)

            # set MIME type for file download
            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % spreadsheet_name

            return buf.getvalue()

    @cherrypy.expose
    @random_wait
    @authenticate
    @json_exception
    def excel_energy_export(self, account=None, **kwargs):
        '''
        Responds with an excel spreadsheet containing all actual charges, total
        energy and rate structure for all utility bills for the given account,
        or every account (1 per sheet) if 'account' is not given,
        '''
        with DBSession(self.state_db) as session:
            if account is not None:
                spreadsheet_name = account + '.xls'
            else:
                spreadsheet_name = 'xbill_accounts.xls'

            exporter = excel_export.Exporter(self.state_db, self.reebill_dao)

            # write excel spreadsheet into a StringIO buffer (file-like)
            buf = StringIO()
            exporter.export_energy_usage(session, buf, account)

            # set MIME type for file download
            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % spreadsheet_name

            return buf.getvalue()

    @cherrypy.expose
    @random_wait
    @authenticate
    @json_exception
    def daily_average_energy_xls(self, account, **kwargs):
        '''Responds with an excel spreadsheet containing daily average energy
        over all time for the given account.'''
        with DBSession(self.state_db) as session:
            buf = StringIO()
            # TODO: include all services
            calendar_reports.write_daily_average_energy_xls(self.reebill_dao, account, buf, service='gas')

            # set MIME type for file download
            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = ('attachment;'
                    ' filename=%s_daily_average_energy.xls') % (account)
            return buf.getvalue()

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def rsi(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        '''AJAX request handler for "Shared Rate Structure Items" grid.
        Performs all CRUD operations on the UPRS of the utility bill
        given by its MySQL id (and reebill_sequence and reebill_version if
        non-None). 'xaction' is one of the Ext-JS operation names "create",
        "read", "update", "destroy". If 'xaction' is not "read", 'rows' should
        contain data to create
        '''
        rows = kwargs.get('rows')
        with DBSession(self.state_db) as session:
            rate_structure = self.process.get_rs_doc(session, utilbill_id,
                    'uprs', reebill_sequence=reebill_sequence,
                    reebill_version=reebill_version)
            rates = rate_structure.rates

            if xaction == "read":
                #return self.dumps({'success': True, 'rows':rates})
                return json.dumps({'success': True, 'rows':[rsi.to_dict()
                        for rsi in rates]})

            # only xaction "read" is allowed when reebill_sequence/version
            # arguments are given
            if (reebill_sequence, reebill_version) != (None, None):
                raise IssuedBillError('Issued reebills cannot be modified')

            rows = json.loads(rows)

            if 'total' in rows:
                del rows['total']

            if xaction == "update":
                # single edit comes in not in a list
                if type(rows) is dict: rows = [rows]


                # process list of edits
                for row in rows:
                    # extract "id" field from the JSON because all remaining
                    # key-value pairs are fields to update in the RSI
                    id = row.pop('id')

                    # Fix boolean values that are interpreted as strings
                    for key in ('shared', 'has_charge'):
                        if row[key] in ("false", False):
                            row[key] = False
                        else:
                            row[key] = True

                    # "id" field contains the old rsi_binding, which is used
                    # to look up the RSI; "rsi_binding" field contains the
                    # new one that will replace it (if there is one)
                    rsi = rate_structure.get_rsi(id)
                    for key, value in row.iteritems():
                        assert hasattr(rsi, key)
                        setattr(rsi, key, value)

                    # re-add "id" field which was removed above (using new
                    # rsi_binding)
                    # TODO this is ugly; find a better way
                    row['id'] = rsi.rsi_binding

            if xaction == "create":
                new_rsi = rate_structure.add_rsi()

            if xaction == "destroy":
                if type(rows) is unicode: rows = [rows]
                # process list of removals
                for row in rows:
                    rsi = rate_structure.get_rsi(row)
                    rates.remove(rsi)

            rate_structure.save()
            rows = [rsi.to_dict() for rsi in rate_structure.rates]
            return json.dumps({'success': True, 'rows':rows, 'total':len(rows) })

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def payment(self, xaction, account, **kwargs):
        with DBSession(self.state_db) as session:
            if xaction == "read":
                payments = self.state_db.payments(session, account)
                return self.dumps({'success': True,
                    'rows': [payment.to_dict() for payment in payments]})
            elif xaction == "update":
                rows = json.loads(kwargs["rows"])
                # single edit comes in not in a list
                if type(rows) is dict: rows = [rows]
                # process list of edits
                for row in rows:
                    self.state_db.update_payment(
                        session,
                        row['id'],
                        row['date_applied'],
                        row['description'],
                        row['credit'],
                    )
                return self.dumps({'success':True})
            elif xaction == "create":
                # date applied is today by default (can be edited later)
                today = datetime.utcnow().date()
                new_payment = self.state_db.create_payment(session, account,
                        today, "New Entry", 0)
                # Payment object lacks "id" until row is inserted in database
                session.flush()
                return self.dumps({'success':True, 'rows':[new_payment.to_dict()]})
            elif xaction == "destroy":
                rows = json.loads(kwargs["rows"])
                # single delete comes in not in a list
                if type(rows) is int: rows = [rows]
                for oid in rows:
                    self.state_db.delete_payment(session, oid)
                return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def reebill(self, xaction, start, limit, account, sort = u'sequence',
            dir=u'DESC', **kwargs):
        '''Handles AJAX requests for reebill grid data.'''
        start, limit = int(start), int(limit)
        with DBSession(self.state_db) as session:
            if xaction == "read":
                # this is inefficient but length is always <= 120 rows
                rows = sorted(self.process.get_reebill_metadata_json(session,
                        account), key=itemgetter(sort))
                if dir.lower() == 'desc':
                    rows.reverse()

                # "limit" means number of rows to return, so the real limit is
                # start + limit
                result = rows[start : start + limit]
                return self.dumps({'success': True, 'rows': result,
                        'results':len(rows)})

            elif xaction == "update":
                return self.dumps({'success':False})

            elif xaction == "create":
                return self.dumps({'success':False})

            elif xaction == "destroy":
                # we do not delete reebills through reebillStore's remove()
                # method, because Ext believes in a 1-1 mapping between grid
                # rows and things, but "deleting" a reebill does not
                # necessarily mean that a row disappears from the grid.
                raise ValueError("Use delete_reebill instead!")

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def issuable(self, xaction, **kwargs):
        '''Return a list of the issuable reebills'''
        with DBSession(self.state_db) as session:
            if xaction == 'read':
                start = int(kwargs['start'])
                limit = int(kwargs['limit'])
                sort = kwargs['sort']
                direction = kwargs['dir']

                try:
                    allowable_diff = cherrypy.session['user'].preferences['difference_threshold']
                except:
                    allowable_diff = UserDAO.default_user.preferences['difference_threshold']

                issuable_reebills = self.process.get_issuable_reebills_dict(session)
                for reebill_info in issuable_reebills:
                    reebill_info['id'] = reebill_info['account'],
                    reebill_info['difference'] = abs(reebill_info['reebill_total']-reebill_info['util_total'])
                    reebill_info['matching'] = reebill_info['difference'] < allowable_diff

                issuable_reebills.sort(key=lambda d: d[sort], reverse = (direction == 'DESC'))
                issuable_reebills.sort(key=lambda d: d['matching'], reverse = True)
                return self.dumps({'success': True,
                                   'rows': issuable_reebills[start:start+limit],
                                   'total': len(issuable_reebills)})
            elif xaction == 'update':
                row = json.loads(kwargs["rows"])
                self.process.update_bill_email_recipient(session,
                                                         row['account'],
                                                         row['sequence'],
                                                         row['mailto'])
                return self.dumps({'success':True})
            
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def delete_reebill(self, account, sequences, **kwargs):
        '''Delete the unissued version of each reebill given, assuming that one
        exists.'''
        if type(sequences) is list:
            sequences = map(int, sequences)
        else:
            sequences = [int(sequences)]
        with DBSession(self.state_db) as session:
            for sequence in sequences:
                deleted_version = self.process.delete_reebill(session,
                        account, sequence)
            # deletions must all have succeeded, so journal them
            for sequence in sequences:
                journal.ReeBillDeletedEvent.save_instance(cherrypy.session['user'],
                        account, sequence, deleted_version)

        return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def new_reebill_version(self, account, sequence, **args):
        '''Creates a new version of the given reebill (only one bill, not all
        successors as in original design).'''
        sequence = int(sequence)
        with DBSession(self.state_db) as session:
            # Process will complain if new version is not issued
            new_reebill = self.process.new_version(session, account, sequence)

            journal.NewReebillVersionEvent.save_instance(cherrypy.session['user'],
                    account, new_reebill.sequence, new_reebill.version)
            # NOTE ReebillBoundEvent is no longer saved in the journal because
            # new energy data are not retrieved unless the user explicitly
            # chooses to do it by clicking "Bind RE&E"

            # client doesn't do anything with the result (yet)
            return self.dumps({'success': True, 'sequences':
                    [new_reebill.sequence]})

    ################
    # Handle addresses

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def account_info(self, account, sequence, **args):
        '''Handles AJAX request for "Sequential Account Information form.
        '''
        with DBSession(self.state_db) as session:
            sequence = int(sequence)
            reebill = self.state_db.get_reebill(session, account, sequence)
            reebill_document = self.reebill_dao.load_reebill(account, sequence)

            def format_address(address):
                # TODO: 64765002
                # This function exists multiple times in here and in exporter
                # code. Time to move it somewhere else!
                return {
                'addressee': address['addressee'] if 'addressee' in address else '',
                'street': address['street'] if 'street' in address else '',
                'city': address['city'] if 'city' in address else '',
                'state': address['state'] if 'state' in address else '',
                'postal_code': address['postal_code'] if 'postal_code' in address else '',
            }

            account_info = {'success': True,
                    'billing_address': format_address(reebill_document
                    .billing_address),
                    'service_address': format_address(reebill_document.service_address),
                    'discount_rate': reebill.discount_rate}

            try:
                account_info['late_charge_rate'] = reebill.late_charge_rate
            except KeyError:
                # ignore late charge rate when absent
                pass

            return self.dumps(account_info)


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def set_account_info(self, account, sequence,
        discount_rate, late_charge_rate,
        ba_addressee, ba_street, ba_city, ba_state, ba_postal_code,
        sa_addressee, sa_street, sa_city, sa_state, sa_postal_code,
        **kwargs):
        '''Update account information in "Sequential Account Information" form.
        '''
        sequence = int(sequence)
        discount_rate = float(discount_rate)
        late_charge_rate = float(late_charge_rate)

        # rely on client-side validation
        assert discount_rate >= 0 and discount_rate <= 1
        assert late_charge_rate >= 0 and late_charge_rate <= 1

        with DBSession(self.state_db) as session:
            self.process.update_sequential_account_info(session, account,
                    sequence, discount_rate=discount_rate,
                    late_charge_rate=late_charge_rate,
                    ba_addressee=ba_addressee, ba_street=ba_street,
                    ba_city=ba_city, ba_state=ba_state,
                    ba_postal_code=ba_postal_code,
                    sa_addressee=sa_addressee, sa_street=sa_street,
                    sa_city=sa_city, sa_state=sa_state,
                    sa_postal_code=sa_postal_code)
            return self.dumps({'success': True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def get_reebill_services(self, account, sequence, **args):
        '''Returns the utililty services associated with the reebill given by
        account and sequence, and a list of which services are suspended
        (usually empty). Used to show service suspension checkboxes in
        "Sequential Account Information".'''
        sequence = int(sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence)
        if reebill is None:
            raise Exception('No reebill found for %s-%s' % (account, sequence))
        # TODO: 40161259 must return success field
        return self.dumps({
            'services': reebill.services,
            'suspended_services': reebill.suspended_services
        })

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def actualCharges(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        with DBSession(self.state_db) as session:
            charges_json = self.process.get_utilbill_charges_json(session,
                    utilbill_id, reebill_sequence=reebill_sequence,
                    reebill_version=reebill_version)
            if xaction == "read":
                return self.dumps({'success': True, 'rows': charges_json,
                        'total':len(charges_json)})

            # only xaction "read" is allowed when reebill_sequence/version
            # arguments are given
            if (reebill_sequence, reebill_version) != (None, None):
                raise IssuedBillError('Issued reebills cannot be modified')

            if xaction == "update":
                row = json.loads(kwargs["rows"])[0]
                # single edit comes in a list containing a dict;
                # multiple would be in list of
                # dicts but that should be impossible
                assert isinstance(row, dict)

                rsi_binding = row.pop('id')
                self.process.update_charge(session, utilbill_id, rsi_binding,
                        row)

            if xaction == "create":
                row = json.loads(kwargs["rows"])[0]
                assert isinstance(row, dict)
                group_name = row['group']
                self.process.add_charge(session, utilbill_id, group_name)

            if xaction == "destroy":
                rsi_binding = json.loads(kwargs["rows"])[0]
                self.process.delete_charge(session, utilbill_id, rsi_binding)

            charges_json = self.process.get_utilbill_charges_json(session,
                    utilbill_id)
            return self.dumps({'success': True, 'rows': charges_json,
                                'total':len(charges_json)})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def hypotheticalCharges(self, xaction, service, account, sequence, **kwargs):
        service = service.lower()
        sequence = int(sequence)

        if not xaction == "read":
            raise NotImplementedError('Cannot create, edit or destroy charges'+ \
                                      ' from this grid.')

        with DBSession(self.state_db) as session:
                charges=self.process.get_hypothetical_matched_charges(
                    session, account, sequence)
                return self.dumps({'success': True, 'rows': charges,
                                   'total':len(charges)})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def utilbill_registers(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        '''Handles AJAX requests to read and write data for the "Utility Bill
        Registers" grid in the "Meters and Registers" tab. 'account',
        'sequence' identify the reebill whose utility bill is being edited.
        Ext-JS uses 'xaction' to specify which CRUD operation is being
        performed (create, read, update, destroy).'''
        # rows in the grid are identified by an "id" consisting of the utility
        # bill service name, meter id, and register id separated by '/'. thus
        # '/' is forbidden in service names, meter ids, and register ids.
        def validate_id_components(*components):
            if any('/' in c for c in components):
                raise ValueError(('Service names and meter/register ids must '
                        'not contain "/"'))

        if xaction not in ('create', 'read', 'update', 'destroy'):
            raise ValueError('Unknown xaction "%s"' % xaction)

        with DBSession(self.state_db) as session:
            utilbill_doc = self.process.get_utilbill_doc(session, utilbill_id,
                    reebill_sequence=reebill_sequence,
                    reebill_version=reebill_version)

            if xaction == 'read':
                # get dictionaries describing all registers in all utility bills
                registers_json = mongo.get_all_actual_registers_json(utilbill_doc)

                result = {'success': True, "rows": registers_json,
                        'total': len(registers_json)}

                # client sends "current_selected_id" to identify which row is
                # selected in the grid; if this key is present, server must also
                # include "current_selected_id" in the response to indicate that
                # the same row is still selected
                if 'current_selected_id' in kwargs:
                    result['current_selected_id'] = kwargs['current_selected_id']

                return self.dumps(result)

            # only xaction "read" is allowed when reebill_sequence/version
            # arguments are given
            if (reebill_sequence, reebill_version) != (None, None):
                raise IssuedBillError('Issued reebills cannot be modified')

            # the "rows" argument is only given when xaction is "create", "update",
            # or "destroy". it's a list if there are multiple rows (though in
            # practice there is only one because only one row of the grid can be
            # created/edited/deleted at a time).
            rows = json.loads(kwargs['rows'])
            if not isinstance(rows, list):
                rows = [rows]

            if xaction == 'create':
                for row in rows:
                    validate_id_components(row.get('meter_id',''),
                            row.get('register_id',''))

                    # create the new register (ignoring return value)
                    mongo.new_register(utilbill_doc, row.get('meter_id', None),
                            row.get('register_id', None))
                   
                # get dictionaries describing all registers in all utility bills
                registers_json = mongo.get_all_actual_registers_json(utilbill_doc)

                result = {'success': True, "rows": registers_json,
                        'total': len(registers_json)}

                # client sends "current_selected_id" to identify which row is
                # selected in the grid; if this key is present, server must also
                # include "current_selected_id" in the response to indicate that
                # the same row is still selected
                if 'current_selected_id' in kwargs:
                    result['current_selected_id'] = kwargs['current_selected_id']

            if xaction == 'update':
                # for update, client sends a JSON representation of the grid rows,
                # containing only the fields to be updated, plus an "id" field that
                # contains the service, meter id, and register id BEFORE the user
                # edited them.

                result = {'success': True}

                for row in rows:
                    # extract keys needed to identify the register being updated
                    # from the "id" field sent by the client
                    _, orig_meter_id, orig_reg_id = row['id'].split('/')

                    validate_id_components(row.get('meter_id',''),
                            row.get('register_id',''))

                    # all arguments should be strings, except "quantity",
                    # which should be a number
                    if 'quantity' in row:
                        assert isinstance(row['quantity'], (float, int))

                    # modify the register using every field in 'row' except "id"
                    # (getting back values necessary to tell the client which row
                    # should be selected)
                    del row['id']
                    new_meter_id, new_reg_id = mongo.update_register(
                            utilbill_doc, orig_meter_id, orig_reg_id, **row)

                    # if this row was selected before, tell the client it should
                    # still be selected, specifying the row by its new "id"
                    if kwargs.get('current_selected_id') == '%s/%s/%s' % (
                            utilbill_id, orig_meter_id, orig_reg_id):
                        result['current_selected_id'] = '%s/%s/%s' % (utilbill_id,
                                new_meter_id, new_reg_id)

                registers_json = mongo.get_all_actual_registers_json(utilbill_doc)
                result.update({
                    'rows': registers_json,
                    'total': len(registers_json)
                })

            if xaction == 'destroy':
                assert len(rows) == 1
                id_of_row_to_delete = rows[0]

                # extract keys needed to identify the register being updated
                _, orig_meter_id, orig_reg_id = id_of_row_to_delete\
                        .split('/')
                mongo.delete_register(utilbill_doc, orig_meter_id, orig_reg_id)

                # NOTE there is no "current_selected_id" because the formerly
                # selected row was deleted
                registers_json = mongo.get_all_actual_registers_json(
                        utilbill_doc)
                result = {'success': True, "rows": registers_json,
                        'total': len(registers_json)}

            self.reebill_dao.save_utilbill(utilbill_doc)
            return self.dumps(result)

    #
    ################

    ################
    # Handle utility bill upload

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def upload_utility_bill(self, account, service, begin_date, end_date,
            total_charges, file_to_upload, **args):
        '''Handles AJAX request to create a new utility bill from the "Upload
        Utility Bill" form. If 'file_to_upload' None, the utility bill state
        will be 'SkylineEstimated'; otherwise it will be 'Complete'. Currently,
        there is no way to specify a 'UtilityEstimated' state in the UI.'''
        with DBSession(self.state_db) as session:
            # pre-process parameters
            service = service.lower()
            total_charges_as_float = float(total_charges)
            begin_date_as_date = datetime.strptime(begin_date, '%Y-%m-%d').date()
            end_date_as_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            UtilBill.validate_utilbill_period(begin_date_as_date,
                    end_date_as_date)

            # NOTE 'file_to_upload.file' is always a CherryPy object; if no
            # file was specified, 'file_to_upload.file' will be None

            self.process.upload_utility_bill(session, account, service,
                    begin_date_as_date,
                    end_date_as_date, file_to_upload.file,
                    file_to_upload.filename if file_to_upload else None,
                    total=total_charges_as_float,
                    state=UtilBill.Complete if file_to_upload.file else \
                            UtilBill.SkylineEstimated,
                    # determine these values from previous bills because
                    # user does not want to specify them explicitly
                    utility=None,
                    rate_class=None)

            return self.dumps({'success': True})

    #
    ################

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def journal(self, xaction, account, **kwargs):
        if xaction == "read":
            journal_entries = self.journal_dao.load_entries(account)
            return self.dumps({'success': True, 'rows':journal_entries})

        # TODO: 20493983 eventually allow admin user to override and edit
        return self.dumps({'success':False, 'errors':{'reason':'Not supported'}})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def save_journal_entry(self, account, sequence, entry, **kwargs):
        '''Saves the text 'entry' as a Note in the journal for 'account'.
        Sequence is optional in case the entry applies to the account as whole,
        but should be provided if it's associated with a particular reebill.'''
        if sequence:
            sequence = int(sequence)
            journal.Note.save_instance(cherrypy.session['user'], account,
                    entry, sequence=sequence)
        else:
            journal.Note.save_instance(cherrypy.session['user'], account,
                    entry)
        return self.dumps({'success':True})

 
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def last_utilbill_end_date(self, account, **kwargs):
        '''Returns date of last utilbill.'''
        with DBSession(self.state_db) as session:
            the_date = self.state_db.last_utilbill_end_date(session, account)
            # the_date will be None (converted to JSON as null) if there are no
            # utilbills for this account
            the_datetime = None
            if the_date is not None:
                # TODO: a pure date gets converted to JSON as a datetime with
                # midnight as its time, causing problems in the browser
                # (https://www.pivotaltracker.com/story/show/23569087). temporary
                # fix is to make it a datetime with a later time.
                the_datetime = datetime(the_date.year, the_date.month, the_date.day, 23)
            return self.dumps({'success':True, 'date': the_datetime})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    # TODO: 25650643 explicit params - security risk and other 
    def utilbill_grid(self, xaction, **kwargs):
        '''Handles AJAX requests to read and write data for the grid of utility
        bills. Ext-JS provides the 'xaction' parameter, which is "read" when it
        wants to read data and "update" when a cell in the grid was edited.'''
        with DBSession(self.state_db) as session:
            if xaction == 'read':
                account = kwargs['account']
                start, limit = int(kwargs['start']), int(kwargs['limit'])
                rows, total_count = self.process.get_all_utilbills_json(
                        session, account, start, limit)
                return self.dumps({'success': True, 'rows':rows,
                        'results': total_count})

            elif xaction == 'update':
                # ext sends a JSON object if there is one row, a list of
                # objects if there are more than one. but in this case only one
                # row can be edited at a time
                row = ju.loads(kwargs['rows'])

                # convert JSON key/value pairs into arguments for
                # Process.update_utilbill_metadata below
                update_args = {}
                for k, v in row.iteritems():
                    # NOTE Ext-JS uses '' (empty string) to represent not
                    # changing a value. yes, that means you can never set a
                    # value to ''.
                    if v == '':
                        pass
                    elif k in ('period_start', 'period_end'):
                        update_args[k] = datetime.strptime(v,
                                ISO_8601_DATETIME_WITHOUT_ZONE).date()
                    elif k == 'service':
                        update_args[k] = v.lower()
                    elif k != 'id':
                        update_args[k] = v

                self.process.update_utilbill_metadata(session, row['id'],
                        **update_args)

                return self.dumps({'success': True})

            elif xaction == 'create':
                # creation happens via upload_utility_bill
                # TODO move here?
                raise ValueError('utilbill_grid does not accept xaction "create"')
            elif xaction == 'destroy':
                # "rows" is either a single id or a list of ids
                account = kwargs["account"]
                rows = ju.loads(kwargs['rows'])
                if type(rows) is int:
                    ids = [rows]
                else:
                    ids = rows

                # delete each utility bill, and log the deletion in the journal
                # with the path where the utility bill file was moved
                for utilbill_id in ids:
                    utilbill, deleted_path = self.process\
                            .delete_utility_bill_by_id(session, utilbill_id)
                    journal.UtilBillDeletedEvent.save_instance(
                            cherrypy.session['user'], account,
                            utilbill.period_start, utilbill.period_end,
                            utilbill.service, deleted_path)
                return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getUtilBillImage(self, utilbill_id):
        # TODO: put url here, instead of in billentry.js?
        resolution = cherrypy.session['user'].preferences['bill_image_resolution']
        with DBSession(self.state_db) as session:
            result = self.process.get_utilbill_image_path(session, utilbill_id,
                                                          resolution)
        return self.dumps({'success':True, 'imageName':result})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getReeBillImage(self, account, sequence, resolution, **args):
        if not self.config.getboolean('billimages', 'show_reebill_images'):
            return self.dumps({'success': False, 'errors': {'reason':
                    'Reebill images have been turned off.'}})
        resolution = cherrypy.session['user'].preferences['bill_image_resolution']
        result = self.billUpload.getReeBillImagePath(account, sequence,
                resolution)
        return self.dumps({'success':True, 'imageName':result})
    
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getBillImageResolution(self, **kwargs):
        resolution = cherrypy.session['user'].preferences['bill_image_resolution']
        return self.dumps({'success':True, 'resolution': resolution})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def setBillImageResolution(self, resolution, **kwargs):
        cherrypy.session['user'].preferences['bill_image_resolution'] = int(resolution)
        self.user_dao.save_user(cherrypy.session['user'])
        return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getDifferenceThreshold(self, **kwargs):
        threshold = cherrypy.session['user'].preferences['difference_threshold']
        return self.dumps({'success':True, 'threshold': threshold})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def setDifferenceThreshold(self, threshold, **kwargs):
        threshold=float(threshold)
        if not threshold or threshold <= 0:
            return self.dumps({'success':False, 'errors':"Threshold of %s is not valid." % str(threshold)})
        cherrypy.session['user'].preferences['difference_threshold'] = threshold
        self.user_dao.save_user(cherrypy.session['user'])
        return self.dumps({'success':True})
    
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getFilterPreference(self, **kwargs):
        filtername = cherrypy.session['user'].preferences.get('filtername', '')
        return self.dumps({'success':True, 'filtername': filtername})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def setFilterPreference(self, filtername, **kwargs):
        if filtername is None:
            return self.dumps({'success':False, 'errors':"Filter '%s' is not valid." % str(filtername)})
        cherrypy.session['user'].preferences['filtername'] = filtername
        self.user_dao.save_user(cherrypy.session['user'])
        return self.dumps({'success':True})

# TODO: place instantiation in main, so this module can be loaded without btb being instantiated
bridge = BillToolBridge()

if __name__ == '__main__':
    # configure CherryPy
    local_conf = {
        '/' : {
            'tools.staticdir.root' :os.path.dirname(os.path.abspath(__file__)), 
            'tools.staticdir.dir' : 'ui',
            'tools.staticdir.on' : True,
            'tools.expires.secs': 0,
            'tools.response_headers.on': True,
            'tools.sessions.on': True,
            'tools.sessions.timeout': 240
        },
    }
    cherrypy.config.update({
        'server.socket_host': bridge.config.get("http", "socket_host"),
        'server.socket_port': int(bridge.config.get("http", "socket_port")),
    })
    #cherrypy.quickstart(bridge, "/", config = local_conf)
    cherrypy.quickstart(bridge,
            # cherrypy doc refers to this as 'script_name': "a string
            # containing the 'mount point' of the application'", i.e. the URL
            # corresponding to the method 'index' above and prefixed to the
            # URLs corresponding to the other methods
            # http://docs.cherrypy.org/stable/refman/cherrypy.html?highlight=quickstart#cherrypy.quickstart
            "/",
            config = local_conf)
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

    application = cherrypy.Application(bridge, script_name=None, config=None)
