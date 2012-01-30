#!/usr/bin/python
'''
File: bill_tool_bridge.py
Description: Allows bill tool to be invoked as a CGI
'''
import sys
import traceback
import json
import cherrypy
import jinja2, os
import string
import ConfigParser
from datetime import datetime
from datetime import date
import itertools as it
from decimal import *

# uuid collides with locals so both module and locals are renamed
import uuid as UUID
import inspect
import logging

from billing.processing import process
from billing.processing import state
from billing.processing import fetch_bill_data as fbd
from billing.reebill import render
from billing.reebill import journal
from billing.processing.billupload import BillUpload
from billing import nexus_util as nu
from billing.nexus_util import NexusUtil
from billing import bill
from billing import json_util as ju
from billing.reebill import bill_mailer
from billing import mongo
import billing.processing.rate_structure as rs
from billing.processing import db_objects
from billing.users import UserDAO, User
from billing import dateutils
from skyliner import splinter
from skyliner.skymap.monguru import Monguru

sys.stdout = sys.stderr
import pprint
pp = pprint.PrettyPrinter(indent=4)

# TODO 11454025 rename to ProcessBridge or something
class BillToolBridge:
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
    - commit the session.
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
            self.config.add_section('journaldb')
            self.config.set('journaldb', 'host', 'localhost')
            self.config.set('journaldb', 'port', '27017')
            self.config.set('journaldb', 'database', 'skyline')
            self.config.set('journaldb', 'collection', 'journal')
            self.config.add_section('http')
            self.config.set('http', 'socket_port', '8185')
            self.config.set('http', 'socket_host', '10.0.0.250')
            self.config.add_section('rsdb')
            #self.config.set('rsdb', 'rspath', '[root]db/skyline/ratestructure/')
            self.config.set('rsdb', 'host', 'localhost')
            self.config.set('rsdb', 'port', '27017')
            self.config.set('rsdb', 'database', 'skyline')
            self.config.set('rsdb', 'collection', 'reebills')
            self.config.add_section('billdb')
            self.config.set('billdb', 'utilitybillpath', '[root]db/skyline/utilitybills/')
            self.config.set('billdb', 'billpath', '[root]db/skyline/bills/')
            self.config.set('billdb', 'host', 'localhost')
            self.config.set('billdb', 'port', '27017')
            self.config.set('billdb', 'database', 'skyline')
            self.config.set('billdb', 'collection', 'reebills')
            self.config.add_section('statedb')
            self.config.set('statedb', 'host', 'localhost')
            self.config.set('statedb', 'database', 'skyline')
            self.config.set('statedb', 'user', '[your mysql user]')
            self.config.set('statedb', 'password', '[your mysql password]')
            self.config.add_section('usersdb')
            self.config.set('usersdb', 'host', 'localhost')
            self.config.set('usersdb', 'database', 'skyline')
            self.config.set('usersdb', 'collection', 'users')
            self.config.set('usersdb', 'user', 'dev')
            self.config.set('usersdb', 'password', 'dev')
            self.config.add_section('mailer')
            self.config.set('mailer', 'smtp_host', 'smtp.gmail.com')
            self.config.set('mailer', 'smtp_port', '587')
            self.config.set('mailer', 'originator', 'jwatson@skylineinnovations.com')
            self.config.set('mailer', 'from', '"Jules Watson" <jwatson@skylineinnovations.com>')
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

            # log file info
            self.config.add_section('log')
            self.config.set('log', 'log_file_name', DEFAULT_LOG_FILE_NAME)
            self.config.set('log', 'log_format', DEFAULT_LOG_FORMAT)

            # bill image rendering
            self.config.add_section('billimages')
            self.config.set('billimages', 'bill_image_directory', DEFAULT_BILL_IMAGE_DIRECTORY)

            # reebill pdf rendering
            self.config.add_section('reebillrendering')
            self.config.set('reebillrendering', 'temp_directory', DEFAULT_RENDERING_TEMP_DIRECTORY)


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

        # load users database
        self.user_dao = UserDAO(dict(self.config.items('usersdb')))

        # create an instance representing the database
        statedb_config_section = self.config.items("statedb")
        self.state_db = state.StateDB(dict(statedb_config_section)) 

        # create one BillUpload object to use for all BillUpload-related methods
        self.billUpload = BillUpload(self.config, self.logger)

        # create a MongoReeBillDAO
        billdb_config_section = self.config.items("billdb")
        self.reebill_dao = mongo.ReebillDAO(dict(billdb_config_section))

        # create a RateStructureDAO
        rsdb_config_section = self.config.items("rsdb")
        self.ratestructure_dao = rs.RateStructureDAO(dict(rsdb_config_section))

        # create a JournalDAO
        journaldb_config_section = self.config.items("journaldb")
        self.journal_dao = journal.JournalDAO(dict(journaldb_config_section))

        # create one Process object to use for all related bill processing
        self.process = process.Process(self.config, self.state_db, self.reebill_dao, self.ratestructure_dao)

        # create a ReebillRenderer
        self.renderer = render.ReebillRenderer(dict(self.config.items('reebillrendering')), self.logger)

        # configure mailer
        # TODO: pass in specific configs?
        bill_mailer.config = self.config

        # create on RateStructureDAO to user for all ratestructure queries
        rsdb_config_section = self.config.items("rsdb")
        self.ratestructure_dao = rs.RateStructureDAO(dict(rsdb_config_section))

        # determine whether authentication is on or off
        self.authentication_on = self.config.getboolean('authentication', 'authenticate')

        # print a message in the log--TODO include the software version
        self.logger.info('BillToolBridge initialized')
    
    @cherrypy.expose
    def index(self):
        print >> sys.stderr, 'index was called'
        if self.check_authentication():
            raise cherrypy.HTTPRedirect('/billentry.html')
        else:
            raise cherrypy.HTTPRedirect('/login.html')

