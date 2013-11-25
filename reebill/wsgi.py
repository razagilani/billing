'''
File: wsgi.py
'''
import sys
import os
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
from skyliner.skymap.monguru import Monguru
from skyliner.splinter import Splinter
#TODO don't rely on test code, if we are, it isn't test code
from skyliner import mock_skyliner
from billing.util import json_util as ju, dateutils, nexus_util as nu
from billing.util.dateutils import ISO_8601_DATE, ISO_8601_DATETIME_WITHOUT_ZONE
from billing.util.nexus_util import NexusUtil
from billing.util.dictutils import deep_map
from billing.processing import mongo, billupload, excel_export
from billing.util import monthmath
from billing.processing import process, state, fetch_bill_data as fbd, rate_structure2 as rs
from billing.processing.state import UtilBill, Customer
from billing.processing.billupload import BillUpload
from billing.processing import journal, bill_mailer
from billing.processing import render
from billing.processing.users import UserDAO, User
from billing.processing import calendar_reports
from billing.processing.estimated_revenue import EstimatedRevenue
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import Unauthenticated, IssuedBillError, NoSuchBillException



# collection names: all collections are now hard-coded. maybe this should go in
# some kind of documentation when we have documentation...
# rate structures: 'ratestructure'
# reebills: 'reebill'
# users: 'users'

