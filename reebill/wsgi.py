from os.path import dirname, realpath, join

from billing import init_config, init_model, init_logging

p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(path=p)
init_config(filename=p)
init_model()
from billing import config

import sys

import traceback
import json
import cherrypy
import os
import ConfigParser
from datetime import datetime
import inspect
import logging
import functools
import md5
from operator import itemgetter
from StringIO import StringIO
import pymongo
import mongoengine
from billing.skyliner.splinter import Splinter
from billing.skyliner import mock_skyliner
from billing.util import json_util as ju
from billing.util.dateutils import ISO_8601_DATETIME_WITHOUT_ZONE
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
from billing.exc import Unauthenticated, IssuedBillError

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
        try:
            return method(btb_instance, *args, **kwargs)
        except Exception as e:
            return btb_instance.handle_exception(e)
    return wrapper

def db_commit(method):
    '''Decorator for committing a database transaction when the method returns.
    This should be used only on methods that should be allowed to modify the
    database.
    '''
    @functools.wraps(method)
    def wrapper(btb_instance, *args, **kwargs):
        # because of the thread-local session, there's no need to do anything
        # before the method starts.
        try:
            result = method(btb_instance, *args, **kwargs)
        except:
            Session().rollback()
            raise
        Session().commit()
        return result
    return wrapper

