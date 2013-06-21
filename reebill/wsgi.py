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
from decimal import Decimal, DivisionByZero, InvalidOperation
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
import operator
from StringIO import StringIO
import mongoengine
from skyliner.skymap.monguru import Monguru
from skyliner.splinter import Splinter
#TODO don't rely on test code, if we are, it isn't test code
from skyliner import mock_skyliner
from billing.util import json_util as ju, dateutils, nexus_util as nu
from billing.util.nexus_util import NexusUtil
from billing.util.dictutils import deep_map
from billing.processing import mongo, billupload, excel_export
from billing.util import monthmath
from billing.processing import process, state, db_objects, fetch_bill_data as fbd, rate_structure as rs
from billing.processing.billupload import BillUpload
from billing.processing import journal, bill_mailer
from billing.processing import render
from billing.processing.users import UserDAO, User
from billing.processing import calendar_reports
from billing.processing.estimated_revenue import EstimatedRevenue
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import Unauthenticated, IssuedBillError



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
            self.config.set('skyline_backend', 'nexus_host', '[specify nexus host]')

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
        self.nexus_util = NexusUtil(self.config.get('skyline_backend', 'nexus_host'))

        # load users database
        self.user_dao = UserDAO(**dict(self.config.items('usersdb')))

        # create an instance representing the database
        self.statedb_config = dict(self.config.items("statedb"))
        self.state_db = state.StateDB(**self.statedb_config) 

        # create one BillUpload object to use for all BillUpload-related methods
        self.billUpload = BillUpload(self.config, self.logger)

        # create a MongoReeBillDAO
        self.billdb_config = dict(self.config.items("billdb"))
        self.reebill_dao = mongo.ReebillDAO(self.state_db, **self.billdb_config)

        # create a RateStructureDAO
        rsdb_config_section = dict(self.config.items("rsdb"))
        self.ratestructure_dao = rs.RateStructureDAO(
            rsdb_config_section['host'],
            rsdb_config_section['port'],
            rsdb_config_section['database'],
            self.reebill_dao,
            logger=self.logger
        )

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
                        'nexus_db': 'nexus',
                        'nexus_collection': 'skyline',
                    },
                },
                cartographer_options={
                    'olap_cache_host': self.config.get('skyline_backend', 'olap_host'),
                    'olap_cache_db': self.config.get('skyline_backend', 'olap_database'),
                    'measure_collection': 'skymap',
                    'install_collection': 'skyit_installs',
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
        return json.dumps(config_dict)

    ###########################################################################
    # bill processing

    # TODO: do this on a per service basis 18311877
    @json_exception
    def copyactual(self, account, sequence, **args):
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
        reebill = self.reebill_dao.load_reebill(account, sequence)
        self.process.copy_actual_charges(reebill)
        self.reebill_dao.save_reebill(reebill)
        return self.dumps({'success': True})

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
    def new_account(self, name, account, discount_rate, late_charge_rate, template_account,
                    ba_addressee, ba_street1, ba_city, ba_state, ba_postal_code,
                    sa_addressee, sa_street1, sa_city, sa_state, sa_postal_code, **kwargs):
        with DBSession(self.state_db) as session:
            if not name or not account or not discount_rate or not template_account:
                raise ValueError("Bad Parameter Value")
            customer = self.process.create_new_account(session, account, name,
                    discount_rate, late_charge_rate, template_account)
            reebill = self.reebill_dao.load_reebill(account, self.state_db.last_sequence(session, account))
            ba = {}
            ba['ba_addressee'] = ba_addressee
            ba['ba_street1'] = ba_street1
            ba['ba_city'] = ba_city
            ba['ba_state'] = ba_state
            ba['ba_postal_code'] = ba_postal_code
            reebill.billing_address = ba
            
            sa = {}
            sa['sa_addressee'] = sa_addressee
            sa['sa_street1'] = sa_street1
            sa['sa_city'] = sa_city
            sa['sa_state'] = sa_state
            sa['sa_postal_code'] = sa_postal_code
            reebill.service_address = sa
            self.reebill_dao.save_reebill(reebill)
            # record account creation
            # (no sequence associated with this)
            journal.AccountCreatedEvent.save_instance(cherrypy.session['user'],
                    customer.account)

            # get next account number to send it back to the client so it
            # can be shown in the account-creation form
            next_account = self.state_db.get_next_account_number(session)
            return self.dumps({'success': True, 'nextAccount': next_account})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def roll(self, account, **kwargs):
        if not account:
            raise ValueError("Bad Parameter Value")
        start_date = kwargs.get('start_date')
        if start_date is not None:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')

        # 1st transaction: roll
        with DBSession(self.state_db) as session:
            lastSequence = self.state_db.last_sequence(session, account)
            reebill = self.reebill_dao.load_reebill(account, lastSequence)
            new_reebill = self.process.roll_bill(session, reebill, start_date)
            self.reebill_dao.save_reebill(new_reebill)
            journal.ReeBillRolledEvent.save_instance(cherrypy.session['user'],
                    account, new_reebill.sequence)
            # Process.roll includes attachment
            journal.ReeBillAttachedEvent.save_instance(cherrypy.session['user'],
                account, new_reebill.sequence, new_reebill.version)

        # 2nd transaction: bind and compute. if one of these fails, don't undo
        # the changes to MySQL above, leaving a Mongo reebill document without
        # a corresponding MySQL row; only undo the changes related to binding
        # and computing (currently there are none).
        with DBSession(self.state_db) as session:
            new_reebill = self.reebill_dao.load_reebill(account, lastSequence+1)
            if self.config.getboolean('runtime', 'integrate_skyline_backend') is True:
                fbd.fetch_oltp_data(self.splinter, self.nexus_util.olap_id(account),
                    new_reebill, use_olap=True, verbose=True)
            self.reebill_dao.save_reebill(new_reebill)
            journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, new_reebill.sequence, new_reebill.version)
            
            self.process.compute_bill(session, reebill, new_reebill)
            self.reebill_dao.save_reebill(new_reebill)

            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def bindree(self, account, sequence, **kwargs):
        '''Puts energy from Skyline OLTP into shadow registers of the reebill
        given by account, sequence.'''
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
        if self.config.getboolean('runtime', 'integrate_skyline_backend') is False:
            raise Exception("OLTP is not integrated")
        if self.config.getboolean('runtime', 'integrate_nexus') is False:
            raise Exception("Nexus is not integrated")
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
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
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
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
        sequence = int(sequence)
        with DBSession(self.state_db) as session:
            for sequence in range(sequence, self.state_db.last_sequence(session,
                    account) + 1):
                # use version 0 of the predecessor to show the real account
                # history (prior balance, payment received, balance forward)
                mongo_reebill = self.reebill_dao.load_reebill(account,
                        sequence, version='max')
                mongo_predecessor = self.reebill_dao.load_reebill(account,
                        sequence - 1, version=0)
                self.process.compute_bill(session, mongo_predecessor, mongo_reebill)
                self.reebill_dao.save_reebill(mongo_reebill)
            return self.dumps({'success': True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def render(self, account, sequence, **args):
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
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

#    no longer used (also disabled in client code)
#    def attach_utility_bills(self, session, account, sequence):
#        '''Finalizes association between the reebill given by 'account',
#        'sequence' and its utility bills by recording it in the state database
#        and marking the utility bills as processed. Utility bills for suspended
#        services are skipped. Note that this does not issue the reebill or give
#        it an issue date.'''
#        # finalize utility bill association
#        reebill = self.reebill_dao.load_reebill(account, sequence)
#        self.process.attach_utilbills(session, reebill)
#
#        version = self.state_db.max_version(session, account, sequence)
#        journal.ReeBillAttachedEvent.save_instance(cherrypy.session['user'],
#                account, sequence, version)
#
#    @cherrypy.expose
#    @random_wait
#    @authenticate_ajax
#    @json_exception
#    def attach_utilbills(self, account, sequence, **args):
#        '''Handles AJAX call to attach utility bills without issuing. Normally
#        this is done through 'issue'.'''
#        if not account or not sequence:
#            raise ValueError("Bad Parameter Value")
#        with DBSession(self.state_db) as session:
#            reebill = self.reebill_dao.load_reebill(account, sequence)
#            if reebill is None:
#                raise Exception('No reebill for account %s, sequence %s')
#            self.attach_utility_bills(session, account, sequence)
#            return self.dumps({'success': True})

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
            predecessor = self.reebill_dao.load_reebill(account,
                    unissued_sequence - 1, version=0)
            reebill = self.reebill_dao.load_reebill(account, unissued_sequence)
            self.process.compute_bill(session, predecessor, reebill)
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
            merge_fields["sa_street1"] = mongo_reebill.service_address.get("sa_street1","")
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
        if not account or not sequences:
            raise ValueError("Bad Parameter Value")
        
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
            merge_fields["sa_street1"] = most_recent_bill.service_address.get("sa_street1","")
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
        for account, all_names in name_dicts:
            names = [account]
            # Only include the names that exist in Nexus
            names += [all_names[name] for name in ('codename', 'casualname', 'primus') if all_names.get(name)]
            result.append(' - '.join(names))
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
        if not account:
            raise ValueError("Bad Parameter Value")
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
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        if not start or not limit:
            raise ValueError("Bad Parameter Value")

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
            for i, status in enumerate(statuses):

                # load highest version of last issued reebill to get data out of it
                reebill = self.reebill_dao.load_reebill(status.account,
                        self.state_db.last_issued_sequence(session, status.account))

                #utility_service_addresses = ', '.join(
                        #u['service_address'].get('street', '?') for u in
                        #reebill._utilbills)
                # NOTE "utility service address" is currently coming from the
                # reebill document, but this should change
                utility_service_addresses = reebill.service_address_formatted()

                last_issue_date = str(reebill.issue_date) if reebill.issue_date is \
                        not None else 'Never Issued'
                lastevent = self.journal_dao.last_event_summary(status.account)

                row = {
                    'account': status.account,
                    'codename': name_dicts[status.account]['codename'] if
                           'codename' in name_dicts[status.account] else '',
                    'casualname': name_dicts[status.account]['casualname'] if
                           'casualname' in name_dicts[status.account] else '',
                    'primusname': name_dicts[status.account]['primus'] if
                           'primus' in name_dicts[status.account] else '',
                    'utilityserviceaddress': utility_service_addresses,
                    'dayssince': status.dayssince,
                    'lastissuedate': last_issue_date,
                    'lastevent': lastevent,
                    'provisionable': False,
                }
                
                rows.append(row)

            if sortcol == 'account':
                rows.sort(key=lambda r: r['account'], reverse=sortreverse)
            elif sortcol == 'codename':
                rows.sort(key=lambda r: r['codename'], reverse=sortreverse)
            elif sortcol == 'casualname':
                rows.sort(key=lambda r: r['casualname'], reverse=sortreverse)
            elif sortcol == 'primusname':
                rows.sort(key=lambda r: r['primusname'], reverse=sortreverse)
            elif sortcol == 'dayssince':
                rows.sort(key=lambda r: r['dayssince'], reverse=sortreverse)
            elif sortcol == 'lastissuedate':
                rows.sort(key=lambda r: r['lastissuedate'] if r['lastissuedate'] != 'Never Issued' else '', reverse=sortreverse)
            elif sortcol == 'lastevent':
                rows.sort(key=lambda r: r['lastevent'], reverse=sortreverse)

            # also get customers from Nexus who don't exist in billing yet
            # (do not sort these; just append them to the end)
            # TODO: we DO want to sort these, but we just want to them to come
            # after all the billing billing customers
            non_billing_customers = self.nexus_util.get_non_billing_customers()
            morerows = []
            for customer in non_billing_customers:
                morerows.append(dict([
                    # we have the olap_id too but we don't show it
                    ('account', 'n/a'),
                    ('codename', customer['codename']),
                    ('casualname', customer['casualname']),
                    ('primusname', customer['primus']),
                    ('dayssince', 'n/a'),
                    ('lastevent', 'n/a'),
                    ('provisionable', True)
                ]))

            if sortcol == 'account':
                morerows.sort(key=lambda r: r['account'], reverse=sortreverse)
            elif sortcol == 'codename':
                morerows.sort(key=lambda r: r['codename'], reverse=sortreverse)
            elif sortcol == 'casualname':
                morerows.sort(key=lambda r: r['casualname'], reverse=sortreverse)
            elif sortcol == 'primusname':
                morerows.sort(key=lambda r: r['primusname'], reverse=sortreverse)
            elif sortcol == 'dayssince':
                morerows.sort(key=lambda r: r['dayssince'], reverse=sortreverse)
            elif sortcol == 'lastevent':
                morerows.sort(key=lambda r: r['lastevent'], reverse=sortreverse)

            rows.extend(morerows)

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
        if not start or not limit:
            raise ValueError("Bad Parameter Value")
        with DBSession(self.state_db) as session:
            accounts, totalCount = self.state_db.list_accounts(session, int(start), int(limit))
            account_names = self.all_names_of_accounts([account for account in accounts])
            rows = self.process.summary_ree_charges(session, accounts, account_names)
            for row in rows:
                outstanding_balance = self.process.get_outstanding_balance(session, row['account'])
                days_since_due_date = None
                if outstanding_balance > 0:
                    payments = self.state_db.payments(session, row['account'])
                    if payments:
                        last_payment_date = payments[-1].date_received
                        reebills_since = self.reebill_dao.load_reebills_in_period(row['account'], 'any', last_payment_date, date.today())
                        if reebills_since and reebills_since[0].due_date:
                            days_since_due_date = (date.today() - reebills_since[0].due_date).days
                
                row.update({'outstandingbalance': '$%.2f' % outstanding_balance,
                           'days_late': days_since_due_date})
            return self.dumps({'success': True, 'rows':rows, 'results':totalCount})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def reebill_details_xls(self, begin_date=None, end_date=None, **kwargs):
        #prep date strings from client
        make_date = lambda x: datetime.strptime(x, dateutils.ISO_8601_DATE) if x else None
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
                    ba['ba_addressee'] if 'ba_addressee' in ba and ba['ba_addressee'] is not None else "",
                    ba['ba_street1'] if 'ba_street1' in ba and ba['ba_street1'] is not None else "",
                    ba['ba_city'] if 'ba_city' in ba and ba['ba_city'] is not None else "",
                    ba['ba_state'] if 'ba_state' in ba and ba['ba_state'] is not None else "",
                    ba['ba_postal_code'] if 'ba_postal_code' in ba and ba['ba_postal_code'] is not None else "",
                )
                sa = row['service_address']
                service_addr_str = "%s %s %s %s %s" % (
                    sa['sa_addressee'] if 'sa_addressee' in sa and sa['sa_addressee'] is not None else "",
                    sa['sa_street1'] if 'sa_street1' in sa and sa['sa_street1'] is not None else "",
                    sa['sa_city'] if 'sa_city' in sa and sa['sa_city'] is not None else "",
                    sa['sa_state'] if 'sa_state' in sa and sa['sa_state'] is not None else "",
                    sa['sa_postal_code'] if 'sa_postal_code' in sa and sa['sa_postal_code'] is not None else "",
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
                    ba['ba_addressee'] if 'ba_addressee' in ba and ba['ba_addressee'] is not None else "",
                    ba['ba_street1'] if 'ba_street1' in ba and ba['ba_street1'] is not None else "",
                    ba['ba_city'] if 'ba_city' in ba and ba['ba_city'] is not None else "",
                    ba['ba_state'] if 'ba_state' in ba and ba['ba_state'] is not None else "",
                    ba['ba_postal_code'] if 'ba_postal_code' in ba and ba['ba_postal_code'] is not None else "",
                )
                sa = row['service_address']
                service_addr_str = "%s %s %s %s %s" % (
                    sa['sa_addressee'] if 'sa_addressee' in sa and sa['sa_addressee'] is not None else "",
                    sa['sa_street1'] if 'sa_street1' in sa and sa['sa_street1'] is not None else "",
                    sa['sa_city'] if 'sa_city' in sa and sa['sa_city'] is not None else "",
                    sa['sa_state'] if 'sa_state' in sa and sa['sa_state'] is not None else "",
                    sa['sa_postal_code'] if 'sa_postal_code' in sa and sa['sa_postal_code'] is not None else "",
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
    # TODO see 15415625 about the problem passing in service to get at a set of RSIs
    def cprsrsi(self, xaction, account, sequence, service, **kwargs):
        if not xaction or not sequence or not service:
            raise ValueError("Bad Parameter Value")
        service = service.lower()

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested rate structure 
        # if this is the case, return no rate structure.  
        # This is done so that the UI can configure itself with no data for the
        # requested rate structure 
        if reebill is None:
            return self.dumps({'success':True})

        rate_structure = self.ratestructure_dao.load_cprs(
            reebill.account, 
            reebill.sequence, 
            reebill.version,
            reebill.utility_name_for_service(service),
            reebill.rate_structure_name_for_service(service)
        )

        rates = rate_structure["rates"]

        if xaction == "read":
            return self.dumps({'success': True, 'rows':rates})
        
        with DBSession(self.state_db) as session:
            if self.state_db.is_issued(session, account, sequence):
                raise Exception("Cannot edit rate structure for an issued bill")
            
        if xaction == "update":

            rows = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            if type(rows) is dict: rows = [rows]

            # process list of edits
            # TODO: RateStructure DAO should do CRUD ops
            for row in rows:
                # identify the RSI UUID of the posted data
                rsi_uuid = row['uuid']

                # identify the rsi, and update it with posted data
                matches = [rsi_match for rsi_match in it.ifilter(lambda x: x['uuid']==rsi_uuid, rates)]
                # there should only be one match
                if (len(matches) == 0):
                    raise Exception("Did not match an RSI UUID which should not be possible")
                if (len(matches) > 1):
                    raise Exception("Matched more than one RSI UUID which should not be possible")
                rsi = matches[0]

                # eliminate attributes that have empty strings or None as these mustn't 
                # be added to the RSI so the RSI knows to compute for those values
                for k,v in row.items():
                    if v is None or v == "":
                        del row[k]

                # now that blank values are removed, ensure that required fields were sent from client 
                if 'uuid' not in row: raise Exception("RSI must have a uuid")
                if 'rsi_binding' not in row: raise Exception("RSI must have an rsi_binding")

                # now take the legitimate values from the posted data and update the RSI
                # clear it so that the old emptied attributes are removed
                rsi.clear()
                rsi.update(row)

            self.ratestructure_dao.save_cprs(
                reebill.account, 
                reebill.sequence, 
                reebill.version,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                rate_structure
            )


            # 23417235 temporary hack
            result = self.compute_bill(account, sequence)
            return self.dumps({'success':True})

        elif xaction == "create":

            # TODO: 27315653 allow more than one RSI to be created

            new_rate = {"uuid": str(UUID.uuid1())}
            # should find an unbound charge item, and use its binding since an RSI
            # might be made after a charge item is created
            #new_rate['rsi_binding'] = orphaned binding
            rates.append(new_rate)

            self.ratestructure_dao.save_cprs(
                reebill.account, 
                reebill.sequence, 
                reebill.version,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True, 'rows':new_rate})

        elif xaction == "destroy":

            uuids = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            # TODO: understand why this is a unicode coming up from browser
            if type(uuids) is unicode: uuids = [uuids]

            # process list of removals
            for rsi_uuid in uuids:

                # identify the rsi
                matches = [result for result in it.ifilter(lambda x: x['uuid']==rsi_uuid, rates)]

                if (len(matches) == 0):
                    raise Exception("Did not match an RSI UUID which should not be possible")
                if (len(matches) > 1):
                    raise Exception("Matched more than one RSI UUID which should not be possible")
                rsi = matches[0]

                rates.remove(rsi)

            self.ratestructure_dao.save_cprs(
                reebill.account, 
                reebill.sequence, 
                reebill.version,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def uprsrsi(self, xaction, account, sequence, service, **kwargs):
        if not xaction or not account or not sequence or not service:
            raise ValueError("Bad Parameter Value")
        # client sends capitalized service names! workaround:
        service = service.lower()
        sequence = int(sequence)

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested rate structure 
        # if this is the case, return no rate structure.  
        # This is done so that the UI can configure itself with no data for the
        # requested rate structure 
        if reebill is None:
            return self.dumps({'success':True})

        utility_name = reebill.utility_name_for_service(service)
        rs_name = reebill.rate_structure_name_for_service(service)
        (effective, expires) = reebill.utilbill_period_for_service(service)
        rate_structure = self.ratestructure_dao.load_uprs(account, sequence,
                reebill.version, utility_name, rs_name)

        # It is possible the a UPRS does not exist for the utility billing period.
        # If this is the case, create it
        if rate_structure is None:
            raise Exception("Could not load UPRS for %s, %s %s to %s" %
                    (utility_name, rs_name, effective, expires) )

        rates = rate_structure["rates"]

        if xaction == "read":
            return self.dumps({'success': True, 'rows':rates})
        
        with DBSession(self.state_db) as session:
            if self.state_db.is_issued(session, account, sequence):
                raise Exception("Cannot edit rate structure for an issued bill")
            
        if xaction == "update":

            rows = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            if type(rows) is dict: rows = [rows]

            # process list of edits
            for row in rows:

                # identify the RSI descriptor of the posted data
                rsi_uuid = row['uuid']

                # identify the rsi, and update it with posted data
                matches = [rsi_match for rsi_match in it.ifilter(lambda x: x['uuid']==rsi_uuid, rates)]
                # there should only be one match
                if (len(matches) == 0):
                    raise Exception("Did not match an RSI UUID which should not be possible")
                if (len(matches) > 1):
                    raise Exception("Matched more than one RSI UUID which should not be possible")
                rsi = matches[0]

                # eliminate attributes that have empty strings or None as these mustn't 
                # be added to the RSI so the RSI knows to compute for those values
                for k,v in row.items():
                    if v is None or v == "":
                        del row[k]

                # now that blank values are removed, ensure that required fields were sent from client 
                if 'uuid' not in row: raise Exception("RSI must have a uuid")
                if 'rsi_binding' not in row: raise Exception("RSI must have an rsi_binding")

                # now take the legitimate values from the posted data and update the RSI
                # clear it so that the old emptied attributes are removed
                rsi.clear()
                rsi.update(row)

            self.ratestructure_dao.save_uprs(
                reebill.account, reebill.sequence, reebill.version,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True})

        elif xaction == "create":

            # TODO: 27315653 allow more than one RSI to be created

            new_rate = {"uuid": str(UUID.uuid1())}
            # find an oprhan binding and set it here
            #new_rate['rsi_binding'] = "Temporary RSI Binding"
            rates.append(new_rate)

            self.ratestructure_dao.save_uprs(
                reebill.account, reebill.sequence, reebill.version,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True, 'rows':new_rate})

        elif xaction == "destroy":

            uuids = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            # TODO: understand why this is a unicode coming up from browser
            if type(uuids) is unicode: uuids = [uuids]

            # process list of removals
            for rsi_uuid in uuids:

                # identify the rsi
                matches = [result for result in it.ifilter(lambda x: x['uuid']==rsi_uuid, rates)]

                if (len(matches) == 0):
                    raise Exception("Did not match an RSI UUID which should not be possible")
                if (len(matches) > 1):
                    raise Exception("Matched more than one RSI UUID which should not be possible")
                rsi = matches[0]

                rates.remove(rsi)

            self.ratestructure_dao.save_uprs(
                reebill.account, reebill.sequence, reebill.version,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def ursrsi(self, xaction, account, sequence, service, **kwargs):
        if not xaction or not account or not sequence or not service:
            raise ValueError("Bad Parameter Value")
        service = service.lower()

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested rate structure 
        # if this is the case, return no rate structure.  
        # This is done so that the UI can configure itself with no data for the
        # requested rate structure 
        if reebill is None:
            return self.dumps({'success':True})

        utility_name = reebill.utility_name_for_service(service)
        rs_name = reebill.rate_structure_name_for_service(service)
        rate_structure = self.ratestructure_dao.load_urs(utility_name, rs_name)

        if rate_structure is None:
            raise Exception("Could not load URS for %s and %s" % (utility_name, rs_name) )

        rates = rate_structure["rates"]

        if xaction == "read":
            return self.dumps({'success': True, 'rows':rates})

        with DBSession(self.state_db) as session:
            if self.state_db.is_issued(session, account, sequence):
                raise Exception("Cannot edit rate structure for an issued bill")
        
        if xaction == "update":

            rows = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            if type(rows) is dict: rows = [rows]

            # process list of edits
            for row in rows:

                # identify the RSI descriptor of the posted data
                rsi_uuid = row['uuid']

                # identify the rsi, and update it with posted data
                matches = [rsi_match for rsi_match in it.ifilter(lambda x: x['uuid']==rsi_uuid, rates)]
                # there should only be one match
                if (len(matches) == 0):
                    raise Exception("Did not match an RSI UUID which should not be possible")
                if (len(matches) > 1):
                    raise Exception("Matched more than one RSI UUID which should not be possible")
                rsi = matches[0]

                # eliminate attributes that have empty strings or None as these mustn't 
                # be added to the RSI so the RSI knows to compute for those values
                for k,v in row.items():
                    if v is None or v == "":
                        del row[k]

                # now that blank values are removed, ensure that required fields were sent from client 
                if 'uuid' not in row: raise Exception("RSI must have a uuid")
                if 'rsi_binding' not in row: raise Exception("RSI must have an rsi_binding")

                # now take the legitimate values from the posted data and update the RSI
                # clear it so that the old emptied attributes are removed
                rsi.clear()
                rsi.update(row)

            self.ratestructure_dao.save_urs(
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                None,
                None,
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True})

        elif xaction == "create":

            # TODO: 27315653 allow more than one RSI to be created

            new_rate = {"uuid": str(UUID.uuid1())}
            # find an orphan rsi and set its binding here
            #new_rate['rsi_binding'] = "Temporary RSI Binding"
            rates.append(new_rate)

            self.ratestructure_dao.save_urs(
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                None,
                None,
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True, 'rows':new_rate})

        elif xaction == "destroy":

            uuids = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            # TODO: understand why this is a unicode coming up from browser
            if type(uuids) is unicode: uuids = [uuids]

            # process list of removals
            for rsi_uuid in uuids:

                # identify the rsi
                matches = [result for result in it.ifilter(lambda x: x['uuid']==rsi_uuid, rates)]

                if (len(matches) == 0):
                    raise Exception("Did not match an RSI UUID which should not be possible")
                if (len(matches) > 1):
                    raise Exception("Matched more than one RSI UUID which should not be possible")
                rsi = matches[0]

                rates.remove(rsi)

            self.ratestructure_dao.save_urs(
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service),
                None,
                None,
                rate_structure
            )

            # 23417235 temporary hack
            self.compute_bill(account, sequence)
            return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def payment(self, xaction, account, **kwargs):
        if not xaction or not account:
            raise ValueError("Bad parameter value")
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
    def reebill(self, xaction, start, limit, account, sort = u'sequence', dir = u'DESC', **kwargs):
        '''Handles AJAX requests for reebill grid data.'''
        if not xaction or not start or not limit:
            raise ValueError("Bad Parameter Value")
        with DBSession(self.state_db) as session:
            if xaction == "read":
                reebills, totalCount = self.state_db.listReebills(session,
                        int(start), int(limit), account, sort, dir)
                rows = []
                for reebill in reebills:
                    row_dict = {}
                    mongo_reebill = self.reebill_dao.load_reebill(account, reebill.sequence)

                    # TODO: clean up. if a reebill lacks any of these keys,
                    # that's an error we do not want to bury. and there would
                    # be nothing wrong with putting a nice to_dict() method
                    # inside MongoReebill.
                    row_dict['id'] = reebill.sequence
                    row_dict['sequence'] = reebill.sequence
                    try: row_dict['issue_date'] = mongo_reebill.issue_date 
                    except: pass
                    try: row_dict['period_start'] = mongo_reebill.period_begin
                    except: pass
                    try: row_dict['period_end'] = mongo_reebill.period_end
                    except: pass
                    try: row_dict['hypothetical_total'] = mongo_reebill.hypothetical_total
                    except: pass
                    try: row_dict['actual_total'] = mongo_reebill.actual_total
                    except: pass
                    try: row_dict['ree_quantity'] = mongo_reebill.total_renewable_energy()
                    except: pass
                    try: row_dict['ree_value'] = mongo_reebill.ree_value
                    except: pass
                    try: row_dict['prior_balance'] = mongo_reebill.prior_balance
                    except: pass
                    try: row_dict['payment_received'] = mongo_reebill.payment_received
                    except: pass
                    try: row_dict['total_adjustment'] = mongo_reebill.total_adjustment
                    except: pass
                    try: row_dict['balance_forward'] = mongo_reebill.balance_forward
                    except: pass
                    try: row_dict['ree_charges'] = mongo_reebill.ree_charges
                    except: pass
                    try: row_dict['balance_due'] = mongo_reebill.balance_due
                    except: pass
                    try: row_dict['services'] = [service.title() for service in mongo_reebill.services]
                    except: pass

                    # human-readable description of correction state
                    version = self.state_db.max_version(session, account, reebill.sequence)
                    issued = self.state_db.is_issued(session, account, reebill.sequence)
                    if version > 0:
                        if issued:
                            row_dict['corrections'] = str(version)
                        else:
                            row_dict['corrections'] = '#%s not issued' % version
                    else:
                        row_dict['corrections'] = '-' if issued else '(never issued)'

                    # version as machine-readable invisible column
                    row_dict['max_version'] = version

                    # other invisible columns
                    row_dict['total_error'] = self.process.get_total_error(
                            session, account, reebill.sequence)
                    row_dict['issued'] = self.state_db.is_issued(session,
                            account, reebill.sequence)

                    rows.append(row_dict)
                return self.dumps({'success': True, 'rows':rows, 'results':totalCount})

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
        if not xaction:
            raise ValueError("Bad Parameter Value")
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
                        row_dict['difference'] = abs(1-row_dict['reebill_total']/row_dict['util_total'])
                    except DivisionByZero:
                        row_dict['difference'] = Decimal('Infinity')
                    except InvalidOperation:
                        row_dict['difference'] = Decimal(0.0)
                    row_dict['matching'] = row_dict['difference'] < allowable_diff
                    rows.append(row_dict)
                rows.sort(key=lambda d: d[sort], reverse = (direction == 'ASC'))
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
            last_sequence = self.state_db.last_sequence(session, account)
            for sequence in sequences:
                # forbid deletion if predecessor has an unissued version (note
                # that client is allowed to delete a range of bills at once, as
                # long as they're in sequence order)
                max_version = self.state_db.max_version(session, account, sequence)
                if not (max_version == 0 and sequence == last_sequence or max_version > 0 and
                        (sequence == 1 or self.state_db.is_issued(session, account, sequence - 1))):
                    raise ValueError(("Can't delete a reebill version whose "
                            "predecessor is unissued, unless its version is 0 "
                            "and its sequence is the last one. Delete a "
                            "series of unissued bills in sequence order."))
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
        '''Creates a new version of the given reebill and all its successors,
        if it's not issued.'''
        sequence = int(sequence)
        with DBSession(self.state_db) as session:
            # Process will complain if new version is not issued
            new_reebills = self.process.new_versions(session, account, sequence)
            for new_reebill in new_reebills:
                journal.NewReebillVersionEvent.save_instance(cherrypy.session['user'],
                        account, new_reebill.sequence, new_reebill.version)
                journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                        account, new_reebill.sequence, new_reebill.version)
            # client doesn't do anything with the result (yet)
            return self.dumps({'success': True, 'sequences': [r.sequence for r in
                    new_reebills]})

    ################
    # Handle addresses

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def account_info(self, account, sequence, **args):
        """ Return information about the account """
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested addresses
        # if this is the case, return no periods.  
        # This is done so that the UI can configure itself with no data
        if reebill is None:
            # TODO: 40161259 - must return success field
            return self.dumps({})

        ba = reebill.billing_address
        sa = reebill.service_address
        
        account_info = {}

        account_info['billing_address'] = {
            'ba_addressee': ba['ba_addressee'] if 'ba_addressee' in ba else '',
            'ba_street1': ba['ba_street1'] if 'ba_street1' in ba else '',
            'ba_city': ba['ba_city'] if 'ba_city' in ba else '',
            'ba_state': ba['ba_state'] if 'ba_state' in ba else '',
            'ba_postal_code': ba['ba_postal_code'] if 'ba_postal_code' in ba else '',
        }

        account_info['service_address'] = {
            'sa_addressee': sa['sa_addressee'] if 'sa_addressee' in sa else '',
            'sa_street1': sa['sa_street1'] if 'sa_street1' in sa else '',
            'sa_city': sa['sa_city'] if 'sa_city' in sa else '',
            'sa_state': sa['sa_state'] if 'sa_state' in sa else '',
            'sa_postal_code': sa['sa_postal_code'] if 'sa_postal_code' in sa else '',
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
        ba_addressee, ba_street1, ba_city, ba_state, ba_postal_code,
        sa_addressee, sa_street1, sa_city, sa_state, sa_postal_code,
        **kwargs):
        """
        Update account information
        """
        if not account or not sequence \
        or not discount_rate \
        or not ba_addressee or not ba_street1 or not ba_city or not ba_state or not ba_postal_code \
        or not sa_addressee or not sa_street1 or not sa_city or not sa_state or not sa_postal_code:
            raise ValueError("Bad Parameter Value")

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # TODO: 27042211 numerical types
        reebill.discount_rate = Decimal(discount_rate)

        # process late_charge_rate
        # strip out anything unrelated to a decimal number
        late_charge_rate = re.sub('[^0-9\.-]+', '', late_charge_rate)
        if late_charge_rate:
            late_charge_rate = Decimal(late_charge_rate)
            if late_charge_rate < 0 or late_charge_rate >1:
                return self.dumps({'success': False, 'errors': {'reason':'Late Charge Rate', 'details':'must be between 0 and 1', 'late_charge_rate':'Invalid late charge rate'}})
            reebill.late_charge_rate = Decimal(late_charge_rate)
        
        ba = {}
        sa = {}
        
        ba['ba_addressee'] = ba_addressee
        ba['ba_street1'] = ba_street1
        ba['ba_city'] = ba_city
        ba['ba_state'] = ba_state
        ba['ba_postal_code'] = ba_postal_code
        reebill.billing_address = ba

        sa['sa_addressee'] = sa_addressee
        sa['sa_street1'] = sa_street1
        sa['sa_city'] = sa_city
        sa['sa_state'] = sa_state
        sa['sa_postal_code'] = sa_postal_code
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
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
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
    def actualCharges(self, xaction, service, account, sequence, **kwargs):
        if not xaction or not account or not sequence or not service:
            raise ValueError("Bad Parameter Value")
        service = service.lower()

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested charges 
        # if this is the case, return no charges.  
        # This is done so that the UI can configure itself with no data for the
        # requested charges 
        # TODO ensure that this is necessary with new datastore scheme
        if reebill is None:
            return self.dumps({'success':True, 'rows':[]})

        flattened_charges = reebill.actual_chargegroups_flattened(service)

        if xaction == "read":
            return self.dumps({'success': True, 'rows': flattened_charges})

        elif xaction == "update":
            rows = json.loads(kwargs["rows"])
            # single edit comes in not in a list
            if type(rows) is dict: rows = [rows]
            for row in rows:
                # identify the charge item UUID of the posted data
                ci_uuid = row['uuid']
                # identify the charge item, and update it with posted data
                matches = [ci_match for ci_match in it.ifilter(lambda x: x['uuid']==ci_uuid, flattened_charges)]
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
            reebill.set_actual_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)
            # copy actual charges to hypothetical
            self.copyactual(account, sequence)
            return self.dumps({'success':True})
        elif xaction == "create":
            rows = json.loads(kwargs["rows"])
            # single create comes in not in a list
            if type(rows) is dict: rows = [rows]
            for row in rows:
                row["uuid"] = str(UUID.uuid1())
                # TODO: 22726549 need a copy here because reebill mangles the datastructure passed in
                flattened_charges.append(copy.copy(row))
            # TODO: 22726549 Reebill shouldn't mangle a datastructure passed in.  It should make a copy
            # for itself.
            reebill.set_actual_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)
            # copy actual charges to hypothetical
            self.copyactual(account, sequence)
            return self.dumps({'success':True, 'rows':rows})
        elif xaction == "destroy":
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
            reebill.set_actual_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)
            # copy actual charges to hypothetical
            self.copyactual(account, sequence)
            return self.dumps({'success':True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def hypotheticalCharges(self, xaction, service, account, sequence, **kwargs):
        if not xaction or not account or not sequence or not service:
            raise ValueError("Bad Parameter Value")
        service = service.lower()

        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested charges 
        # if this is the case, return no charges.  
        # This is done so that the UI can configure itself with no data for the
        # requested charges 
        # TODO ensure that this is necessary with new datastore scheme
        if reebill is None:
            return self.dumps({'success':True, 'rows':[]})

        flattened_charges = reebill.hypothetical_chargegroups_flattened(service)

        if xaction == "read":
            return self.dumps({'success': True, 'rows': flattened_charges})

        elif xaction == "update":

            rows = json.loads(kwargs["rows"])

            # single edit comes in not in a list
            if type(rows) is dict: rows = [rows]

            for row in rows:
                # identify the charge item UUID of the posted data
                ci_uuid = row['uuid']

                # identify the charge item, and update it with posted data
                matches = [ci_match for ci_match in it.ifilter(lambda x: x['uuid']==ci_uuid, flattened_charges)]
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

            reebill.set_hypothetical_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)

            return self.dumps({'success':True})

        elif xaction == "create":

            rows = json.loads(kwargs["rows"])

            # single create comes in not in a list
            if type(rows) is dict: rows = [rows]

            for row in rows:
                row["uuid"] = str(UUID.uuid1())
                # TODO: 22726549 need a copy here because reebill mangles the datastructure passed in
                flattened_charges.append(copy.copy(row))

            # TODO: 22726549 Reebill shouldn't mangle a datastructure passed in.  It should make a copy
            # for itself.
            reebill.set_hypothetical_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)

            return self.dumps({'success':True, 'rows':rows})

        elif xaction == "destroy":

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

            reebill.set_hypothetical_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)

            return self.dumps({'success':True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def _saveActualCharges(self, service, account, sequence, rows, **args):
        if not account or not sequence or not service or not rows:
            raise ValueError("Bad Parameter Value")
        flattened_charges = ju.loads(rows)
        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.set_actual_chargegroups_flattened(service, flattened_charges)
        self.reebill_dao.save_reebill(reebill)
        # copy actual charges to hypothetical
        self.copyactual(account, sequence)
        return self.dumps({'success': True})


    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def _saveHypotheticalCharges(self, service, account, sequence, rows, **args):
        if not account or not sequence or not service or not rows:
            raise ValueError("Bad Parameter Value")
        flattened_charges = ju.loads(rows)

        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.set_hypothetical_chargegroups_flattened(service, flattened_charges)
        self.reebill_dao.save_reebill(reebill)
    
        return self.dumps({'success': True})


    ################
    # Handle measuredUsages
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def utilbill_registers(self, account, sequence, **args):
        """
        """
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
        reebill = self.reebill_dao.load_reebill(account, sequence)
        # It is possible that there is no reebill for the requested measured usages
        # if this is the case, return no usages.  
        # This is done so that the UI can configure itself with no data for the
        # requested measured usage
        if reebill is None:
            # TODO: 40161259 must return success field
            return self.dumps({'success': True, 'meters':[], 'total':0})

        meters = reebill.meters
        registers = []
        for service, meter_list in meters.items():
            for meter in meter_list:
                meter_id = meter['identifier']
                for register in meter['registers']:
                    if not register['shadow']:
                        row = {'id':service+'/'+meter_id+'/'+register['identifier'], 'meter_id':meter_id, 'register_id':register['identifier'], 'service':service}
                        row['type'] = register.get('type', '')
                        row['binding'] = register.get('register_binding', '')
                        row['description'] = register.get('description', '')
                        row['quantity'] = register.get('quantity', 0)
                        row['quantity_units'] = register.get('quantity_units','')
                        registers.append(row)
            
        if args['xaction'] == 'read':
            toRet = {'success':True, "rows":registers, 'total':len(registers)}
            for r in registers:
                if 'current_selected_id' in args and r['id'] == args['current_selected_id']:
                    toRet['current_selected_id'] = r['id']
            return self.dumps(toRet)
        rows = json.loads(args['rows'])
        if type(rows) is not list:
            rows = [rows]
        toSelect = None
        if args['xaction'] == 'create':
            for row in rows:
                if not row.has_key('service'):
                    row['service'] = reebill.services[0]
                if '/' in row.get('meter_id','') or '/' in row.get('register_id',''):
                    raise ValueError('Cannot use a \'/\' in a meter or register identifier')
                meter_id, new_reg = reebill.new_register(row['service'], row.get('meter_id', None), row.get('register_id', None))
                if not row.has_key('meter_id'):
                    row['meter_id'] = meter_id
                if not row.has_key('register_id'):
                    row['register_id'] = new_reg['identifier']
                row['id'] = row['service']+'/'+row['meter_id']+'/'+row['register_id']
                row['type'] = ''
                row['binding'] = ''
                row['description'] = ''
                row['quantity'] = 0
                row['quantity_units'] = ''
                registers.append(row)
            toSelect = rows[0]['id']
        if args['xaction'] == 'update' or args['xaction'] == 'create':
            regs = []
            for row in rows:
                reg = next((r for r in registers if r['id'] == row['id']), None)
                old_id = row['id']
                old_ids = old_id.split('/')
                if len(old_ids) != 3:
                    raise ValueError('ID doesn\'t split into 3 parts: %s'%id)
                old_service, old_meter, old_register = old_ids
                if reg is None:
                    raise ValueError('No register found with id %s for meter %s for service %s' %(old_register, old_meter, old_service))
                reg.update(row)
                new_service = row.get('service', old_service).lower()
                reg['service'] = new_service
                new_meter = row.get('meter_id', old_meter)
                new_register = row.get('register_id', old_register)
                if '/' in row.get('meter_id','') or '/' in row.get('register_id',''):
                    raise ValueError('Cannot use a \'/\' in a meter or register identifier')
                if new_service != old_service or new_meter != old_meter or new_register != old_register:
                    meter = reebill._meter(new_service, new_meter)
                    if meter is not None:
                        for _r in meter['registers']:
                            if _r['identifier'] == new_register:
                                raise ValueError('Register with id %s for meter %s for service %s already exists' %(new_register, new_meter, new_service))
                if new_service != old_service or new_meter != old_meter:
                    reebill.delete_register(old_service, old_meter, old_register)
                    reebill.new_register(new_service, new_meter, old_register)
                    old_service = new_service
                    old_meter = new_meter
                new_dict = {}
                new_dict['identifier'] = reg['register_id']
                new_dict['description'] = reg['description']
                new_dict['type'] = reg['type']
                new_dict['register_binding'] = reg['binding']
                new_dict['quantity'] = reg['quantity']
                new_dict['quantity_units'] = reg['quantity_units']
                reebill.update_register(old_service, old_meter, old_register, new_dict)
                reg['id'] = reg['service']+'/'+reg['meter_id']+'/'+reg['register_id']
                if 'current_selected_id' in args and old_id == args['current_selected_id'] and toSelect is None:
                    toSelect = reg['id']
        if args['xaction'] == 'destroy':
            for id in rows:
                old_ids = id.split('/')
                if len(old_ids) != 3:
                    raise ValueError('ID doesn\'t split into 3 parts: %s'%id)
                old_service, old_meter, old_register = old_ids
                reebill.delete_register(old_service, old_meter, old_register)
                registers[:] = [r for r in registers if r['id'] != id]
        reebill.set_meter_dates_from_utilbills()
        self.reebill_dao.save_reebill(reebill)
        toRet = {'success':True, "rows":registers, 'total':len(registers)}
        if toSelect is not None:
            toRet['current_selected_id'] = toSelect
        return self.dumps(toRet)
    
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def ubMeasuredUsages(self, account, sequence, branch=0, **args):
        """
        Return all of the measuredusages on a per service basis so that the forms may be
        dynamically created.

        This function returns a sophisticated data structure to the client. However, the client
        is expected to flatten it, and return edits keyed by meter or register identifier.

        {"SERVICENAME": [
            "present_read_date": "2011-10-04", 
            "prior_read_date": "2011-09-05",
            "identifier": "028702956",
            "registers": [
                {
                "description": "Total Ccf", 
                "quantity": 200.0, 
                "quantity_units": "Ccf", 
                "shadow": false, 
                "identifier": "028702956", 
                "type": "total", 
                "register_binding": "REG_TOTAL"
                }
            ], ...
        ]}
        """
        if not account or not sequence:
            raise ValueError("Bad Parameter Value")
        reebill = self.reebill_dao.load_reebill(account, sequence)

        # It is possible that there is no reebill for the requested measured usages
        # if this is the case, return no usages.  
        # This is done so that the UI can configure itself with no data for the
        # requested measured usage
        if reebill is None:
            # TODO: 40161259 must return success field
            return self.dumps({'success': True})

        meters = reebill.meters
        # TODO: 40161259 must return success field
        return self.dumps({'success':True, "meters":meters})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def setMeter(self, account, sequence, service, meter_identifier, presentreaddate, priorreaddate):
        if not account or not sequence or not service or not meter_identifier \
            or not presentreaddate or not priorreaddate:
            raise ValueError("Bad Parameter Value")

        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.set_meter_read_date(service, meter_identifier, 
            datetime.strptime(presentreaddate, "%Y-%m-%d"), 
            datetime.strptime(priorreaddate, "%Y-%m-%d")
        )
        self.reebill_dao.save_reebill(reebill)
        return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def setActualRegister(self, account, sequence, service, register_identifier, meter_identifier, quantity):
        if not account or not sequence or not service or not register_identifier \
            or not meter_identifier or not quantity:
            raise ValueError("Bad Parameter Value")
        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.set_meter_actual_register(service, meter_identifier, register_identifier, Decimal(quantity))
        self.reebill_dao.save_reebill(reebill)
        return self.dumps({'success':True})

    #
    ################

    ################
    # Handle utility bill upload

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def upload_utility_bill(self, account, service, begin_date, end_date, total_charges,
            file_to_upload, **args):
        with DBSession(self.state_db) as session:
            if not account or not begin_date or not end_date or not total_charges or not file_to_upload:
                raise ValueError("Bad Parameter Value")

            # pre-process parameters
            service = service.lower()
            total_charges_as_float = float(total_charges)
            begin_date_as_date = datetime.strptime(begin_date, '%Y-%m-%d').date()
            end_date_as_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            self.validate_utilbill_period(begin_date_as_date, end_date_as_date)

            try:
                self.process.upload_utility_bill(session, account, service,
                        begin_date_as_date, end_date_as_date,
                        file_to_upload.file, file_to_upload.filename if
                        file_to_upload else None, total=total_charges_as_float)
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
        journal_entries = self.journal_dao.load_entries(account)
#        for entry in journal_entries:
#            # TODO 29715501 replace user identifier with user name
#            # (UserDAO.load_user() currently requires a password to load a
#            # user, but we just want to translate an indentifier into a
#            # name)
#
#            # put a string containing all non-standard journal entry data in an
#            # 'extra' field for display in the browser, because the UI can't
#            # have column to handle any key that might appear in any event.
#            # disabled for now because the client doesn't actually show the
#            #"extra" data.
#            # TODO processing the entries in this way is slow when loading entries
#            # for all accounts. (yes, "paging" will be needed when the number of
#            # entries gets REALLY large but the real problem here is bad code,
#            # which should be fixed first. mongo aggregation is probably the
#            # simplest way to do it and it's fast.)
#            extra_data = copy.deepcopy(entry)
#            del extra_data['account']
#            if 'sequence' in extra_data:
#                del extra_data['sequence']
#            del extra_data['date']
#            if 'event' in extra_data:
#                del extra_data['event']
#            if 'user' in extra_data:
#                del extra_data['user']
#            entry['extra'] = ', '.join(['%s: %s' % (k,v) for (k,v) in extra_data.iteritems()])

        if xaction == "read":
            return self.dumps({'success': True, 'rows':journal_entries})

        elif xaction == "update":
            # TODO: 20493983 eventually allow admin user to override and edit
            return self.dumps({'success':False, 'errors':{'reason':'Not supported'}})

        elif xaction == "create":
            # TODO: 20493983 necessary for adding new journal entries directy to grid
            return self.dumps({'success':False, 'errors':{'reason':'Not supported'}})
        elif xaction == "destroy":
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
        if not account or not entry:
            raise ValueError("Bad Parameter Value")
        if sequence:
            sequence = int(sequence)
            journal.Note.save_instance(cherrypy.session['user'], account,
                    entry, sequence=sequence)
        else:
            journal.Note.save_instance(cherrypy.session['user'], account,
                    entry)
        return self.dumps({'success':True})

 
    # TODO merge into utilbill_grid(); this is not called by the front-end anymore
    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def listUtilBills(self, start, limit, account, **args):
        '''Handles AJAX call to populate Ext grid of utility bills.'''
        with DBSession(self.state_db) as session:
            # names for utilbill states in the UI
            state_descriptions = {
                db_objects.UtilBill.Complete: 'Final',
                db_objects.UtilBill.UtilityEstimated: 'Utility Estimated',
                db_objects.UtilBill.SkylineEstimated: 'Skyline Estimated',
                db_objects.UtilBill.Hypothetical: 'Missing'
            }

            if not start or not limit or not account:
                raise ValueError("Bad Parameter Value")

            # result is a list of dictionaries of the form {account: account
            # number, name: full name, period_start: date, period_end: date,
            # sequence: reebill sequence number (if present)}
            utilbills, totalCount = self.state_db.list_utilbills(session, account, int(start), int(limit))
            state_reebills = reduce(operator.add, (ub.reebills for ub in utilbills), [])
            mongo_reebills = [self.reebill_dao.load_reebill(rb.customer.account, rb.sequence) if rb else None for rb in state_reebills]

            full_names = self.full_names_of_accounts([account])
            full_name = full_names[0] if full_names else account

            rows = [dict([
                # TODO: sending real database ids to the client a security
                # risk; these should be encrypted
                ('id', ub.id),
                ('account', ub.customer.account),
                ('name', full_name),
                ('utility', rb.utility_name_for_service(ub.service) if ub.service is not None and rb is not None else ''),
                ('rate_structure', rb.rate_structure_name_for_service(ub.service) if ub.service is not None and rb is not None else ''),
                # capitalize service name
                ('service', 'Unknown' if ub.service is None else ub.service[0].upper() + ub.service[1:]),
                ('period_start', ub.period_start),
                ('period_end', ub.period_end),
                ('total_charges', ub.total_charges),
                ('sequence', max(r.sequence for r in ub.reebills if
                        r.customer.account == account) if ub.reebills != [] else
                        None),
                ('state', state_descriptions[ub.state]),
                # utility bill rows are only editable if they don't have any
                # issued reebills attached to them
                # TODO should become editable all the time; issued reebills
                # store all relevant history in their own document
                ('editable', (not ub.has_reebills or not any(r.issued for r in
                        ub.reebills)))
            ]) for rb, ub in zip(mongo_reebills, utilbills)]

            return self.dumps({'success': True, 'rows':rows, 'results':totalCount})
    
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

    def validate_utilbill_period(self, start, end):
        '''Raises an exception if the dates 'start' and 'end' are unreasonable
        as a utility bill period: "reasonable" means start < end and (end -
        start) < 1 year.'''
        if start >= end:
            raise Exception('Utility bill start date must precede end.')
        if (end - start).days > 365:
            raise Exception('Utility billing period lasts longer than a year?!')

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
                # for just reading, forward the request to the old function that
                # was doing this
                return self.listUtilBills(**kwargs)
            elif xaction == 'update':
                # TODO move out of BillToolBridge, make into its own function
                # so it's testable

                # only certain data can be updated.
                # parse data from the client

                # ext sends a dict if there is one row, a list of dicts if there are more than one
                rows = ju.loads(kwargs['rows'])
                utilbill_id = rows['id']
                new_period_start = datetime.strptime(rows['period_start'],
                        dateutils.ISO_8601_DATETIME_WITHOUT_ZONE).date()
                new_period_end = datetime.strptime(rows['period_end'],
                        dateutils.ISO_8601_DATETIME_WITHOUT_ZONE).date()
                new_service = rows['service'].lower()
                new_total_charges = rows['total_charges']
                new_utility = rows['utility']
                new_ratestructure = rows['rate_structure']

                # check that new dates are reasonable
                self.validate_utilbill_period(new_period_start, new_period_end)

                # find utilbill in mysql
                utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

                # load editable version of utility bill document from Mongo
                # TODO unissued reebill must have editable utility bill as its utility bill for this to work.
                # https://www.pivotaltracker.com/story/show/50223789
                utilbill_doc = self.reebill_dao.load_utilbill(account,
                        utilbill.service, utilbill.period_start,
                        utilbill.period_end, sequence=False, version=False)

                # move the file, if there is one. (only utility bills that are
                # Complete (0) or UtilityEstimated (1) have files;
                # SkylineEstimated (2) and Hypothetical (3) ones don't.)
                if utilbill.state < db_objects.UtilBill.SkylineEstimated:
                    self.billUpload.move_utilbill_file(utilbill.customer.account,
                            # don't trust the client to say what the original dates were
                            # TODO don't pass dates into BillUpload as strings
                            # https://www.pivotaltracker.com/story/show/24869817
                            utilbill.period_start,
                            utilbill.period_end,
                            new_period_start, new_period_end)

                # change dates in Mongo if needed
                if (utilbill.period_start != new_period_start or utilbill.period_end != new_period_end):
                    # NOTE meter read date(s) are not modified because there is
                    # no way to specify which meter in the utility bill grid
                    utilbill_doc['start'], utilbill_doc['end'] = new_period_start, new_period_end

                # update utility and ratestructure names
                # NOTE this is going to fail until RS document _ids no longer
                # contain reebill data (account, sequence)
                # https://www.pivotaltracker.com/story/show/50223313
                self.ratestructure_dao.update_rs_name(utilbill.customer.account,
                        reebill.sequence, reebill.max_version,
                        utilbill_doc['utility'],
                        utilbill_doc['rate_structure_binding'],
                        new_utility, new_ratestructure)
                utilbill_doc['utility'] = new_utility
                utilbill_doc['rate_structure_binding'] = new_ratestructure

                # change dates in MySQL
                utilbill.period_start = new_period_start
                utilbill.period_end = new_period_end
                utilbill.total_charges = new_total_charges

                # delete any estimated utility bills in MySQL that were created
                # to cover gaps that no longer exist
                self.state_db.trim_hypothetical_utilbills(session,
                        utilbill.customer.account, utilbill.service)

                # update service in MySQL
                utilbill.service = new_service

                self.reebill_dao._save_utilbill(utilbill_doc)

                return self.dumps({'success': True})

            elif xaction == 'create':
                # creation happens via upload_utility_bill
                # TODO move here?
                raise Exception('utilbill_grid() does not accept xaction "create"')
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
                print ids
                for utilbill_id in ids:
                    # load utilbill to get its dates and service
                    utilbill = session.query(db_objects.UtilBill)\
                            .filter(db_objects.UtilBill.id == utilbill_id).one()
                    start, end = utilbill.period_start, utilbill.period_end
                    service = utilbill.service

                    # delete it & get new path (will be None if there was never
                    # a utility bill file or the file could not be found)
                    print start, end, service
                    deleted_path = self.process.delete_utility_bill(session,
                            utilbill_id)

                    # log it
                    journal.UtilBillDeletedEvent.save_instance(cherrypy.session['user'],
                            account, start, end, service, deleted_path)

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
        if not account or not begin_date or not end_date or not resolution:
            raise ValueError("Bad Parameter Value")
        # TODO: put url here, instead of in billentry.js?
        resolution = cherrypy.session['user'].preferences['bill_image_resolution']
        result = self.billUpload.getUtilBillImagePath(account, begin_date, end_date, resolution)
        return self.dumps({'success':True, 'imageName':result})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def getReeBillImage(self, account, sequence, resolution, **args):
        if not account or not sequence or not resolution:
            raise ValueError("Bad Parameter Value")
        if not self.config.getboolean('billimages', 'show_reebill_images'):
            return self.dumps({'success': False, 'errors': {'reason':
                    'Reebill images have been turned off.'}})
        resolution = cherrypy.session['user'].preferences['bill_image_resolution']
        result = self.billUpload.getReeBillImagePath(account, sequence, resolution)
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
        threshold = cherrypy.session['user'].preferences['difference_threshold']*100.0
        return self.dumps({'success':True, 'threshold': threshold})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def setDifferenceThreshold(self, threshold, **kwargs):
        threshold=float(threshold)
        if not threshold or threshold > 100 or threshold <= 0:
            return self.dumps({'success':False, 'errors':"Threshold of %s is not valid." % str(threshold)})
        cherrypy.session['user'].preferences['difference_threshold'] = threshold/100.0
        self.user_dao.save_user(cherrypy.session['user'])
        return self.dumps({'success':True})

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def reebill_structure(self, account, sequence=None, **args):
        if not account:
            raise ValueError("Bad Parameter Value: account")
        with DBSession(self.state_db) as session:
            if sequence is None:
                sequence = self.state_db.last_sequence(session, account)
            reebill = self.reebill_dao.load_reebill(account, sequence)

            if reebill:

                services = reebill.services

                # construct utilbill parts
                tree = []
                node_index = 0
                for service in reebill.services:
                    utility = reebill.utility_name_for_service(service)
                    rate_structure = reebill.rate_structure_name_for_service(service)
                    chargegroups_model = reebill.chargegroups_model_for_service(service)
                    meters = reebill.meters_for_service(service)

                    utility_node = {
                        'id': str(UUID.uuid1()), 
                        'leaf': True,
                        'text': utility,
                    }

                    ratestructure_node = {
                        'id': str(UUID.uuid1()), 
                        'leaf': True,
                        'text': rate_structure,
                    }

                    meter_nodes = []
                    for meter in meters:
                        register_nodes = []
                        for register in meter['registers']:
                            if register['shadow'] is True:
                                continue
                            register_nodes.append({
                                'id': str(UUID.uuid1()),
                                'leaf': True,
                                'text': register['identifier'],
                                'service': service,
                                'account': account, 
                                'sequence': sequence, 
                                'node_type': 'register',
                                'node_key': register['identifier']
                            })
                        meter_nodes.append({
                            'id': str(UUID.uuid1()),
                            'text': meter['identifier'],
                            'children': register_nodes,
                            'service': service,
                            'account': account, 
                            'sequence': sequence, 
                            'node_type': 'meter',
                            'node_key': meter['identifier']
                        })

                    meters_node = {
                        'id': str(UUID.uuid1()),
                        'text': 'Meters',
                        'children': meter_nodes
                    }

                    chargegroup_names_nodes = []
                    for group in chargegroups_model:
                        chargegroup_names_nodes.append({
                            'id': str(UUID.uuid1()),
                            'text':group,
                            'leaf': True
                        })

                    chargegroups_node = {
                        'id': str(UUID.uuid1()),
                        'text': 'Charge Groups',
                        'children': chargegroup_names_nodes
                    }

                    utilbill_node = {
                        'id': str(UUID.uuid1()),
                        'text': service,
                        'children': [utility_node, ratestructure_node, chargegroups_node, meters_node]
                    }
                    tree.append(utilbill_node)

                # we want to return success to ajax call and then load the tree in page
                #return self.dumps({'success':True, 'reebill_structure':tree});
                # but the TreeLoader doesn't abide by the above ajax packet
                # TODO: 40161259 must return success field
                return self.dumps(tree);

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def insert_reebill_sibling_node(self, service, account, sequence, node_type, node_key, **args):
            if not service or not account or not sequence or not node_type or not node_key:
                raise ValueError("Bad Parameter Value")
            with DBSession(self.state_db) as session:
                reebill = self.reebill_dao.load_reebill(account, sequence)

                # node insertions are done by selecting a sibling node and creating
                # a new node based on the context of that selection.

                new_node = None
                if node_type == 'meter':
                    # in the case of inserting a meter, we simply need to know
                    # for which service the meter will be created since meters

                    new_meter = reebill.new_meter(service)
                    # both an actual and shadow register get created (actual, shadow)
                    new_registers = reebill.new_register(service, new_meter['identifier'])

                    register_nodes = [{
                        'id': str(UUID.uuid4()),
                        'leaf': True,
                        'text': new_registers[0]['identifier'],
                        'service': service,
                        'account': account, 
                        'sequence': sequence, 
                        'node_type': 'register',
                        'node_key': new_registers[0]['identifier'],
                    }]
                    new_node = {
                        'id': str(UUID.uuid4()),
                        'text': new_meter['identifier'],
                        'children': register_nodes,
                        'service': service,
                        'account': account, 
                        'sequence': sequence, 
                        'node_type': 'meter',
                        'node_key': new_meter['identifier'], 
                    }
                elif node_type == 'register':
                    # in the case of inserting a register, we need to find
                    # the parent of the currently selected register node
                    meter = reebill.meter_for_register(service, node_key)
                    new_registers = reebill.new_register(service, meter['identifier'])
                    new_node = {
                        'id': str(UUID.uuid4()),
                        'leaf': True,
                        'text': new_registers[0]['identifier'],
                        'service': service,
                        'account': account, 
                        'sequence': sequence, 
                        'node_type': 'register',
                        'node_key': new_registers[0]['identifier'],
                    }
                self.reebill_dao.save_reebill(reebill)
                return self.dumps({'success': True, 'node':new_node })

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    @json_exception
    def delete_reebill_node(self, service, account, sequence, node_type, node_key, text, **args):
        if not service or not account or not sequence or not node_type or not node_key or not text:
            raise ValueError("Bad Parameter Value")
        with DBSession(self.state_db) as session:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            if reebill:
                if node_type == 'meter':
                    # retrieve this meter based on node_key
                    reebill.delete_meter(service, node_key)
                elif node_type == 'register':
                    raise Exception("finish me")
            self.reebill_dao.save_reebill(reebill)
            return self.dumps({'success': True })

    @cherrypy.expose
    @random_wait
    @authenticate_ajax
    def update_reebill_node(self, service, account, sequence, node_type, node_key, text, **args):
        if not service or not account or not sequence or not node_type or not node_key or not text:
            raise ValueError("Bad Parameter Value")
        with DBSession(self.state_db) as session:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            updated_node = None
            if reebill:
                if node_type == 'meter':

                    # retrieve this meter based on node_key
                    reebill.set_meter_identifier(service, node_key, text)

                    # now that it has been changed, retrieve it with the new name
                    meter = reebill.meter(service, text)

                    # get the children of this meter
                    register_nodes = []
                    for register in meter['registers']:
                        if register['shadow'] is True:
                            continue
                        register_nodes.append({
                            'id': str(UUID.uuid1()),
                            'leaf': True,
                            'text': register['identifier'],
                            'service': service,
                            'account': account, 
                            'sequence': sequence, 
                            'node_type': 'register',
                            'node_key': register['identifier']
                        })
                    updated_node = {
                        'id': str(UUID.uuid1()),
                        'text': meter['identifier'],
                        'children': register_nodes,
                        'service': service,
                        'account': account, 
                        'sequence': sequence, 
                        'node_type': 'meter',
                        'node_key': meter['identifier'], 
                    }
                    # update the meter fields
                elif node_type == 'register':
                    # retrieve this meter based on node_key
                    reebill.set_register_identifier(service, node_key, text)

                    # now that it has been changed, retrieve it with the new name
                    register = reebill.actual_register(service, text)

                    updated_node = {
                        'id': str(UUID.uuid1()),
                        'leaf': True,
                        'text': register['identifier'],
                        'service': service,
                        'account': account, 
                        'sequence': sequence, 
                        'node_type': 'register',
                        'node_key': register['identifier'], 
                    }

            self.reebill_dao.save_reebill(reebill)
            return self.dumps({'success': True, 'node':updated_node})

        
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