import pprint
sys.stdout = sys.stderr
# 29926885 output environment configs to debug virtual env
pprint.pprint(os.environ)
pprint.pprint(sys.path)
pprint.pprint(sys.prefix)
pp = pprint.PrettyPrinter(indent=4)

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

        # create one Process object to use for all related bill processing
        # TODO it's theoretically bad to hard-code these, but all skyliner
        # configuration is hard-coded right now anyway
        if self.config.getboolean('runtime', 'integrate_skyline_backend') is True:
            self.process = process.Process(self.state_db, self.reebill_dao,
                    self.ratestructure_dao, self.billUpload, self.nexus_util,
                    self.splinter, logger=self.logger)
        else:
            self.process = process.Process(self.state_db, self.reebill_dao,
                    self.ratestructure_dao, self.billUpload, None, None)

        # create a ReebillRenderer
        self.renderer = render.ReebillRenderer(
                dict(self.config.items('reebillrendering')), self.state_db,
                self.reebill_dao, self.logger)

        # configure mailer
        bill_mailer.config = dict(self.config.items("mailer"))

        # determine whether authentication is on or off
        self.authentication_on = self.config.getboolean('authentication', 'authenticate')

        # TODO: allow the log to be viewed in the UI
        self.reconciliation_log_dir = self.config.get('reebillreconciliation', 'log_directory')
        self.reconciliation_report_dir = self.config.get('reebillreconciliation', 'report_directory')

        # TODO: allow the log to be viewed in the UI
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

    # TODO 30164355 DBSession should log rollbacks the way this did
    #def rollback_session(self, session):
    #    try:
    #        if session is not None: session.rollback()
    #    except:
    #        try:
    #            self.logger.error('Could not rollback session:\n%s' % traceback.format_exc())
    #        except:
    #            print >> sys.stderr, ('Logger not functioning\nCould not '
    #                    'roll back session:\n%s') % traceback.format_exc()

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

        # 1st transaction: roll
        with DBSession(self.state_db) as session:
            last_seq = self.state_db.last_sequence(session, account)
            if last_seq == 0:
                utilbill = session.query(UtilBill).join(Customer)\
                        .filter(UtilBill.customer_id == Customer.id)\
                        .filter_by(account=account)\
                        .filter(UtilBill.period_start >= start_date)\
                        .order_by(UtilBill.period_start).first()
                if utilbill is None:
                    raise ValueError("No utility bill found starting on/after %s" %
                            start_date)
                self.process.create_first_reebill(session, utilbill)
            else:
                self.process.create_next_reebill(session, account)
            new_reebill_doc = self.reebill_dao.load_reebill(account, last_seq +
                    1)

            journal.ReeBillRolledEvent.save_instance(cherrypy.session['user'],
                    account, last_seq + 1)
            # Process.roll includes attachment
            # TODO "attached" is no longer a useful event;
            # see https://www.pivotaltracker.com/story/show/55044870
            journal.ReeBillAttachedEvent.save_instance(cherrypy.session['user'],
                account, last_seq + 1, new_reebill_doc.version)

        # 2nd transaction: bind and compute. if one of these fails, don't undo
        # the changes to MySQL above, leaving a Mongo reebill document without
        # a corresponding MySQL row; only undo the changes related to binding
        # and computing (currently there are none).
        with DBSession(self.state_db) as session:
            if self.config.getboolean('runtime', 'integrate_skyline_backend') is True:
                fbd.fetch_oltp_data(self.splinter, self.nexus_util.olap_id(account),
                    new_reebill_doc, use_olap=True, verbose=True)
            self.reebill_dao.save_reebill(new_reebill_doc)
            journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, new_reebill_doc.sequence, new_reebill_doc.version)
            
            self.process.compute_reebill(session, new_reebill_doc)
            self.reebill_dao.save_reebill(new_reebill_doc)

            return self.dumps({'success': True})

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
        reebill = self.reebill_dao.load_reebill(account, sequence)

        if self.config.getboolean('runtime', 'integrate_skyline_backend') is True:
            fbd.fetch_oltp_data(self.splinter,
                    self.nexus_util.olap_id(account), reebill, use_olap=True,
                    verbose=True)
        self.reebill_dao.save_reebill(reebill)
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
        reebill = self.reebill_dao.load_reebill(account, sequence)

        # convert column letters into 0-based indices
        if not re.match('[A-Za-z]', timestamp_column):
            raise ValueError('Timestamp column must be a letter')
        if not re.match('[A-Za-z]', energy_column):
            raise ValueError('Energy column must be a letter')
        timestamp_column = ord(timestamp_column.lower()) - ord('a')
        energy_column = ord(energy_column.lower()) - ord('a')

        # extract data from the file (assuming the format of AtSite's
        # example files)
        fbd.fetch_interval_meter_data(reebill, csv_file.file,
                meter_identifier=register_identifier,
                timestamp_column=timestamp_column,
                energy_column=energy_column,
                timestamp_format=timestamp_format, energy_unit=energy_unit)

        self.reebill_dao.save_reebill(reebill)
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
            # use version 0 of the predecessor to show the real account
            # history (prior balance, payment received, balance forward)
            mongo_reebill = self.reebill_dao.load_reebill(account,
                    sequence, version='max')
            self.process.compute_reebill(session, mongo_reebill)
            self.reebill_dao.save_reebill(mongo_reebill)
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
    def refresh_charges(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            self.process.refresh_charges(session, utilbill_id)
            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def regenerate_uprs(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            self.process.regenerate_uprs(session, utilbill_id)
            # NOTE utility bill is not automatically computed after rate
            # structure is changed. nor are charges updated to match.
            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def regenerate_cprs(self, utilbill_id, **args):
        with DBSession(self.state_db) as session:
            self.process.regenerate_cprs(session, utilbill_id)
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

    def issue_reebills(self, session, account, sequences,
            apply_corrections=True):
        '''Issues all unissued bills given by account and sequences. These must
        be version 0, not corrections. If apply_corrections is True, all
        unissued corrections will be applied to the earliest unissued bill in
        sequences.'''
        # attach utility bills to all unissued bills
        #for unissued_sequence in sequences:
        #    self.attach_utility_bills(session, account, unissued_sequence)

        if apply_corrections:
            # get unissued corrections for this account
            unissued_correction_sequences = self.process\
                    .get_unissued_correction_sequences(session, account)

            # apply all corrections to earliest un-issued bill, then issue
            # that and all other un-issued bills
            self.process.issue_corrections(session, account, sequences[0])

        # compute and issue all unissued reebills
        for unissued_sequence in sequences:
            reebill = self.reebill_dao.load_reebill(account, unissued_sequence)
            self.process.compute_reebill(session, reebill)
            self.process.issue(session, account, unissued_sequence)

        # journal attaching of utility bills
        for unissued_sequence in sequences:
            journal.ReeBillAttachedEvent.save_instance(cherrypy.session['user'],
                    account, unissued_sequence, self.state_db.max_version(session,
                    account, unissued_sequence))
        # journal issuing of corrections (applied to the earliest unissued
        # bill), if any
        if apply_corrections:
            for correction_sequence in unissued_correction_sequences:
                journal.ReeBillIssuedEvent.save_instance(
                        cherrypy.session['user'],
                        account, sequences[0],
                        self.state_db.max_version(session, account,
                        correction_sequence),
                        applied_sequence=sequences[0])
        # journal issuing of all unissued bills
        for unissued_sequence in sequences:
            journal.ReeBillIssuedEvent.save_instance(cherrypy.session['user'],
                    account, unissued_sequence, 0)

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def issue_and_mail(self, account, sequence, apply_corrections, **kwargs):
        sequence = int(sequence)
        apply_corrections = (apply_corrections == 'true')
        with DBSession(self.state_db) as session:
            mongo_reebill = self.reebill_dao.load_reebill(account, sequence)
            recipients = mongo_reebill.bill_recipients
            unissued_corrections = self.process.get_unissued_corrections(session, account)
            unissued_correction_sequences = [c[0] for c in unissued_corrections]
            unissued_correction_adjustment = sum(c[2] for c in unissued_corrections)
            if len(unissued_corrections) > 0 and not apply_corrections:
                    return self.dumps({'success': False,
                        'corrections': unissued_correction_sequences,
                        'adjustment': unissued_correction_adjustment })
            self.issue_reebills(session, account, [sequence], apply_corrections=apply_corrections)
            mongo_reebill = self.reebill_dao.load_reebill(account, sequence)
            self.renderer.render_max_version(session, account, sequence,
                                             self.config.get("billdb", "billpath")+ "%s" % account,
                                             "%.5d_%.4d.pdf" % (int(account), int(sequence)), True)
            bill_name = "%.5d_%.4d.pdf" % (int(account), int(sequence))
            merge_fields = {}
            merge_fields["street"] = mongo_reebill.service_address.get("street","")
            merge_fields["balance_due"] = mongo_reebill.balance_due.quantize(Decimal("0.00"))
            merge_fields["bill_dates"] = "%s" % (mongo_reebill.period_end)
            merge_fields["last_bill"] = bill_name
            print recipients,merge_fields, os.path.join(self.config.get('billdb', 'billpath'), account), [bill_name]
            bill_mailer.mail(recipients, merge_fields,
                    os.path.join(self.config.get("billdb", "billpath"),
                        account), [bill_name]);

            last_sequence = self.state_db.last_sequence(session, account)
            if sequence != last_sequence:
                next_bill = self.reebill_dao.load_reebill(account, sequence+1)
                next_bill.bill_recipients = recipients
                self.reebill_dao.save_reebill(next_bill)
            journal.ReeBillMailedEvent.save_instance(cherrypy.session['user'],
                                                     account, sequence, ", ".join(recipients))

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
            all_bills = [self.reebill_dao.load_reebill(account, sequence) for
                    sequence in sequences]

            # render all the bills
            # TODO 25560415 this fails if reebill rendering is turned
            # off--there should be a better error message
            for reebill in all_bills:
                self.renderer.render_max_version(session, reebill.account, reebill.sequence,
                    self.config.get("billdb", "billpath")+ "%s" % reebill.account,
                    "%.5d_%.4d.pdf" % (int(account), int(reebill.sequence)), True)

            # "the last element" (???)
            most_recent_bill = all_bills[-1]
            bill_file_names = ["%.5d_%.4d.pdf" % (int(account), int(sequence)) for sequence in sequences]
            bill_dates = ["%s" % (b.period_end) for b in all_bills]
            bill_dates = ", ".join(bill_dates)
            merge_fields = {}
            merge_fields["street"] = most_recent_bill.service_address.get("street","")
            merge_fields["balance_due"] = most_recent_bill.balance_due.quantize(Decimal("0.00"))
            merge_fields["bill_dates"] = bill_dates
            merge_fields["last_bill"] = bill_file_names[-1]
            print recipient_list, merge_fields,os.path.join(self.config.get("billdb", "billpath"),account), bill_file_names
            bill_mailer.mail(recipient_list, merge_fields,
                    os.path.join(self.config.get("billdb", "billpath"),
                        account), bill_file_names);

            # journal mailing of every bill
            for reebill in all_bills:
                journal.ReeBillMailedEvent.save_instance(cherrypy.session['user'],
                        reebill.account, reebill.sequence, recipients)

            return self.dumps({'success': True})

    def all_names_of_accounts(self, accounts):
        if self.config.getboolean('runtime', 'integrate_nexus') is False:
            return accounts

        # get list of customer name dictionaries sorted by their billing account
        all_accounts_all_names = self.nexus_util.all_names_for_accounts(accounts)
        name_dicts = sorted(all_accounts_all_names.iteritems())

        return name_dicts

    def full_names_of_accounts(self, accounts):
        '''Given a list of account numbers (as strings), returns a list
        containing the "full name" of each account, each of which is of the
        form "accountnumber - codename - casualname - primus" (sorted by
        account). Names that do not exist for a given account are skipped.'''
        if self.config.getboolean('runtime', 'integrate_nexus') is False:
            return accounts

        # get list of customer name dictionaries sorted by their billing account
        name_dicts = self.all_names_of_accounts(accounts)

        result = []
        with DBSession(self.state_db) as session:
            for account, all_names in name_dicts:
                res = account + ' - '
                # Only include the names that exist in Nexus
                names = [all_names[name] for name in
                         ('codename', 'casualname', 'primus')
                         if all_names.get(name)]
                res += '/'.join(names)
                if len(names) > 0:
                    res += ' - '
                #Append utility and rate_class from the last utilbill for the
                #account if one exists as per
                #https://www.pivotaltracker.com/story/show/58027082
                try:
                    last_utilbill = self.state_db.get_last_utilbill(
                        session, account)
                except NoSuchBillException:
                    #No utilbill found, just don't append utility info
                    pass
                else:
                    res += "%s: %s" %(last_utilbill.utility,
                                      last_utilbill.rate_class)
                result.append(res)
        return result

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def listAccounts(self, **kwargs):
        with DBSession(self.state_db) as session:
            accounts = []
            # eventually, this data will have to support pagination
            accounts = self.state_db.listAccounts(session)
            rows = [{'account': account, 'name': full_name} for account,
                    full_name in zip(accounts, self.full_names_of_accounts(accounts))]
            return self.dumps({'success': True, 'rows':rows})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def listSequences(self, account, **kwargs):
        '''Handles AJAX request to get reebill sequences for each account and
        whether each reebill has been committed.'''
        with DBSession(self.state_db) as session:
            sequences = []
            # eventually, this data will have to support pagination
            sequences = self.state_db.listSequences(session, account)
            # TODO "issued" is used for the value of "committed" here because
            # committed is ill-defined: currently StateDB.is_committed()
            # returns true iff the reebill has attached utilbills, which
            # doesn't make sense.
            # https://www.pivotaltracker.com/story/show/24382885
            rows = [{'sequence': sequence,
                'committed': self.state_db.is_issued(session, account, sequence)}
                for sequence in sequences]
            return self.dumps({'success': True, 'rows':rows})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def retrieve_account_status(self, start, limit, **kwargs):
        '''Handles AJAX request for "Account Processing Status" grid in
        "Accounts" tab.'''
        # this function is used below to format the "Utility Service Address"
        # grid column
        def format_service_address(utilbill_doc):
            try:
                return '%(street)s, %(city)s, %(state)s' % utilbill_doc['service_address']
            except KeyError as e:
                self.logger.error(('Utility bill service address for %s '
                        'from %s to %s lacks key "%s": %s') % (
                                utilbill_doc['account'], utilbill_doc['start'],
                                utilbill_doc['end'], e.message,
                                utilbill_doc['service_address']))
                return '?'

        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        with DBSession(self.state_db) as session:
            start, limit = int(start), int(limit)

            # result is a list of dictionaries of the form
            # {account: full name, dayssince: days}

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

            # pass the sort params if we want the db to do any sorting work
            statuses = self.state_db.retrieve_status_days_since(session, sortcol, sortdir)

            name_dicts = self.nexus_util.all_names_for_accounts([s.account for s in statuses])

            rows = []
            for status in statuses:
                last_reebill = self.state_db.get_last_reebill(session,
                        status.account, issued_only=True)
                if last_reebill is None:
                    utility_service_addresses = ''
                else:
                    # get service address from utility bill document, convert
                    # JSON to string using the function above
                    last_reebill_doc = self.reebill_dao.load_reebill(
                            last_reebill.customer.account,
                            last_reebill.sequence, last_reebill.version)
                    utility_service_addresses = format_service_address(
                            last_reebill_doc._utilbills[0])
                lastevent = self.journal_dao.last_event_summary(status.account)
                rows.append({
                    'account': status.account,
                    'codename': name_dicts[status.account]['codename'] if
                           'codename' in name_dicts[status.account] else '',
                    'casualname': name_dicts[status.account]['casualname'] if
                           'casualname' in name_dicts[status.account] else '',
                    'primusname': name_dicts[status.account]['primus'] if
                           'primus' in name_dicts[status.account] else '',
                    'utilityserviceaddress': utility_service_addresses,
                    'dayssince': status.dayssince,
                    'lastissuedate': last_reebill.issue_date if last_reebill \
                            else '',
                    'lastevent': lastevent,
                    'provisionable': False,
                })
            rows.sort(key=itemgetter(sortcol), reverse=sortreverse)

            ## also get customers from Nexus who don't exist in billing yet
            ## (do not sort these; just append them to the end)
            ## TODO: we DO want to sort these, but we just want to them to come
            ## after all the billing billing customers
            #non_billing_customers = self.nexus_util.get_non_billing_customers()
            #morerows = []
            #for customer in non_billing_customers:
                #morerows.append(dict([
                    ## we have the olap_id too but we don't show it
                    #('account', 'n/a'),
                    #('codename', customer['codename']),
                    #('casualname', customer['casualname']),
                    #('primusname', customer['primus']),
                    #('dayssince', 'n/a'),
                    #('lastevent', 'n/a'),
                    #('provisionable', True)
                #]))

            #if sortcol == 'account':
                #morerows.sort(key=lambda r: r['account'], reverse=sortreverse)
            #elif sortcol == 'codename':
                #morerows.sort(key=lambda r: r['codename'], reverse=sortreverse)
            #elif sortcol == 'casualname':
                #morerows.sort(key=lambda r: r['casualname'], reverse=sortreverse)
            #elif sortcol == 'primusname':
                #morerows.sort(key=lambda r: r['primusname'], reverse=sortreverse)
            #elif sortcol == 'dayssince':
                #morerows.sort(key=lambda r: r['dayssince'], reverse=sortreverse)
            #elif sortcol == 'lastevent':
                #morerows.sort(key=lambda r: r['lastevent'], reverse=sortreverse)

            #rows.extend(morerows)

            # count includes both billing and non-billing customers (front end
            # needs this for pagination)
            count = len(rows)

            # take slice for one page of the grid's data
            rows = rows[start:start+limit]

            cherrypy.session['user'].preferences['default_account_sort_field'] = sortcol
            cherrypy.session['user'].preferences['default_account_sort_direction'] = sortdir
            self.user_dao.save_user(cherrypy.session['user'])

            return self.dumps({'success': True, 'rows':rows, 'results':count})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def summary_ree_charges(self, start, limit, **args):
        '''Handles AJAX request for "Summary and Export" grid in "Accounts"
        tab.'''
        return self.dumps({'success': True})
        with DBSession(self.state_db) as session:
            accounts, totalCount = self.state_db.list_accounts(session,
                    int(start), int(limit))
            account_names = self.all_names_of_accounts([account for account in
                    accounts])
            rows = self.process.summary_ree_charges(session, accounts, account_names)
            for row in rows:
                outstanding_balance = self.process.get_outstanding_balance(session,
                        row['account'])
                days_since_due_date = None
                if outstanding_balance > 0:
                    payments = self.state_db.payments(session, row['account'])
                    if payments:
                        last_payment_date = payments[-1].date_received
                        reebills_since = self.reebill_dao.load_reebills_in_period(
                                row['account'], 'any', last_payment_date, date.today())
                        if reebills_since and reebills_since[0].due_date:
                            days_since_due_date = (date.today() -
                                    reebills_since[0].due_date).days

                row.update({'outstandingbalance': '$%.2f' % outstanding_balance,
                           'days_late': days_since_due_date})
            return self.dumps({'success': True, 'rows':rows,
                    'results':totalCount})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def reebill_details_xls(self, begin_date=None, end_date=None, **kwargs):
        #prep date strings from client
        make_date = lambda x: datetime.strptime(x, ISO_8601_DATE).date() if x else None
        begin_date = make_date(begin_date)
        end_date = make_date(end_date)
        #write out spreadsheet(s)
        with DBSession(self.state_db) as session:
            rows, total_count = self.process.reebill_report(session, begin_date,
                                                           end_date)

            buf = StringIO()

            import xlwt
            from xlwt import easyxf
            workbook = xlwt.Workbook(encoding='utf-8')
            sheet = workbook.add_sheet('All REE Charges')
            row_index = 0

            headings = ['Account','Sequence', 'Version',
                'Billing Addressee', 'Service Addressee',
                'Issue Date', 'Period Begin', 'Period End',
                'Hypothesized Charges', 'Actual Utility Charges',
                'RE&E Value',
                'Prior Balance',
                'Payment Applied',
                'Payment Date',
                'Payment Amount',
                'Adjustment',
                'Balance Forward',
                'RE&E Charges',
                'Late Charges',
                'Balance Due',
                '', # spacer
                'Savings',
                'Cumulative Savings',
                'RE&E Energy',
                'Average Rate per Unit RE&E',
                ]
            for i, heading in enumerate(headings):
                sheet.write(row_index, i, heading)
            row_index += 1

            for row in rows:
                ba = row['billing_address']
                bill_addr_str = "%s %s %s %s %s" % (
                    ba['addressee'] if 'addressee' in ba and ba['addressee'] is not None else "",
                    ba['street'] if 'street' in ba and ba['street'] is not None else "",
                    ba['city'] if 'city' in ba and ba['city'] is not None else "",
                    ba['state'] if 'state' in ba and ba['state'] is not None else "",
                    ba['postal_code'] if 'postal_code' in ba and ba['postal_code'] is not None else "",
                )
                sa = row['service_address']
                service_addr_str = "%s %s %s %s %s" % (
                    sa['addressee'] if 'addressee' in sa and sa['addressee'] is not None else "",
                    sa['street'] if 'street' in sa and sa['street'] is not None else "",
                    sa['city'] if 'city' in sa and sa['city'] is not None else "",
                    sa['state'] if 'state' in sa and sa['state'] is not None else "",
                    sa['postal_code'] if 'postal_code' in sa and sa['postal_code'] is not None else "",
                )

                actual_row = [row['account'], row['sequence'], row['version'],
                        bill_addr_str, service_addr_str,
                        row['issue_date'], row['period_begin'], row['period_end'],
                        row['hypothetical_charges'], row['actual_charges'],
                        row['ree_value'],
                        row['prior_balance'],
                        row['payment_applied'],
                        row['payment_date'],
                        row['payment_amount'],
                        row['total_adjustment'],
                        row['balance_forward'],
                        row['ree_charges'],
                        row['late_charges'],
                        row['balance_due'],
                        '', # spacer
                        row['savings'],
                        row['cumulative_savings'],
                        row['total_ree'],
                        row['average_rate_unit_ree'] ]
                for i, cell_text in enumerate(actual_row):
                    if isinstance(cell_text, date):
                        sheet.write(row_index, i, cell_text, easyxf(num_format_str='YYYY-MM-DD'))
                    else:
                        sheet.write(row_index, i, cell_text)
                row_index += 1

                cherrypy.response.headers['Content-Type'] = 'application/excel'
                cherrypy.response.headers['Content-Disposition'] = \
                        'attachment; filename=%s.xls' % \
                        datetime.now().strftime("%Y%m%d")

            workbook.save(buf)
            return buf.getvalue()

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def all_ree_charges_csv_altitude(self, **args):
        with DBSession(self.state_db) as session:
            rows, total_count = self.process.reebill_report_altitude(session)

            import csv
            import StringIO

            buf = StringIO.StringIO()

            writer = csv.writer(buf)

            writer.writerow(['Account-Sequence', 'Period End', 'RE&E Charges'])

            for row in rows:
                ba = row['billing_address']
                bill_addr_str = "%s %s %s %s %s" % (
                    ba['addressee'] if 'addressee' in ba and ba['addressee'] is not None else "",
                    ba['street'] if 'street' in ba and ba['street'] is not None else "",
                    ba['city'] if 'city' in ba and ba['city'] is not None else "",
                    ba['state'] if 'state' in ba and ba['state'] is not None else "",
                    ba['postal_code'] if 'postal_code' in ba and ba['postal_code'] is not None else "",
                )
                sa = row['service_address']
                service_addr_str = "%s %s %s %s %s" % (
                    sa['addressee'] if 'addressee' in sa and sa['addressee'] is not None else "",
                    sa['street'] if 'street' in sa and sa['street'] is not None else "",
                    sa['city'] if 'city' in sa and sa['city'] is not None else "",
                    sa['state'] if 'state' in sa and sa['state'] is not None else "",
                    sa['postal_code'] if 'postal_code' in sa and sa['postal_code'] is not None else "",
                )

                writer.writerow(["%s-%s" % (row['account'], row['sequence']), row['period_end'], row['ree_charges']])

                cherrypy.response.headers['Content-Type'] = 'text/csv'
                cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s.csv' % datetime.now().strftime("%Y%m%d")


            data = buf.getvalue()
            return data

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def discount_rates_csv_altitude(self, **args):
        with DBSession(self.state_db) as session:
            rows, total_count = self.process.reebill_report_altitude(session)

            import csv
            import StringIO

            buf = StringIO.StringIO()

            writer = csv.writer(buf)

            writer.writerow(['Account', 'Discount Rate'])

            for account, group in it.groupby(rows, lambda row: row['account']):
                for row in group:
                    if row['discount_rate']:
                        writer.writerow([account, row['discount_rate']])
                        break

            cherrypy.response.headers['Content-Type'] = 'text/csv'
            cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=reebill_discount_rates_%s.csv' % datetime.now().strftime("%Y%m%d")

            data = buf.getvalue()
            return data


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
            exporter.export(session, buf, account, start_date=start_date,
                            end_date=end_date)

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
    def uprsrsi(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        '''AJAX request handler for "Shared Rate Structure Items" grid.
        '''
        return self.rsi_crud(utilbill_id, 'uprs', xaction, reebill_sequence,
                reebill_version, kwargs.get('rows'))

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def cprsrsi(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        '''AJAX request handler for "Individual Rate Structure Items" grid.
        '''
        return self.rsi_crud(utilbill_id, 'cprs', xaction, reebill_sequence,
                reebill_version, kwargs.get('rows'))

    def rsi_crud(self, utilbill_id, rsi_type, xaction, reebill_sequence,
            reebill_version, rows):
        '''Performs all CRUD operations on the UPRS or CPRS of the utility bill
        given by its MySQL id (and reebill_sequence and reebill_version if
        non-None). 'xaction' is one of the Ext-JS operation names "create",
        "read", "update", "destroy". If 'xaction' is not "read", 'rows' should
        contain data to create/update/delete as a JSON string.
        '''
        with DBSession(self.state_db) as session:
            rate_structure = self.process.get_rs_doc(session, utilbill_id,
                    rsi_type, reebill_sequence=reebill_sequence,
                    reebill_version=reebill_version)
            rates = rate_structure["rates"]

            if xaction == "read":
                #return self.dumps({'success': True, 'rows':rates})
                return json.dumps({'success': True, 'rows':[rsi.to_dict()
                        for rsi in rate_structure.rates]})

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
                    # identify the RSI descriptor of the posted data
                    rsi_uuid = row['uuid']
                    # identify the rsi, and update it with posted data
                    matches = [rsi_match for rsi_match in it.ifilter(lambda x:
                            x.uuid==rsi_uuid, rates)]
                    # there should only be one match
                    if len(matches) == 0: raise Exception("Did not match an RSI UUID which should not be possible")
                    if len(matches) > 1:
                        raise Exception("Matched more than one RSI UUID which should not be possible")
                    rsi = matches[0]

                    for key, value in row.iteritems():
                        assert hasattr(rsi, key)
                        setattr(rsi, key, value)

            if xaction == "create":
                new_rsi = rs.RateStructureItem(
                    rsi_binding='Insert binding here',
                    description='Insert description here',
                    quantity='Insert quantity here',
                    quantity_units='',
                    rate='Insert rate here',
                    round_rule='',
                    uuid=str(UUID.uuid1()),
                )
                rates.append(new_rsi)
                rows = [new_rsi.to_dict()]

            if xaction == "destroy":
                uuids = rows
                if type(uuids) is unicode: uuids = [uuids]
                # process list of removals
                for rsi_uuid in uuids:
                    # identify the rsi
                    matches = [result for result in it.ifilter(lambda x:
                        x['uuid']==rsi_uuid, rates)]
                    if (len(matches) == 0):
                        raise Exception("Did not match an RSI UUID which should not be possible")
                    if (len(matches) > 1):
                        raise Exception("Matched more than one RSI UUID which should not be possible")
                    rsi = matches[0]
                    rates.remove(rsi)
                rows = []

            rate_structure.save()

            return self.dumps({'success':True, 'rows':rows})

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
                start = kwargs['start']
                limit = kwargs['limit']
                sort = kwargs['sort']
                direction = kwargs['dir']
                rows = []
                allowable_diff = 0
                try:
                    allowable_diff = cherrypy.session['user'].preferences['difference_threshold']
                except:
                    allowable_diff = UserDAO.default_user.preferences['difference_threshold']
                reebills, total = self.state_db.listAllIssuableReebillInfo(session=session)
                for reebill_info in reebills:
                    row_dict = {}
                    mongo_reebill = self.reebill_dao.load_reebill(reebill_info[0], reebill_info[1])
                    row_dict['id'] = reebill_info[0]
                    row_dict['account'] = reebill_info[0]
                    row_dict['sequence'] = reebill_info[1]
                    row_dict['util_total'] = reebill_info[2]
                    row_dict['mailto'] = ", ".join(mongo_reebill.bill_recipients)
                    row_dict['reebill_total'] = mongo_reebill.actual_total
                    try:
                        row_dict['difference'] = abs(row_dict['reebill_total']-row_dict['util_total'])
                    except ZeroDivisionError:
                        row_dict['difference'] = float('inf')
                    row_dict['matching'] = row_dict['difference'] < allowable_diff
                    rows.append(row_dict)
                rows.sort(key=lambda d: d[sort], reverse = (direction == 'DESC'))
                rows.sort(key=lambda d: d['matching'], reverse = True)
                return self.dumps({'success': True, 'rows':rows[int(start):int(start)+int(limit)], 'total':total})
            elif xaction == 'update':
                row = json.loads(kwargs["rows"])
                mongo_reebill = self.reebill_dao.load_reebill(row['account'],row['sequence'])
                mongo_reebill.bill_recipients = [r.strip() for r in row['mailto'].split(',')]
                self.reebill_dao.save_reebill(mongo_reebill)
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
                # previously, a reebill was only allowed to be deleted if
                # predecessor has an unissued version, so bills could only be
                # deleted in sequence order. as of 54786706, the lesson that
                # accounting history can never change has finally been learned;
                # since there is no dependency of one bill's accounting history
                # information on that of its predecessors, there is no need for
                # the rule that corrections must always be in a contiguous
                # block ending at the newest reebill that has ever been issued.
                #last_sequence = self.state_db.last_sequence(session, account)
                #max_version = self.state_db.max_version(session, account, sequence)
                #if not (max_version == 0 and sequence == last_sequence or max_version > 0 and
                        #(sequence == 1 or self.state_db.is_issued(session, account, sequence - 1))):
                    #raise ValueError(("Can't delete a reebill version whose "
                            #"predecessor is unissued, unless its version is 0 "
                            #"and its sequence is the last one. Delete a "
                            #"series of unissued bills in sequence order."))

                reebill = self.state_db.get_reebill(session, account, sequence)
                deleted_version = self.process.delete_reebill(session, reebill)

                # Delete the PDF associated with a reebill if it was version 0
                # because we believe it is confusing to delete the pdf when
                # when a version still exists
                if deleted_version == 0:
                    path = self.config.get('billdb', 'billpath')+'%s' %(account)
                    file_name = "%.5d_%.4d.pdf" % (int(account), int(sequence))
                    full_path = os.path.join(path, file_name)

                    # If the file exists, delete it, otherwise don't worry.
                    try:
                        os.remove(full_path)
                    except OSError as e:
                        if e.errno != errno.ENOENT:
                            raise
            
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
        sequence = int(sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested addresses
        # if this is the case, return no periods.  
        # This is done so that the UI can configure itself with no data
        if reebill is None:
            # TODO: 40161259 - must return success field
            return self.dumps({})

        ba = reebill.billing_address
        sa = reebill.service_address
        
        account_info = {'success': True}

        account_info['billing_address'] = {
            'addressee': ba['addressee'] if 'addressee' in ba else '',
            'street': ba['street'] if 'street' in ba else '',
            'city': ba['city'] if 'city' in ba else '',
            'state': ba['state'] if 'state' in ba else '',
            'postal_code': ba['postal_code'] if 'postal_code' in ba else '',
        }

        account_info['service_address'] = {
            'addressee': sa['addressee'] if 'addressee' in sa else '',
            'street': sa['street'] if 'street' in sa else '',
            'city': sa['city'] if 'city' in sa else '',
            'state': sa['state'] if 'state' in sa else '',
            'postal_code': sa['postal_code'] if 'postal_code' in sa else '',
        }

        try:
            account_info['late_charge_rate'] = reebill.late_charge_rate
        except KeyError:
            # ignore late charge rate when absent
            pass

        account_info['discount_rate'] = reebill.discount_rate

        # TODO: 40161259 - must return success field
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
        """ Update account information in "Sequential Account Information form.
        """
        sequence = int(sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence)

        # TODO: 27042211 numerical types
        reebill.discount_rate = discount_rate

        # process late_charge_rate
        # strip out anything unrelated to a decimal number
        late_charge_rate = re.sub('[^0-9\.-]+', '', late_charge_rate)
        if late_charge_rate:
            late_charge_rate = late_charge_rate
            if late_charge_rate < 0 or late_charge_rate >1:
                return self.dumps({'success': False, 'errors': {'reason':'Late Charge Rate', 'details':'must be between 0 and 1', 'late_charge_rate':'Invalid late charge rate'}})
            reebill.late_charge_rate = late_charge_rate
        
        ba = {}
        sa = {}
        
        ba['addressee'] = ba_addressee
        ba['street'] = ba_street
        ba['city'] = ba_city
        ba['state'] = ba_state
        ba['postal_code'] = ba_postal_code
        reebill.billing_address = ba

        sa['addressee'] = ba_addressee
        sa['street'] = ba_street
        sa['city'] = ba_city
        sa['state'] = ba_state
        sa['postal_code'] = ba_postal_code
        reebill.service_address = sa

        # set disabled services (services not mentioned in the request are
        # automatically resumed)
        for service in reebill.services:
            if kwargs.get('%s_suspended' % service, '') == 'on' or kwargs \
                    .get('%s_suspended' % service.lower(), '') == 'on':
                reebill.suspend_service(service.lower())
                #print service, 'suspended'
            elif kwargs.get('%s_suspended' % service, '') == 'off' or kwargs \
                    .get('%s_suspended' % service.lower(), '') == 'off':
                #print service, 'resumed'
                reebill.resume_service(service.lower())

        self.reebill_dao.save_reebill(reebill)

        return self.dumps({'success':True})


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

    #
    ################

    ################
    # handle actual and hypothetical charges 

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def actualCharges(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        with DBSession(self.state_db) as session:
            utilbill_doc = self.process.get_utilbill_doc(session, utilbill_id,
                    reebill_sequence=reebill_sequence,
                    reebill_version=reebill_version)
            flattened_charges = mongo.actual_chargegroups_flattened(utilbill_doc)

            if xaction == "read":
                return self.dumps({'success': True, 'rows': flattened_charges})

            # only xaction "read" is allowed when reebill_sequence/version
            # arguments are given
            if (reebill_sequence, reebill_version) != (None, None):
                raise IssuedBillError('Issued reebills cannot be modified')

            if xaction == "update":
                rows = json.loads(kwargs["rows"])
                # single edit comes in not in a list
                if type(rows) is dict: rows = [rows]
                for row in rows:
                    # identify the charge item UUID of the posted data
                    ci_uuid = row['uuid']
                    # identify the charge item, and update it with posted data
                    matches = [ci_match for ci_match in it.ifilter(lambda x:
                            x['uuid']==ci_uuid, flattened_charges)]
                    # there should only be one match
                    if (len(matches) == 0):
                        raise Exception("Did not match charge item UUID which should not be possible")
                    if (len(matches) > 1):
                        raise Exception("Matched more than one charge item UUID which should not be possible")
                    ci = matches[0]

                    # now that blank values are removed, ensure that required fields were sent from client 
                    # if 'rsi_binding' not in row: raise Exception("RSI must have an rsi_binding")

                    # now take the legitimate values from the posted data and update the RSI
                    # clear it so that the old emptied attributes are removed
                    ci.clear()
                    ci.update(row)

                mongo.set_actual_chargegroups_flattened(utilbill_doc,
                        flattened_charges)
                self.reebill_dao.save_utilbill(utilbill_doc)
                return self.dumps({'success':True})

            if xaction == "create":
                rows = json.loads(kwargs["rows"])
                # single create comes in not in a list
                if type(rows) is dict: rows = [rows]
                for row in rows:
                    row["uuid"] = str(UUID.uuid1())
                    flattened_charges.append(copy.copy(row))
                mongo.set_actual_chargegroups_flattened(utilbill_doc,
                        flattened_charges)
                self.reebill_dao.save_utilbill(utilbill_doc)

                return self.dumps({'success':True, 'rows':rows})

            if xaction == "destroy":
                uuids = json.loads(kwargs["rows"])
                # single edit comes in not in a list
                # TODO: understand why this is a unicode coming up from browser
                if type(uuids) is unicode: uuids = [uuids]
                for ci_uuid in uuids:
                    # identify the rsi
                    matches = [result for result in it.ifilter(lambda x: x['uuid']==ci_uuid, flattened_charges)]
                    if (len(matches) == 0):
                        raise Exception("Did not match a charge item UUID which should not be possible")
                    if (len(matches) > 1):
                        raise Exception("Matched more than one charge item UUID which should not be possible")
                    ci = matches[0]
                    flattened_charges.remove(ci)
                mongo.set_actual_chargegroups_flattened(utilbill_doc,
                        flattened_charges)
                self.reebill_dao.save_utilbill(utilbill_doc)

                return self.dumps({'success':True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def hypotheticalCharges(self, xaction, service, account, sequence, **kwargs):
        service = service.lower()
        sequence = int(sequence)

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested charges 
        # if this is the case, return no charges.  
        # This is done so that the UI can configure itself with no data for the
        # requested charges 
        # TODO ensure that this is necessary with new datastore scheme
        if reebill is None:
            return self.dumps({'success':True, 'rows':[]})

        utilbill_doc = reebill._get_utilbill_for_service(service)
        flattened_charges_a = mongo.actual_chargegroups_flattened(utilbill_doc)
        charge_dict_a = {c['rsi_binding']:c for c in flattened_charges_a}
        flattened_charges_h = reebill.hypothetical_chargegroups_flattened(service)
        for charge_dict_h in flattened_charges_h:
            matching = charge_dict_a[charge_dict_h['rsi_binding']]
            charge_dict_h['actual_rate'] = matching['rate']
            charge_dict_h['actual_quantity'] = matching['quantity']
            charge_dict_h['actual_total'] = matching['total']
        if xaction == "read":
            return self.dumps({'success': True, 'rows': flattened_charges_h})
        else:
            raise NotImplementedError('Cannot create, edit or destroy charges'+\
                                      ' from this grid.')


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

            toSelect = None

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

            try:
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
            except IOError:
                self.logger.error('file upload failed:', begin_date, end_date,
                        file_to_upload.filename)
                raise

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
                account, start, limit = kwargs['account'], kwargs['start'], kwargs['limit']

                # result is a list of dictionaries of the form {account: account
                # number, name: full name, period_start: date, period_end: date,
                # sequence: reebill sequence number (if present)}
                utilbills, totalCount = self.state_db.list_utilbills(session,
                        account, int(start), int(limit))
                # NOTE does not support multiple reebills per utility bill
                state_reebills = chain.from_iterable([ubrb.reebill for ubrb in
                        ub._utilbill_reebills] for ub in utilbills)

                full_names = self.full_names_of_accounts([account])
                full_name = full_names[0] if full_names else account

                rows = [{
                    # TODO: sending real database ids to the client a security
                    # risk; these should be encrypted
                    'id': ub.id,
                    'account': ub.customer.account,
                    'name': full_name,
                    'utility': ub.utility,
                    'rate_structure': ub.rate_class,
                    # capitalize service name
                    'service': 'Unknown' if ub.service is None else
                           ub.service[0].upper() + ub.service[1:],
                    'period_start': ub.period_start,
                    'period_end': ub.period_end,
                    'total_charges': ub.total_charges,
                    'computed_total': mongo.total_of_all_charges(
                            self.reebill_dao.load_doc_for_utilbill(ub)),
                    # NOTE the value of 'issue_date' in this JSON object is
                    # used by the client to determine whether a frozen utility
                    # bill version exists (when issue date == null, the reebill
                    # is unissued, so there is no frozen version of the utility
                    # bill corresponding to it).
                    'reebills': ub.sequence_version_json(),
                    'state': ub.state_name(),
                    # utility bill rows are always editable (since editing them
                    # should not affect utility bill data in issued reebills)
                    'editable': True,
                } for ub in utilbills]

                return self.dumps({'success': True, 'rows':rows,
                        'results':totalCount})
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
                    elif k == 'rate_structure':
                        # translate wrong name into right one 
                        update_args['rate_class'] = v
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
                    # load utilbill to get its dates and service
                    utilbill = session.query(state.UtilBill)\
                            .filter(state.UtilBill.id == utilbill_id).one()
                    start, end = utilbill.period_start, utilbill.period_end
                    service = utilbill.service

                    # delete it & get new path (will be None if there was never
                    # a utility bill file or the file could not be found)
                    deleted_path = self.process.delete_utility_bill(session,
                            utilbill)

                    # log it
                    journal.UtilBillDeletedEvent.save_instance(
                            cherrypy.session['user'], account, start, end,
                            service, deleted_path)

                # delete any estimated utility bills that were created to
                # cover gaps that no longer exist
                self.state_db.trim_hypothetical_utilbills(session,
                        utilbill.customer.account, utilbill.service)

                return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getUtilBillImage(self, account, begin_date, end_date, resolution, **args):
        # TODO: put url here, instead of in billentry.js?
        resolution = cherrypy.session['user'].preferences['bill_image_resolution']
        try:
            result = self.billUpload.getUtilBillImagePath(account, begin_date, end_date, resolution)
        except IOError:
            return self.dumps({'success':False})
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
        try:
            result = self.billUpload.getReeBillImagePath(account, sequence, resolution)
        except IOError:
            return self.dumps({'success':False})
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