class ReeBillWSGI(object):
    def __init__(self, config):
        self.config = config        
        self.logger = logging.getLogger('reebill')

        # create a NexusUtil
        self.nexus_util = NexusUtil(self.config.get('skyline_backend', 'nexus_web_host'))

        # load users database
        self.user_dao = UserDAO(**dict(self.config.items('usersdb')))

        # create an instance representing the database
        self.statedb_config = dict(self.config.items("statedb"))
        self.state_db = state.StateDB(logger=self.logger)

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
    @authenticate
    def index(self, **kwargs):
        raise cherrypy.HTTPRedirect('/billentry.html')

    @cherrypy.expose
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
    @authenticate_ajax
    @json_exception
    def getUsername(self, **kwargs):
        '''This returns the username of the currently logged-in user--not to be
        confused with the identifier. The identifier is a unique id but the
        username is not.'''
        return self.dumps({'success':True,
                'username': cherrypy.session['user'].username})

    @cherrypy.expose
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
    @authenticate_ajax
    @json_exception
    def get_next_account_number(self, **kwargs):
        '''Handles AJAX request for what the next account would be called if it
        were created (highest existing account number + 1--we require accounts
        to be numbers, even though we always store them as arbitrary
        strings).'''
        next_account = self.state_db.get_next_account_number()
        return self.dumps({'success': True, 'account': next_account})
            
    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def new_account(self, name, account, discount_rate, late_charge_rate,
            template_account, ba_addressee, ba_street, ba_city, ba_state,
            ba_postal_code, sa_addressee, sa_street, sa_city, sa_state,
            sa_postal_code, **kwargs):
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

        self.process.create_new_account(account, name, discount_rate,
                late_charge_rate, billing_address,
                service_address, template_account)

        # record account creation
        # (no sequence associated with this)
        journal.AccountCreatedEvent.save_instance(cherrypy.session['user'],
                account)

        # get next account number to send it back to the client so it
        # can be shown in the account-creation form
        next_account = self.state_db.get_next_account_number()
        return self.dumps({'success': True, 'nextAccount': next_account})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def roll(self, account, **kwargs):
        start_date = kwargs.get('start_date')
        if start_date is not None:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        reebill = self.process.roll_reebill(account, start_date=start_date)

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
    @authenticate_ajax
    @json_exception
    @db_commit
    def update_readings(self, account, sequence, **kwargs):
        self.process.update_reebill_readings(account, sequence)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def update_readings(self, account, sequence, **kwargs):
        self.process.update_reebill_readings(account, sequence)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def bindree(self, account, sequence, **kwargs):
        '''Puts energy from Skyline OLTP into shadow registers of the reebill
        given by account, sequence.'''
        if self.config.get('runtime', 'integrate_skyline_backend') is False:
            raise ValueError("OLTP is not integrated")
        if self.config.get('runtime', 'integrate_nexus') is False:
            raise ValueError("Nexus is not integrated")
        sequence = int(sequence)
        self.process.bind_renewable_energy(account, sequence)
        reebill = self.state_db.get_reebill(account, sequence)
        journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, sequence, reebill.version)
        return self.dumps({'success': True})


    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def upload_interval_meter_csv(self, account, sequence, csv_file,
            timestamp_column, timestamp_format, energy_column, energy_unit, register_identifier, **args):
        '''Takes an upload of an interval meter CSV file (cherrypy file upload
        object) and puts energy from it into the shadow registers of the
        reebill given by account, sequence.'''
        version = self.process.upload_interval_meter_csv(account, sequence,
                        csv_file,timestamp_column, timestamp_format,
                        energy_column, energy_unit, register_identifier, args)
        journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, sequence, version)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    # TODO clean this up and move it out of BillToolBridge
    # https://www.pivotaltracker.com/story/show/31404685
    def compute_bill(self, account, sequence, **args):
        '''Handler for the front end's "Compute Bill" operation.'''
        sequence = int(sequence)
        self.process.compute_reebill(account,sequence,'max')
        return self.dumps({'success': True})
    
        
    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def mark_utilbill_processed(self, utilbill, processed, **kwargs):
        '''Takes a utilbill id and a processed-flag and applies they flag to the bill '''
        utilbill, processed = int(utilbill), bool(int(processed))
        self.process.update_utilbill_metadata(utilbill, processed=processed)
        return self.dumps({'success': True})


    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def mark_reebill_processed(self, account, sequence , processed, **kwargs):
        '''Takes a reebill id and a processed-flag and applies that flag to the reebill '''
        account, processed, sequence = int(account), bool(int(processed)), int(sequence)
        self.process.update_sequential_account_info(account, sequence,
                processed=processed)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def mark_reebill_processed(self, account, sequence , processed, **kwargs):
        '''Takes a reebill id and a processed-flag and applies that flag to the reebill '''
        account, processed, sequence = int(account), bool(int(processed)), int(sequence)
        self.process.update_sequential_account_info(account, sequence,
                processed=processed)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def compute_utility_bill(self, utilbill_id, **args):
        self.process.compute_utility_bill(utilbill_id)
        return self.dumps({'success': True})
    
    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def has_utilbill_predecessor(self, utilbill_id, **args):
        predecessor=self.process.has_utilbill_predecessor(utilbill_id)
        return self.dumps({'success': True, 'has_predecessor':predecessor})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def refresh_charges(self, utilbill_id, **args):
        self.process.refresh_charges(utilbill_id)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def regenerate_rs(self, utilbill_id, **args):
        self.process.regenerate_uprs(utilbill_id)
        # NOTE utility bill is not automatically computed after rate
        # structure is changed. nor are charges updated to match.
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def render(self, account, sequence, **args):
        sequence = int(sequence)
        if not self.config.get('billimages', 'show_reebill_images'):
            return self.dumps({'success': False, 'code':2, 'errors': {'reason':
                    ('"Render" does nothing because reebill images have '
                    'been turned off.'), 'details': ''}})
        self.renderer.render(account, sequence,
            self.config.get("billdb", "billpath")+ "%s" % account,
            "%.5d_%.4d.pdf" % (account, sequence), False )
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def issue_and_mail(self, account, sequence, recipients, apply_corrections,
                       **kwargs):
        sequence = int(sequence)
        apply_corrections = (apply_corrections == 'true')
        result = self.process.issue_and_mail(cherrypy.session['user'], account,
                sequence, recipients, apply_corrections)
        print result
        return self.dumps(result)

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def issue_processed_and_mail(self, apply_corrections, **kwargs):
        apply_corrections = (apply_corrections == 'true')
        result = self.process.issue_processed_and_mail(cherrypy.session['user'],
                apply_corrections)
        return self.dumps(result)

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def mail(self, account, sequences, recipients, **kwargs):
        # Go from comma-separated e-mail addresses to a list of e-mail addresses
        recipient_list = [rec.strip() for rec in recipients.split(',')]

        # sequences will come in as a string if there is one element in post data.
        # If there are more, it will come in as a list of strings
        if type(sequences) is list:
            sequences = sorted(map(int, sequences))
        else:
            sequences = [int(sequences)]

        self.process.mail_reebills(account, sequences, recipient_list)

        # journal mailing of every bill
        for sequence in sequences:
            journal.ReeBillMailedEvent.save_instance(
                    cherrypy.session['user'], account, sequence, recipients)

        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def listAccounts(self, **kwargs):
        accounts = self.state_db.listAccounts()
        rows = [{'account': account, 'name': full_name} for account,
                full_name in zip(accounts,
                self.process.full_names_of_accounts(accounts))]
        return self.dumps({'success': True, 'rows':rows})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def retrieve_account_status(self, start, limit ,**kwargs):
        '''Handles AJAX request for "Account Processing Status" grid in
        "Accounts" tab.'''
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

        count, rows = self.process.list_account_status(start,limit,filtername,sortcol,sortreverse)

        cherrypy.session['user'].preferences['default_account_sort_field'] = sortcol
        cherrypy.session['user'].preferences['default_account_sort_direction'] = sortdir
        self.user_dao.save_user(cherrypy.session['user'])

        return self.dumps({'success': True, 'rows':rows, 'results':count})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def reebill_details_xls(self, begin_date=None, end_date=None, **kwargs):
        '''
        Responds with an excel spreadsheet containing all actual charges, total
        energy and rate structure for all utility bills for the given account,
        or every account (1 per sheet) if 'account' is not given,
        '''
        exporter = excel_export.Exporter(self.state_db, self.reebill_dao)

        # write excel spreadsheet into a StringIO buffer (file-like)
        buf = StringIO()
        exporter.export_reebill_details(buf)

        # set MIME type for file download
        cherrypy.response.headers['Content-Type'] = 'application/excel'
        cherrypy.response.headers['Content-Disposition'] = \
                'attachment; filename=%s.xls'%datetime.now().strftime("%Y%m%d")
        return buf.getvalue()

    @cherrypy.expose
    @authenticate
    @json_exception
    def excel_export(self, account=None, start_date=None, end_date=None, **kwargs):
        '''
        Responds with an excel spreadsheet containing all actual charges for all
        utility bills for the given account, or every account (1 per sheet) if
        'account' is not given, or all utility bills for the account(s) filtered
        by time, if 'start_date' and/or 'end_date' are given.
        '''
        if account is not None:
            spreadsheet_name = account + '.xls'
        else:
            spreadsheet_name = 'all_accounts.xls'

        exporter = excel_export.Exporter(self.state_db, self.reebill_dao)

        # write excel spreadsheet into a StringIO buffer (file-like)
        buf = StringIO()
        exporter.export_account_charges(buf, account, start_date=start_date,
                        end_date=end_date)

        # set MIME type for file download
        cherrypy.response.headers['Content-Type'] = 'application/excel'
        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % spreadsheet_name

        return buf.getvalue()

    @cherrypy.expose
    @authenticate
    @json_exception
    def excel_energy_export(self, account=None, **kwargs):
        '''
        Responds with an excel spreadsheet containing all actual charges, total
        energy and rate structure for all utility bills for the given account,
        or every account (1 per sheet) if 'account' is not given,
        '''
        if account is not None:
            spreadsheet_name = account + '.xls'
        else:
            spreadsheet_name = 'brokerage_accounts.xls'

        exporter = excel_export.Exporter(self.state_db, self.reebill_dao)

        # write excel spreadsheet into a StringIO buffer (file-like)
        buf = StringIO()
        exporter.export_energy_usage(buf, account)

        # set MIME type for file download
        cherrypy.response.headers['Content-Type'] = 'application/excel'
        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % spreadsheet_name

        return buf.getvalue()

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
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
        if xaction == "read":
            return json.dumps({'success': True,
                    'rows': self.process.get_rsis_json(utilbill_id), })

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
                rsi_binding = self.process.update_rsi(utilbill_id, id, row)

                # re-add "id" field which was removed above (using new
                # rsi_binding)
                # TODO this is ugly; find a better way
                row['id'] = rsi_binding

        if xaction == "create":
            self.process.add_rsi(utilbill_id)

        if xaction == "destroy":
            if type(rows) is unicode: rows = [rows]
            for row in rows:
                self.process.delete_rsi(utilbill_id, row)

        rsis_json = self.process.get_rsis_json(utilbill_id)
        return json.dumps({'success': True, 'rows': rsis_json,
                'total':len(rsis_json)})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def payment(self, xaction, account, **kwargs):
        if xaction == "read":
            payments = self.state_db.payments(account)
            return self.dumps({'success': True,
                'rows': [payment.to_dict() for payment in payments]})
        elif xaction == "update":
            rows = json.loads(kwargs["rows"])
            # single edit comes in not in a list
            if type(rows) is dict: rows = [rows]
            # process list of edits
            for row in rows:
                self.process.update_payment(
                    row['id'],
                    row['date_applied'],
                    row['description'],
                    row['credit'],
                )
            return self.dumps({'success':True})
        elif xaction == "create":
            # date applied is today by default (can be edited later)
            today = datetime.utcnow().date()
            new_payment = self.process.create_payment(account,
                    today, "New Entry", 0)
            # Payment object lacks "id" until row is inserted in database
            Session().flush()
            return self.dumps({'success':True, 'rows':[new_payment.to_dict()]})
        elif xaction == "destroy":
            rows = json.loads(kwargs["rows"])
            # single delete comes in not in a list
            if type(rows) is int: rows = [rows]
            for oid in rows:
                self.process.delete_payment(oid)
            return self.dumps({'success':True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def reebill(self, xaction, start, limit, account, sort = u'sequence',
            dir=u'DESC', **kwargs):
        '''Handles AJAX requests for reebill grid data.'''
        start, limit = int(start), int(limit)
        if xaction == "read":
            # this is inefficient but length is always <= 120 rows
            rows = sorted(self.process.get_reebill_metadata_json(account),
                    key=itemgetter(sort))
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
    @authenticate_ajax
    @json_exception
    @db_commit
    def issuable(self, xaction, **kwargs):
        '''Return a list of the issuable reebills'''
        if xaction == 'read':
            start = int(kwargs['start'])
            limit = int(kwargs['limit'])
            sort = kwargs['sort']
            direction = kwargs['dir']

            try:
                allowable_diff = cherrypy.session['user'].preferences['difference_threshold']
            except:
                allowable_diff = UserDAO.default_user.preferences['difference_threshold']

            issuable_reebills = self.process.get_issuable_reebills_dict()
            for reebill_info in issuable_reebills:
                reebill_info['id'] = reebill_info['account'],
                reebill_info['difference'] = abs(reebill_info['reebill_total']-reebill_info['util_total'])
                if reebill_info['processed'] == True:
                    reebill_info['group'] = 'Processed ReeBills'
                elif reebill_info['difference'] < allowable_diff:
                    reebill_info['group'] = 'ReeBills with Matching Totals'
                else:
                    reebill_info['group'] = 'ReeBills with Non Matching Totals'

            # sort by 'sort' column, then by 'group' to
            # get rows sorted by 'sort' column within groups
            issuable_reebills.sort(key=itemgetter(sort),
                    reverse = (direction == 'DESC'))
            def group_order(row):
                result = ['Processed ReeBills', 'ReeBills with Matching Totals',
                          'ReeBills with Non Matching Totals'].index(
                        row['group'])
                assert result >= 0
                return result
            issuable_reebills.sort(key=group_order)

            return self.dumps({'success': True,
                               'rows': issuable_reebills[start:start+limit],
                               'total': len(issuable_reebills)})
        elif xaction == 'update':
            row = json.loads(kwargs["rows"])
            self.process.update_bill_email_recipient(row['account'],
                                                     row['sequence'],
                                                     row['mailto'])
            return self.dumps({'success':True})
            
    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def delete_reebill(self, account, sequences, **kwargs):
        '''Delete the unissued version of each reebill given, assuming that one
        exists.'''
        if type(sequences) is list:
            sequences = map(int, sequences)
        else:
            sequences = [int(sequences)]
        for sequence in sequences:
            deleted_version = self.process.delete_reebill(account, sequence)
        # deletions must all have succeeded, so journal them
        for sequence in sequences:
            journal.ReeBillDeletedEvent.save_instance(cherrypy.session['user'],
                    account, sequence, deleted_version)

        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def new_reebill_version(self, account, sequence, **args):
        '''Creates a new version of the given reebill (only one bill, not all
        successors as in original design).'''
        sequence = int(sequence)
        # Process will complain if new version is not issued
        version = self.process.new_version(account, sequence)

        journal.NewReebillVersionEvent.save_instance(cherrypy.session['user'],
                account, sequence, version)
        # NOTE ReebillBoundEvent is no longer saved in the journal because
        # new energy data are not retrieved unless the user explicitly
        # chooses to do it by clicking "Bind RE&E"

        # client doesn't do anything with the result (yet)
        return self.dumps({'success': True, 'sequences': [sequence]})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def account_info(self, account, sequence, **args):
        '''Handles AJAX request for "Sequential Account Information form.
        '''
        sequence = int(sequence)
        reebill = self.state_db.get_reebill(account, sequence)
        return self.dumps({
            'success': True,
            'billing_address': reebill.billing_address.to_dict(),
            'service_address': reebill.service_address.to_dict(),
            'discount_rate': reebill.discount_rate,
            'late_charge_rate': reebill.late_charge_rate,
        })

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
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

        self.process.update_sequential_account_info(account, sequence,
                discount_rate=discount_rate,
                late_charge_rate=late_charge_rate,
                ba_addressee=ba_addressee, ba_street=ba_street,
                ba_city=ba_city, ba_state=ba_state,
                ba_postal_code=ba_postal_code,
                sa_addressee=sa_addressee, sa_street=sa_street,
                sa_city=sa_city, sa_state=sa_state,
                sa_postal_code=sa_postal_code)
        return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def get_reebill_services(self, account, sequence, **args):
        # TODO: delete this? is it ever used?
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
            'services': [],
            'suspended_services': reebill.suspended_services
        })

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def actualCharges(self, utilbill_id, xaction, reebill_sequence=None,
            reebill_version=None, **kwargs):
        charges_json = self.process.get_utilbill_charges_json(
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
            self.process.update_charge(utilbill_id, rsi_binding, row)

        if xaction == "create":
            row = json.loads(kwargs["rows"])[0]
            assert isinstance(row, dict)
            group_name = row['group']
            self.process.add_charge(utilbill_id, group_name)

        if xaction == "destroy":
            rsi_binding = json.loads(kwargs["rows"])[0]
            self.process.delete_charge(utilbill_id, rsi_binding)

        charges_json = self.process.get_utilbill_charges_json(utilbill_id)
        return self.dumps({'success': True, 'rows': charges_json,
                            'total':len(charges_json)})


    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def hypotheticalCharges(self, xaction, service, account, sequence, **kwargs):
        sequence = int(sequence)
        if not xaction == "read":
            raise NotImplementedError('Cannot create, edit or destroy charges'
                                      ' from this grid.')
        charges=self.process.get_hypothetical_matched_charges(
                account, sequence)
        return self.dumps({'success': True, 'rows': charges,
                           'total':len(charges)})


    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
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

        if xaction == 'read':
            # get dictionaries describing all registers in all utility bills
            registers_json = self.process.get_registers_json(utilbill_id,
                                            reebill_sequence=reebill_sequence,
                                            reebill_version=reebill_version)

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
                self.process.new_register(utilbill_id, row,
                                        reebill_sequence=reebill_sequence,
                                        reebill_version=reebill_version)


            # get dictionaries describing all registers in all utility bills
            registers_json = self.process.get_registers_json(utilbill_id,
                                            reebill_sequence=reebill_sequence,
                                            reebill_version=reebill_version)

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
                new_meter_id, new_reg_id = self.process.update_register(
                        utilbill_id, orig_meter_id, orig_reg_id,
                        row)

                # if this row was selected before, tell the client it should
                # still be selected, specifying the row by its new "id"
                if kwargs.get('current_selected_id') == '%s/%s/%s' % (
                        utilbill_id, orig_meter_id, orig_reg_id):
                    result['current_selected_id'] = '%s/%s/%s' % (utilbill_id,
                            new_meter_id, new_reg_id)

            registers_json = self.process.get_registers_json(utilbill_id,
                                            reebill_sequence=reebill_sequence,
                                            reebill_version=reebill_version)
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
            self.process.delete_register(utilbill_id, orig_meter_id, orig_reg_id,
                                            reebill_sequence=reebill_sequence,
                                            reebill_version=reebill_version)

            # NOTE there is no "current_selected_id" because the formerly
            # selected row was deleted
            registers_json = self.process.get_registers_json(utilbill_id,
                                            reebill_sequence=reebill_sequence,
                                            reebill_version=reebill_version)
            result = {'success': True, "rows": registers_json,
                    'total': len(registers_json)}

        return self.dumps(result)

#
    ################

    ################
    # Handle utility bill upload

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def upload_utility_bill(self, account, service, begin_date, end_date,
            total_charges, file_to_upload, **args):
        '''Handles AJAX request to create a new utility bill from the "Upload
        Utility Bill" form. If 'file_to_upload' None, the utility bill state
        will be 'SkylineEstimated'; otherwise it will be 'Complete'. Currently,
        there is no way to specify a 'UtilityEstimated' state in the UI.'''
        # pre-process parameters
        service = service.lower()
        total_charges_as_float = float(total_charges)
        begin_date_as_date = datetime.strptime(begin_date, '%Y-%m-%d').date()
        end_date_as_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        UtilBill.validate_utilbill_period(begin_date_as_date,
                end_date_as_date)

        # NOTE 'file_to_upload.file' is always a CherryPy object; if no
        # file was specified, 'file_to_upload.file' will be None

        self.process.upload_utility_bill(account, service,
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
    @authenticate_ajax
    @json_exception
    def journal(self, xaction, account, **kwargs):
        if xaction == "read":
            journal_entries = self.journal_dao.load_entries(account)
            return self.dumps({'success': True, 'rows':journal_entries})

        # TODO: 20493983 eventually allow admin user to override and edit
        return self.dumps({'success':False, 'errors':{'reason':'Not supported'}})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
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
    @authenticate_ajax
    @json_exception
    def last_utilbill_end_date(self, account, **kwargs):
        '''Returns date of last utilbill.'''
        the_date = self.state_db.last_utilbill_end_date(account)
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
    @authenticate_ajax
    @json_exception
    @db_commit
    # TODO: 25650643 explicit params - security risk and other
    def utilbill_grid(self, xaction, **kwargs):
        '''Handles AJAX requests to read and write data for the grid of utility
        bills. Ext-JS provides the 'xaction' parameter, which is "read" when it
        wants to read data and "update" when a cell in the grid was edited.'''
        if xaction == 'read':
            account = kwargs['account']
            start, limit = int(kwargs['start']), int(kwargs['limit'])
            rows, total_count = self.process.get_all_utilbills_json(
                    account, start, limit)
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

            self.process.update_utilbill_metadata(row['id'], **update_args)

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
                        .delete_utility_bill_by_id(utilbill_id)
                journal.UtilBillDeletedEvent.save_instance(
                        cherrypy.session['user'], account,
                        utilbill.period_start, utilbill.period_end,
                        utilbill.service, deleted_path)
            return self.dumps({'success': True})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def getDifferenceThreshold(self, **kwargs):
        threshold = cherrypy.session['user'].preferences['difference_threshold']
        return self.dumps({'success':True, 'threshold': threshold})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    @db_commit
    def setDifferenceThreshold(self, threshold, **kwargs):
        threshold=float(threshold)
        if not threshold or threshold <= 0:
            return self.dumps({'success':False, 'errors':"Threshold of %s is not valid." % str(threshold)})
        cherrypy.session['user'].preferences['difference_threshold'] = threshold
        self.user_dao.save_user(cherrypy.session['user'])
        return self.dumps({'success':True})
    
    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def getFilterPreference(self, **kwargs):
        filtername = cherrypy.session['user'].preferences.get('filtername', '')
        return self.dumps({'success':True, 'filtername': filtername})

    @cherrypy.expose
    @authenticate_ajax
    @json_exception
    def setFilterPreference(self, filtername, **kwargs):
        if filtername is None:
            return self.dumps({'success':False, 'errors':"Filter '%s' is not valid." % str(filtername)})
        cherrypy.session['user'].preferences['filtername'] = filtername
        self.user_dao.save_user(cherrypy.session['user'])
        return self.dumps({'success':True})



if __name__ == '__main__':
    class Root(object):
        pass
    root = Root()
    root.reebill = ReeBillWSGI(config)
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
        'server.socket_host': root.reebill.config.get("http", "socket_host"),
        'server.socket_port': root.reebill.config.get("http", "socket_port")})
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, False)
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, True,
            stream=sys.stdout)
    cherrypy.quickstart(root, config=local_conf)
else:
    # WSGI Mode
    cherrypy.config.update({
        'environment': 'embedded',
        'tools.sessions.on': True,
        'tools.sessions.timeout': 240
    })

    bridge = ReeBillWSGI(config)
    application = cherrypy.Application(bridge, script_name=None, config=None)