#    @cherrypy.expose
#    def generate_reconciliation_report(self):
#        '''Reconciliation report for reebills.'''
#        try:
#            # file where the report goes: json format
#            output_file = open(os.path.join(os.path.dirname(
#                os.path.realpath(__file__)), 'reconciliation_report.json'), 'w')
#
#            session = self.state_db.session()
#            monguru = Monguru('tyrell', 'dev') # TODO don't hard-code
#
#            for account in self.state_db.listAccounts(session):
#                # TODO don't hard-code
#                install = splinter.Splinter('http://duino-drop.appspot.com/',
#                        "tyrell", "dev").get_install_obj_for(nu.NexusUtil() \
#                        .olap_id(account))
#                for sequence in self.state_db.listSequences(session, account):
#                    print 'reconciliation report for %s-%s' % (account, sequence)
#                    reebill = self.reebill_dao.load_reebill(account, sequence)
#                    try:
#                        # get energy from the bill
#                        bill_therms = reebill.total_renewable_energy
#
#                        # OLTP is more accurate but way too slow to generate this report in a reasonable time
#                        #oltp_therms = sum(install.get_energy_consumed_by_service(
#                                #day, 'service type is ignored!', [0,23]) for day
#                                #in dateutils.date_generator(reebill.period_begin,
#                                #reebill.period_end))
#                        
#                        # now get energy from OLAP: start by adding up energy
#                        # sold for each day, whether billable or not (assuming
#                        # that periods of missing data from OLTP will have
#                        # contributed 0 to the OLAP aggregate)
#                        olap_btu = 0
#                        for day in dateutils.date_generator(reebill.period_begin,
#                                reebill.period_end):
#                            olap_btu += monguru.get_data_for_day(install,
#                                    day).energy_sold
#
#                        # now find out how much energy was unbillable by
#                        # subtracting energy sold during all unbillable
#                        # annotations from the previous total
#                        for anno in [anno for anno in install.get_annotations() if
#                                anno.unbillable]:
#                            # i think annotation datetimes are in whole hours
#                            # and their ends are exclusive
#                            for hour in sky_handlers.cross_range(anno._from, anno._to):
#                                hourly_doc = monguru.get_data_for_hour(install, hour)
#                                olap_btu -= hourly_doc.energy_sold
#                        olap_therms = olap_btu / 100000
#                    except Exception as error:
#                        output_file.write(ju.dumps({
#                            'success': False,
#                            'account': account,
#                            'sequence': sequence,
#                            'error': '%s\n%s' % (error, traceback.format_exc()
#                        }))
#                    else:
#                        output_file.write(ju.dumps({
#                            'success': True,
#                            'account': account,
#                            'sequence': sequence,
#                            'bill_therms': bill_therms,
#                            'olap_therms': olap_therms
#                        }))
#                    output_file.write('\n')
#        except Exception as e:
#            print >> sys.stderr, e, traceback.format_exc()
#            self.logger.error(e, traceback.format_exc())
#            raise

    @cherrypy.expose
    def reconciliation(self):
        '''Show reconciliation report.'''
        return open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'reconciliation_report.json')).read().replace('\n', '<p>')

#    @cherrypy.expose
#    def reconciliation_for_account(self, account, **kwargs):
#        '''Returns JSON representing the reconciliation data for all reebills
#        belonging to a single customer account.'''
#        try:
#            result = []
#            olap_id = nu.NexusUtil().olap_id(account)
#            install = splinter.Splinter('http://duino-drop.appspot.com/', "tyrell", "dev") \
#                    .get_install_obj_for(olap_id)
#            monguru = Monguru('tyrell', 'dev') # TODO don't hard-code
#            session = self.state_db.session()
#            for sequence in self.state_db.listSequences(session, account):
#                reebill = self.reebill_dao.load_reebill(account, sequence)
#                print '%s-%s' % (account, sequence)
#                try:
#                    # get energy from the bill
#                    bill_therms = reebill.total_renewable_energy
#                    #oltp_therms = sum(install.get_energy_consumed_by_service(
#                            #day, 'service type is ignored!', [0,23]) for day
#                            #in dateutils.date_generator(reebill.period_begin,
#                            #reebill.period_end))
#
#                    # OLTP is more accurate but way too slow to generate this report in a reasonable time
#                    
#                    # now get energy from OLAP: start by adding up energy
#                    # sold for each day, whether billable or not (assuming
#                    # that periods of missing data from OLTP will have
#                    # contributed 0 to the OLAP aggregate)
#                    olap_btu = 0
#                    for day in dateutils.date_generator(reebill.period_begin,
#                            reebill.period_end):
#                        olap_btu += monguru.get_data_for_day(install,
#                                day).energy_sold
#
#                    # now find out how much energy was unbillable by
#                    # subtracting energy sold during all unbillable
#                    # annotations from the previous total
#                    # TODO worry about floating-point errors
#                    for anno in [anno for anno in install.get_annotations() if
#                            anno.unbillable]:
#                        # i think annotation datetimes are in whole hours
#                        # and their ends are exclusive
#                        for hour in sky_handlers.cross_range(anno._from, anno._to):
#                            hourly_doc = monguru.get_data_for_hour(install, hour)
#                            olap_btu -= hourly_doc.energy_sold
#                    olap_therms = olap_btu / 100000.
#                except Exception as error:
#                    result.append({'sequence': sequence, 'success': False,
#                        'error': error})
#                else:
#                    result.append({'sequence': sequence, 'success': True,
#                        'bill_therms': bill_therms, 'olap_therms':
#                        olap_therms})
#            return ju.dumps(result)
#        except Exception as e:
#            print >> sys.stderr, e, traceback.format_exc()
#            self.logger.error(e, traceback.format_exc())
#            raise
        
    ###########################################################################
    # authentication functions

    @cherrypy.expose
    def login(self, identifier, rememberme='off', **kwargs):
        user = self.user_dao.load_user(identifier)
        if user is None:
            self.logger.info(('login attempt failed: identifier "%s"'
                ', remember me: %s') % (identifier, rememberme))
            raise cherrypy.HTTPRedirect("/login.html")

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
        self.logger.info(('user "%s" logged in: remember '
            'me: "%s" type is %s') % (identifier, rememberme,
            type(rememberme)))
        raise cherrypy.HTTPRedirect("/billentry.html")

    def check_authentication(self):
        '''Decorator to check authentication for HTTP request functions:
        returns True if the user is logged in; if not, sets the HTTP status
        code to 401 and returns False. Does not redirect to the login page,
        because it gets called in AJAX requests, which must return actual data
        instead of a redirect.'''
        try:
            # if authentication is turned off, skip the check and make sure the
            # session contains default data
            if not self.authentication_on:
                if 'user' not in cherrypy.session:
                    cherrypy.session['user'] = UserDAO.default_user
                return True
            if 'user' not in cherrypy.session:
                self.logger.info("Non-logged-in user was denied access to: %s" % \
                        inspect.stack()[1][3])
                # TODO: 19664107
                # 401 = unauthorized--can't reply to an ajax call with a redirect
                cherrypy.response.status = 401
                return False
            return True
        except Exception as e:
            print >> sys.stderr, e, traceback.format_exc()
            self.logger.error(e, traceback.format_exc())
            raise
    
    @cherrypy.expose
    def getUsername(self, **kwargs):
        '''This returns the username of the currently logged-in user--not to be
        confused with the identifier. The identifier is a unique id but the
        username is not.'''
        self.check_authentication()
        try:
            return ju.dumps({'success':True,
                    'username': cherrypy.session['user'].username})
        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e),
                    'details':traceback.format_exc()}})

    @cherrypy.expose
    def logout(self):
        if 'user' in cherrypy.session:
            self.logger.info('user "%s" logged out' % (cherrypy.session['user'].username))
            del cherrypy.session['user']
        raise cherrypy.HTTPRedirect('/login.html')

    ###########################################################################
    # bill processing

    # TODO: do this on a per service basis 18311877
    @cherrypy.expose
    def copyactual(self, account, sequence, **args):
        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)
            self.process.copy_actual_charges(reebill)
            self.reebill_dao.save_reebill(reebill)

            return json.dumps({'success': True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def new_account(self, name, account, discount_rate, template_account, **args):
        self.check_authentication()
        try:
            session = None
            if not name or not account or not discount_rate or not template_account:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

            customer = self.process.create_new_account(session, account, name, discount_rate, template_account)

            reebill = self.reebill_dao.load_reebill(account, 0)

            # record the successful completion
            self.journal_dao.journal(customer.account, 0, "Newly created")

            self.process.roll_bill(session, reebill)
            self.reebill_dao.save_reebill(reebill)
            self.journal_dao.journal(account, 0, "ReeBill rolled")

            session.commit()

            return json.dumps({'success': True})

        except Exception as e:
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def roll(self, account, sequence, **args):
        self.check_authentication()
        try:
            session = None
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            session = self.state_db.session()
            self.process.roll_bill(session, reebill)
            self.reebill_dao.save_reebill(reebill)
            session.commit()
            self.journal_dao.journal(account, sequence, "ReeBill rolled")
            return json.dumps({'success': True})
        except Exception as e:
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def pay(self, account, sequence, **args):
        self.check_authentication()
        try:
            session = None
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")
            reebill = self.reebill_dao.load_reebill(account, sequence)

            session = self.state_db.session()
            self.process.pay_bill(session, reebill)
            session.commit()
            self.reebill_dao.save_reebill(reebill)
            return json.dumps({'success': True})

        except Exception as e:
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def bindree(self, account, sequence, **args):
        self.check_authentication()
        from billing.processing import fetch_bill_data as fbd
        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")
            reebill = self.reebill_dao.load_reebill(account, sequence)

            fbd.fetch_bill_data(
                "http://duino-drop.appspot.com/",
                nu.NexusUtil().olap_id(account),
                reebill
            )

            self.reebill_dao.save_reebill(reebill)

            self.journal_dao.journal(account, sequence, "RE&E Bound")

            return json.dumps({'success': True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def bindrs(self, account, sequence, **args):
        self.check_authentication()
        session = None
        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

            reebill = self.reebill_dao.load_reebill(account, sequence)
            prior_reebill = self.reebill_dao.load_reebill(account, int(sequence)-1)

            self.process.calculate_reperiod(reebill)

            self.process.bind_rate_structure(reebill)

            self.process.pay_bill(session, reebill)

            # TODO: 22726549 hack to ensure the computations from bind_rs come back as decimal types
            self.reebill_dao.save_reebill(reebill)
            reebill = self.reebill_dao.load_reebill(account, sequence)

            self.process.sum_bill(session, prior_reebill, reebill)

            # TODO: 22726549  hack to ensure the computations from bind_rs come back as decimal types
            self.reebill_dao.save_reebill(reebill)
            reebill = self.reebill_dao.load_reebill(account, sequence)
            self.process.calculate_statistics(prior_reebill, reebill)

            self.reebill_dao.save_reebill(reebill)

            session.commit()

            return json.dumps({'success': True})
        except Exception as e:
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def render(self, account, sequence, **args):
        self.check_authentication()
        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")
            reebill = self.reebill_dao.load_reebill(account, sequence)
            # TODO 22598787 - branch awareness
            self.renderer.render(reebill, 
                self.config.get("billdb", "billpath")+ "%s/%.4d.pdf" % (account, int(sequence)),
                "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
                None,
            )
        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def mail(self, account, sequences, recipients, **args):
        self.check_authentication()
        try:
            session = None
            if not account or not sequences or not recipients:
                raise ValueError("Bad Parameter Value")

            # look up this value and fail early if there is something wrong
            # with the session.
            current_user = cherrypy.session['user'].username
            session = self.state_db.session()

            # sequences will come in as a string if there is one element in post data. 
            # If there are more, it will come in as a list of strings
            if type(sequences) is not list: sequences = [sequences]
            # acquire the most recent reebill from the sequence list and use
            # its values for the merge
            sequences = [sequence for sequence in sequences]
            # sequences is [u'17']
            all_bills = [self.reebill_dao.load_reebill(account, sequence) for
                    sequence in sequences]

            # set issue date 
            for reebill in all_bills:
                self.process.issue(reebill.account, reebill.sequence)
                self.process.issue_to_customer(session, reebill.account,
                        reebill.sequence)

            #  TODO: 21305875  Do this until reebill is being passed around
            #  problem is all_bills is not reloaded after .issue and
            #  .issue_to_customer
            all_bills = [self.reebill_dao.load_reebill(account, sequence) for
                    sequence in sequences]

            # render all the bills
            for reebill in all_bills:
                self.renderer.render(reebill, 
                    self.config.get("billdb", "billpath")+ "%s/%s.pdf" % (
                        reebill.account, reebill.sequence),
                    "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
                    None,
                )
                

            # the last element
            most_recent_bill = all_bills[-1]

            bill_file_names = ["%s.pdf" % sequence for sequence in sequences]
            bill_dates = ["%s" % (b.period_end) for b in all_bills]
            bill_dates = ", ".join(bill_dates)

            merge_fields = {}
            merge_fields["sa_street1"] = most_recent_bill.service_address["sa_street1"]
            merge_fields["balance_due"] = most_recent_bill.balance_due.quantize(Decimal("0.00"))
            merge_fields["bill_dates"] = bill_dates
            merge_fields["last_bill"] = bill_file_names[-1]

            bill_mailer.mail(recipients, merge_fields,
                    os.path.join(self.config.get("billdb", "billpath"),
                        account), bill_file_names);


            # set issued to customer flagnflict.
            # Commit bill
            for reebill in all_bills:
                self.journal_dao.journal(reebill.account, reebill.sequence,
                        "Mailed to %s by %s" % (recipients, current_user))
                self.process.issue_to_customer(session, reebill.account,
                        reebill.sequence)
                self.process.commit_reebill(session, reebill.account,
                        reebill.sequence)

            session.commit()
            return json.dumps({'success': True})

        except Exception as e:
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e),
                    'details':traceback.format_exc()}})


    def full_names_of_accounts(self, accounts):
        '''Given a list of account numbers (as strings), returns a list
        containing the "full name" of each account, each of which is of the
        form "accountnumber - codename - casualname - primus". Names that do not
        exist for a given account are skipped.'''
        all_accounts_all_names = NexusUtil().all_ids_for_accounts("billing", accounts)
        result = []
        for account, all_names in zip(accounts, all_accounts_all_names):
            names = [account]
            try:
                names.append(all_names['codename'])
            except KeyError:
                pass
            try:
                names.append(all_names['casualname'])
            except KeyError:
                pass
            try:
                names.append(all_names['primus'])
            except KeyError:
                pass
            result.append(' - '.join(names))
        return result

    @cherrypy.expose
    def listAccounts(self, **kwargs):
        self.check_authentication()
        try:
            session = None
            accounts = []
            # eventually, this data will have to support pagination
            session = self.state_db.session()
            accounts = self.state_db.listAccounts(session)
            session.commit()
            rows = [{'account': account, 'name': full_name} for account,
                    full_name in zip(accounts, self.full_names_of_accounts(accounts))]
            return json.dumps({'success': True, 'rows':rows})
        except Exception as e:
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def listSequences(self, account, **kwargs):
        self.check_authentication()
        try:
            session = None
            sequences = []
            if not account:
                raise ValueError("Bad Parameter Value")
            # eventually, this data will have to support pagination
            session = self.state_db.session()
            sequences = self.state_db.listSequences(session, account)
            session.commit()
            rows = [{'sequence': sequence} for sequence in sequences]
            return json.dumps({'success': True, 'rows':rows})
        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def retrieve_account_status(self, start, limit, **args):
        self.check_authentication()
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            session = None
            if not start or not limit:
                raise ValueError("Bad Parameter Value")
            # result is a list of dictionaries of the form
            # {account: full name, dayssince: days}
            session = self.state_db.session()
            statuses, totalCount = self.state_db.retrieve_status_days_since(session, int(start), int(limit))
            session.commit()
            full_names = self.full_names_of_accounts([s.account for s in statuses])
            rows = [dict([('account', status.account), ('fullname', full_names[i]), ('dayssince', status.dayssince)])
                    for i, status in enumerate(statuses)]

            return ju.dumps({'success': True, 'rows':rows, 'results':totalCount})
        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def summary_ree_charges(self, start, limit, **args):
        self.check_authentication()
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            session = None

            if not start or not limit:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

            accounts, totalCount = self.state_db.list_accounts(session, int(start), int(limit))

            full_names = self.full_names_of_accounts([account for account in accounts])

            rows = self.process.summary_ree_charges(session, accounts, full_names)

            session.commit()


            return ju.dumps({'success': True, 'rows':rows, 'results':totalCount})

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            # TODO 20217999: log errors?
            print >> sys.stderr, e
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def all_ree_charges(self, **args):

        self.check_authentication()

        try:
            session = None

            session = self.state_db.session()

            rows, total_count = self.process.all_ree_charges(session)

            session.commit()

            return ju.dumps({'success': True, 'rows':rows, 'results':total_count})

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            # TODO 20217999: log errors?
            print >> sys.stderr, e
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def all_ree_charges_csv(self, **args):
        try:
            session = None

            session = self.state_db.session()
            rows, total_count = self.process.all_ree_charges(session)
            session.commit()

            import csv
            import StringIO

            buf = StringIO.StringIO()

            writer = csv.writer(buf)

            writer.writerow(['Account','Sequence',
                'Billing Addressee', 'Service Addressee',
                'Issue Date', 'Period Begin', 'Period End', 'RE&E Value', 
                'RE&E Charges', 'utility charges', 'hypothesized charges',
                'RE&E Energy Therms', 'Marginal Rate per Therm'])

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

                writer.writerow([row['account'], row['sequence'], 
                    bill_addr_str, service_addr_str, 
                    row['issue_date'], row['period_begin'], row['period_end'],
                    row['ree_value'], row['ree_charges'], row['actual_charges'], row['hypothetical_charges'],
                    row['total_energy'], row['marginal_rate_therm'] ])

                cherrypy.response.headers['Content-Type'] = 'text/csv'
                cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s.csv' % datetime.now().strftime("%Y%m%d")


            return buf.getvalue()

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            # TODO 20217999: log errors?
            print >> sys.stderr, e
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def all_ree_charges_csv_altitude(self, **args):
        try:
            session = None

            session = self.state_db.session()
            rows, total_count = self.process.all_ree_charges(session)
            session.commit()

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


            return buf.getvalue()

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            # TODO 20217999: log errors?
            print >> sys.stderr, e
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    # TODO see 15415625 about the problem passing in service to get at a set of RSIs
    def cprsrsi(self, xaction, account, sequence, service, **kwargs):
        self.check_authentication()
        try:
            if not xaction or not sequence or not service:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested rate structure 
            # if this is the case, return no rate structure.  
            # This is done so that the UI can configure itself with no data for the
            # requested rate structure 
            if reebill is None:
                return ju.dumps({'success':True})

            rate_structure = self.ratestructure_dao.load_cprs(
                reebill.account, 
                reebill.sequence, 
                reebill.branch,
                reebill.utility_name_for_service(service),
                reebill.rate_structure_name_for_service(service)
            )

            rates = rate_structure["rates"]

            if xaction == "read":
                return json.dumps({'success': True, 'rows':rates})

            elif xaction == "update":

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
                    reebill.branch,
                    reebill.utility_name_for_service(service),
                    reebill.rate_structure_name_for_service(service),
                    rate_structure
                )

                return json.dumps({'success':True})

            elif xaction == "create":

                new_rate = {"uuid": str(UUID.uuid1())}
                # should find an unbound charge item, and use its binding since an RSI
                # might be made after a charge item is created
                new_rate['rsi_binding'] = "Temporary RSI Binding"
                rates.append(new_rate)

                self.ratestructure_dao.save_cprs(
                    reebill.account, 
                    reebill.sequence, 
                    reebill.branch,
                    reebill.utility_name_for_service(service),
                    reebill.rate_structure_name_for_service(service),
                    rate_structure
                )

                return json.dumps({'success':True, 'rows':new_rate})

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
                    reebill.branch,
                    reebill.utility_name_for_service(service),
                    reebill.rate_structure_name_for_service(service),
                    rate_structure
                )

                return json.dumps({'success':True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def ursrsi(self, xaction, account, sequence, service, **kwargs):
        self.check_authentication()
        try:
            if not xaction or not account or not sequence or not service:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested rate structure 
            # if this is the case, return no rate structure.  
            # This is done so that the UI can configure itself with no data for the
            # requested rate structure 
            if reebill is None:
                return ju.dumps({'success':True})

            utility_name = reebill.utility_name_for_service(service)
            rs_name = reebill.rate_structure_name_for_service(service)
            rate_structure = self.ratestructure_dao.load_urs(utility_name, rs_name)

            if rate_structure is None:
                raise Exception("Could not load URS for %s and %s" % (utility_name, rs_name) )

            rates = rate_structure["rates"]

            if xaction == "read":
                return json.dumps({'success': True, 'rows':rates})

            elif xaction == "update":

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

                return json.dumps({'success':True})

            elif xaction == "create":

                new_rate = {"uuid": str(UUID.uuid1())}
                new_rate['rsi_binding'] = "Temporary RSI Binding"
                rates.append(new_rate)

                self.ratestructure_dao.save_urs(
                    reebill.utility_name_for_service(service),
                    reebill.rate_structure_name_for_service(service),
                    None,
                    None,
                    rate_structure
                )

                return json.dumps({'success':True, 'rows':new_rate})

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

                return json.dumps({'success':True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def payment(self, xaction, account, **kwargs):
        self.check_authentication()
        try:
            session = None
            if not xaction or not account:
                raise ValueError("Bad parameter value")


            if xaction == "read":

                session = self.state_db.session()
                payments = self.state_db.payments(session, account)
                session.commit()

                payments = [{
                    'id': payment.id, 
                    'date': str(payment.date),
                    'description': payment.description, 
                    'credit': str(payment.credit),
                } for payment in payments]

                
                return json.dumps({'success': True, 'rows':payments})

            elif xaction == "update":

                session = self.state_db.session()

                rows = json.loads(kwargs["rows"])

                # single edit comes in not in a list
                if type(rows) is dict: rows = [rows]

                # process list of edits
                for row in rows:
                    self.state_db.update_payment(
                        session,
                        row['id'],
                        row['date'],
                        row['description'],
                        row['credit'],
                    )
                
                session.commit()

                return json.dumps({'success':True})

            elif xaction == "create":

                session = self.state_db.session()

                from datetime import date

                new_payment = self.state_db.create_payment(session, account, date.today(), "New Entry", "0.00")
                session.commit()
                # TODO: is there a better way to populate a dictionary from an ORM object dict?
                row = [{
                    'id': new_payment.id, 
                    'date': str(new_payment.date),
                    'description': new_payment.description,
                    'credit': str(new_payment.credit),
                    }]


                return json.dumps({'success':True, 'rows':row})

            elif xaction == "destroy":

                session = self.state_db.session()

                rows = json.loads(kwargs["rows"])

                # single delete comes in not in a list
                if type(rows) is int: rows = [rows]

                for oid in rows:
                    self.state_db.delete_payment(session, oid)

                session.commit()
                         
                return json.dumps({'success':True})

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def reebill(self, xaction, start, limit, account, **kwargs):
        self.check_authentication()
        try:
            session = None

            if not xaction or not start or not limit:
                raise ValueError("Bad Parameter Value")

            if xaction == "read":

                session = self.state_db.session()

                reebills, totalCount = self.state_db.listReebills(session, int(start), int(limit), account)
                session.commit()

                # convert the result into a list of dictionaries for returning as
                # JSON to the browser
                rows = [{'sequence': reebill.sequence} for reebill in reebills]


                return json.dumps({'success': True, 'rows':rows, 'results':totalCount})

            elif xaction == "update":

                return json.dumps({'success':False})

            elif xaction == "create":

                return json.dumps({'success':False})

            elif xaction == "destroy":

                return json.dumps({'success':False})

        except Exception as e:    
            try:
               if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    ################
    # Handle addresses

    @cherrypy.expose
    def addresses(self, account, sequence, **args):
        self.check_authentication()
        """
        Return the billing and service address so that it may be edited.
        """

        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested addresses
            # if this is the case, return no periods.  
            # This is done so that the UI can configure itself with no data
            if reebill is None:
                return ju.dumps({})

            ba = reebill.billing_address
            sa = reebill.service_address
            
            addresses = {}

            addresses['billing_address'] = {
                'ba_addressee': ba['ba_addressee'] if 'ba_addressee' in ba else '',
                'ba_street1': ba['ba_street1'] if 'ba_street1' in ba else '',
                'ba_city': ba['ba_city'] if 'ba_city' in ba else '',
                'ba_state': ba['ba_state'] if 'ba_state' in ba else '',
                'ba_postal_code': ba['ba_postal_code'] if 'ba_postal_code' in ba else '',
            }

            addresses['service_address'] = {
                'sa_addressee': sa['sa_addressee'] if 'sa_addressee' in sa else '',
                'sa_street1': sa['sa_street1'] if 'sa_street1' in sa else '',
                'sa_city': sa['sa_city'] if 'sa_city' in sa else '',
                'sa_state': sa['sa_state'] if 'sa_state' in sa else '',
                'sa_postal_code': sa['sa_postal_code'] if 'sa_postal_code' in sa else '',
            }

            return ju.dumps(addresses)

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def set_addresses(self, account, sequence, 
        ba_addressee, ba_street1, ba_city, ba_state, ba_postal_code,
        sa_addressee, sa_street1, sa_city, sa_state, sa_postal_code,
         **args):
        """
        Update both the billing and service address.
        """

        self.check_authentication()
        try:
            if not account or not sequence \
            or not ba_addressee or not ba_street1 or not ba_city or not ba_state or not ba_postal_code \
            or not sa_addressee or not sa_street1 or not sa_city or not sa_state or not sa_postal_code:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            ba = reebill.billing_address
            sa = reebill.service_address
            
            reebill.billing_address['ba_addressee'] = ba_addressee
            reebill.billing_address['ba_street1'] = ba_street1
            reebill.billing_address['ba_city'] = ba_city
            reebill.billing_address['ba_state'] = ba_state
            reebill.billing_address['ba_postal_code'] = ba_postal_code

            reebill.service_address['sa_addressee'] = sa_addressee
            reebill.service_address['sa_street1'] = sa_street1
            reebill.service_address['sa_city'] = sa_city
            reebill.service_address['sa_state'] = sa_state
            reebill.service_address['sa_postal_code'] = sa_postal_code

            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    #
    ################

    ################
    # Handle ubPeriods

    @cherrypy.expose
    def ubPeriods(self, account, sequence, **args):
        self.check_authentication()
        """
        Return all of the utilbill periods on a per service basis so that the forms may be
        dynamically created.
        """

        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested periods 
            # if this is the case, return no periods.  
            # This is done so that the UI can configure itself with no data for the
            # requested measured usage
            if reebill is None:
                return ju.dumps({})
            
            utilbill_periods = {}
            for service in reebill.services:
                (begin, end) = reebill.utilbill_period_for_service(service)
                utilbill_periods[service] = {
                    'begin': begin,
                    'end': end
                    }

            return ju.dumps(utilbill_periods)

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def setUBPeriod(self, account, sequence, service, begin, end, **args):
        self.check_authentication()
        """ 
        Utilbill period forms are dynamically created in browser, and post back to here individual periods.
        """ 

        try:
            if not account or not sequence or not service or not begin or not end:
                raise ValueError("Bad Parameter Value")
            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_utilbill_period_for_service(service, (datetime.strptime(begin, "%Y-%m-%d"),datetime.strptime(end, "%Y-%m-%d")))
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    #
    ################

    ################
    # handle actual and hypothetical charges 

    @cherrypy.expose
    def actualCharges(self, service, account, sequence, **args):
        self.check_authentication()
        try:
            if not account or not sequence or not service:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested charges 
            # if this is the case, return no charges.  
            # This is done so that the UI can configure itself with no data for the
            # requested charges 
            if reebill is None:
                return ju.dumps({'success':True, 'rows':[]})

            flattened_charges = reebill.actual_chargegroups_flattened(service)
            return ju.dumps({'success': True, 'rows': flattened_charges})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def hypotheticalCharges(self, service, account, sequence, **args):
        self.check_authentication()
        try:
            if not account or not sequence or not service:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested charges 
            # if this is the case, return no charges.  
            # This is done so that the UI can configure itself with no data for the
            # requested charges 
            if reebill is None:
                return ju.dumps({'success':True, 'rows':[]})

            flattened_charges = reebill.hypothetical_chargegroups_flattened(service)
            return ju.dumps({'success': True, 'rows': flattened_charges})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def saveActualCharges(self, service, account, sequence, rows, **args):
        self.check_authentication()
        try:
            if not account or not sequence or not service or not rows:
                raise ValueError("Bad Parameter Value")

            flattened_charges = ju.loads(rows)

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_actual_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success': True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def saveHypotheticalCharges(self, service, account, sequence, rows, **args):
        self.check_authentication()
        try:
            if not account or not sequence or not service or not rows:
                raise ValueError("Bad Parameter Value")
            flattened_charges = ju.loads(rows)

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_hypothetical_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)
        
            return ju.dumps({'success': True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    ################
    # Handle measuredUsages

    @cherrypy.expose
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

        self.check_authentication()
        try:
            if not account or not sequence:
                raise ValueError("Bad Parameter Value")
            reebill = self.reebill_dao.load_reebill(account, sequence)

            # It is possible that there is no reebill for the requested measured usages
            # if this is the case, return no usages.  
            # This is done so that the UI can configure itself with no data for the
            # requested measured usage
            if reebill is None:
                return ju.dumps({'success': True})

            meters = reebill.meters

            return ju.dumps(meters)

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def setMeter(self, account, sequence, service, meter_identifier, presentreaddate, priorreaddate):
        self.check_authentication()
        try:
            if not account or not sequence or not service or not meter_identifier \
                or not presentreaddate or not priorreaddate:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_meter_read_date(service, meter_identifier, 
                datetime.strptime(presentreaddate, "%Y-%m-%d"), 
                datetime.strptime(priorreaddate, "%Y-%m-%d")
            )

            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def setActualRegister(self, account, sequence, service, register_identifier, meter_identifier, quantity):
        self.check_authentication()
        try:
            if not account or not sequence or not service or not register_identifier \
                or not meter_identifier or not quantity:
                raise ValueError("Bad Parameter Value")

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_meter_actual_register(service, meter_identifier, register_identifier, Decimal(quantity))
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    #
    ################

    ################
    # Handle utility bill upload

    @cherrypy.expose
    def upload_utility_bill(self, account, begin_date, end_date,
            file_to_upload, **args):
        self.check_authentication()
        try:
            session = None
            if not account or not begin_date or not end_date or not file_to_upload:
                raise ValueError("Bad Parameter Value")

            # convert dates, which come in as strings, into actual date objects
            begin_date_as_date = datetime.strptime(begin_date, '%Y-%m-%d').date()
            end_date_as_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            session = self.state_db.session()

            # if begin_date does not match end date of latest existing bill,
            # create hypothetical bills to cover the gap
            latest_end_date = self.state_db.last_utilbill_end_date(session, account)
            if latest_end_date is not None and begin_date_as_date > latest_end_date:
                self.state_db.fill_in_hypothetical_utilbills(session, account, latest_end_date, begin_date_as_date)
                # TODO 23165829 not certain we need to commit the guesses, when the upload
                # is successful, the session does get committed
                session.commit()

            if file_to_upload.file is None:
                # if there's no file, this is a "skyline estimated bill":
                # record it in the database with that state, but don't upload
                # anything
                self.state_db.record_utilbill_in_database(session, account,
                        begin_date, end_date, datetime.utcnow(),
                        state=db_objects.UtilBill.SkylineEstimated)
                session.commit()
                return ju.dumps({'success':True})
            else:
                # if there is a file, get the Python file object and name
                # string from CherryPy, and pass those to BillUpload to upload
                # the file (so BillUpload can stay independent of CherryPy
                upload_result = self.billUpload.upload(account, begin_date,
                        end_date, file_to_upload.file, file_to_upload.filename)
                if upload_result is True:
                    self.state_db.record_utilbill_in_database(session, account,
                            begin_date, end_date, datetime.utcnow())
                    session.commit()
                    return ju.dumps({'success':True})
                else:
                    self.logger.error('file upload failed:', begin_date, end_date,
                            file_to_upload.filename)
                    return ju.dumps({'success':False, 'errors': {
                        'reason':'file upload failed', 'details':'Returned False'}})
            
        except Exception as e: 
            if session is not None: 
                try:
                    if session is not None: session.rollback()
                except:
                    print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e),
                'details':traceback.format_exc()}})

    #
    ################

    @cherrypy.expose
    def journal(self, xaction, account, **kwargs):
        self.check_authentication()
        try:
            if not xaction or not account:
                raise ValueError("Bad Parameter Value")

            journal_entries = self.journal_dao.load_entries(account)

            if xaction == "read":
                return ju.dumps({'success': True, 'rows':journal_entries})

            elif xaction == "update":

                # TODO: 20493983 eventually allow admin user to override and edit
                return json.dumps({'success':False, 'errors':{'reason':'Not supported'}})

            elif xaction == "create":

                # TODO: 20493983 necessary for adding new journal entries directy to grid
                return json.dumps({'success':False, 'errors':{'reason':'Not supported'}})

            elif xaction == "destroy":

                # TODO: 20493983 eventually allow admin user to override and edit
                return json.dumps({'success':False, 'errors':{'reason':'Not supported'}})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def save_journal_entry(self, account, sequence, entry, **kwargs):
        self.check_authentication()
        try:
            # TODO: 1320091681504  allow a journal entry to be made without a sequence
            if not account or not sequence or not entry:
                raise ValueError("Bad Parameter Value")

            self.journal_dao.journal(account, sequence, entry)

            return json.dumps({'success':True})

        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

 
    @cherrypy.expose
    def listUtilBills(self, start, limit, account, **args):
        self.check_authentication()
        try:
            # names for utilbill states in the UI
            state_descriptions = {
                db_objects.UtilBill.Complete: 'Final',
                db_objects.UtilBill.UtilityEstimated: 'Utility Estimated',
                db_objects.UtilBill.SkylineEstimated: 'Skyline Estimated',
                db_objects.UtilBill.Hypothetical: 'Hypothetical'
            }

            session = None

            if not start or not limit or not account:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

            # result is a list of dictionaries of the form {account: account
            # number, name: full name, period_start: date, period_end: date,
            # sequence: reebill sequence number (if present)}
            utilbills, totalCount = self.state_db.list_utilbills(session, account, int(start), int(limit))
            session.commit()
            # note that utilbill customers are eagerly loaded
            full_names = self.full_names_of_accounts([ub.customer.account for ub in utilbills])
            rows = [dict([
                ('account', ub.customer.account),
                ('name', full_names[i]),
                ('period_start', ub.period_start),
                ('period_end', ub.period_end),
                ('sequence', ub.reebill.sequence if ub.reebill else None),
                # TODO this doesn't show up in the gui
                ('state', state_descriptions[ub.state])
            ]) for i, ub in enumerate(utilbills)]
            return ju.dumps({'success': True, 'rows':rows, 'results':totalCount})
        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})
    
    @cherrypy.expose
    def last_utilbill_end_date(self, account, **kwargs):
        '''Returns date of last utilbill.'''
        self.check_authentication()
        try:
            session = self.state_db.session()
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
            return ju.dumps({'success':True, 'date': the_datetime})
        except Exception as e: 
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def getUtilBillImage(self, account, begin_date, end_date, resolution, **args):
        self.check_authentication()
        try:
            if not account or not begin_date or not end_date or not resolution:
                raise ValueError("Bad Parameter Value")
            # TODO: put url here, instead of in billentry.js?
            resolution = cherrypy.session['user'].preferences['bill_image_resolution']
            result = self.billUpload.getUtilBillImagePath(account, begin_date, end_date, resolution)
            return ju.dumps({'success':True, 'imageName':result})
        except Exception as e: 
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def getReeBillImage(self, account, sequence, resolution, **args):
        self.check_authentication()
        try:
            if not account or not sequence or not resolution:
                raise ValueError("Bad Parameter Value")
            resolution = cherrypy.session['user'].preferences['bill_image_resolution']
            result = self.billUpload.getReeBillImagePath(account, sequence, resolution)
            return ju.dumps({'success':True, 'imageName':result})
        except Exception as e: 
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})
    
    @cherrypy.expose
    def getBillImageResolution(self, **kwargs):
        self.check_authentication()
        try:
            resolution = cherrypy.session['user'].preferences['bill_image_resolution']
            return ju.dumps({'success':True, 'resolution': resolution})
        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def setBillImageResolution(self, resolution, **kwargs):
        self.check_authentication()
        try:
            cherrypy.session['user'].preferences['bill_image_resolution'] = int(resolution)
            self.user_dao.save_user(cherrypy.session['user'])
            return ju.dumps({'success':True})
        except Exception as e:
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def reebill_structure(self, account, sequence=None, **args):
        self.check_authentication()
        try:
            session = None
            if not account:
                raise ValueError("Bad Parameter Value: account")

            session = self.state_db.session()

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
                #return ju.dumps({'success':True, 'reebill_structure':tree});
                # but the TreeLoader doesn't abide by the above ajax packet
                return ju.dumps(tree);

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))

            # TreePanel doesn't do error handling
            # Maybe the TreeLoader can be made to respond to something.
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def insert_reebill_sibling_node(self, service, account, sequence, node_type, node_key, **args):
        """
        """
        self.check_authentication()
        try:
            session = None
            if not service or not account or not sequence or not node_type or not node_key:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

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

            session.commit()

            return ju.dumps({'success': True, 'node':new_node })

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))

            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def delete_reebill_node(self, service, account, sequence, node_type, node_key, text, **args):
        """
        """
        self.check_authentication()
        try:
            session = None
            if not service or not account or not sequence or not node_type or not node_key or not text:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

            reebill = self.reebill_dao.load_reebill(account, sequence)

            if reebill:
                if node_type == 'meter':

                    # retrieve this meter based on node_key
                    reebill.delete_meter(service, node_key)

                elif node_type == 'register':
                    raise Exception("finish me")

            self.reebill_dao.save_reebill(reebill)

            session.commit()

            return ju.dumps({'success': True })

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))

            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def update_reebill_node(self, service, account, sequence, node_type, node_key, text, **args):
        """
        """
        self.check_authentication()
        try:
            session = None
            if not service or not account or not sequence or not node_type or not node_key or not text:
                raise ValueError("Bad Parameter Value")

            session = self.state_db.session()

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

            session.commit()

            return ju.dumps({'success': True, 'node':updated_node})
            #return ju.dumps({'success': True})

        except Exception as e:
            try:
                if session is not None: session.rollback()
            except:
                print "Could not rollback session"
            self.logger.error('%s:\n%s' % (e, traceback.format_exc()))

            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        
# TODO: place instantiation in main, so this module can be loaded without btb being instantiated
bridge = BillToolBridge()

if __name__ == '__main__':
    # configure CherryPy
    local_conf = {
        '/' : {
            'tools.staticdir.root' :os.path.dirname(os.path.abspath(__file__)), 
            #'tools.staticdir.dir' : '',
            #'tools.staticdir.on' : True,
            'tools.expires.secs': 0,
            'tools.response_headers.on': True,
        },
    }
    cherrypy.config.update({ 'server.socket_host': bridge.config.get("http", "socket_host"),
                             'server.socket_port': int(bridge.config.get("http", "socket_port")),
                             })
    cherrypy.quickstart(bridge, "/", config = local_conf)
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
