from os.path import dirname, realpath, join
import smtplib
from boto.s3.connection import S3Connection
from core import init_config, init_model, init_logging
from core.utilbill_loader import UtilBillLoader

# TODO: is it necessary to specify file path?
p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(filepath=p)
init_config(filepath=p)
init_model()

from core import config
import sys

import json
import cherrypy
import os
import ConfigParser
from datetime import datetime
import logging
import functools
from operator import itemgetter
from StringIO import StringIO
import mongoengine
from skyliner.splinter import Splinter
from skyliner import mock_skyliner
from util import json_util as ju
from util.dateutils import ISO_8601_DATE
from nexusapi.nexus_util import NexusUtil
from util.dictutils import deep_map
from reebill.bill_mailer import Mailer
from reebill import state, fetch_bill_data as fbd
from core.pricing import FuzzyPricingModel
from core.model import Session
from core.utilbill_loader import UtilBillLoader
from core.bill_file_handler import BillFileHandler
from reebill import journal, reebill_file_handler
from reebill.users import UserDAO
from reebill.utilbill_processor import UtilbillProcessor
from reebill.reebill_processor import ReebillProcessor
from exc import Unauthenticated, IssuedBillError, ConfirmAdjustment
from reebill.excel_export import Exporter
from core.model import UtilBill

user_dao = UserDAO(**dict(config.items('mongodb')))

cherrypy.request.method_with_bodies = ['PUT', 'POST', 'GET', 'DELETE']


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
    if not config.get('reebill', 'authenticate'):
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

        user = user_dao.load_by_session_token(credentials) if credentials else None
        if user is None:
            logger.info('Remember Me login attempt failed:'
                        ' username "%s"' % username)
        else:
            logger.info('Remember Me login attempt'
                        ' success: username "%s"' % username)
            cherrypy.session['user'] = user
            return True
        raise Unauthenticated("No Session")
    return True

def db_commit(method):
    '''CherryPY Decorator for committing a database transaction when the method
    returns. This should be used only on methods that should be allowed to
    modify the database.
    '''
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        result = method(*args, **kwargs)
        Session().commit()
        return result
    return wrapper


class WebResource(object):

    def __init__(self):
        self.config = config
        self.logger = logging.getLogger('reebill')

        # create a NexusUtil
        cache_file_path = self.config.get('reebill', 'nexus_offline_cache_file')
        if cache_file_path == '':
            cache = None
        else:
            with open(cache_file_path) as cache_file:
                text = cache_file.read()
            if text == '':
                cache = []
            else:
                cache = json.load(text)
        self.nexus_util = NexusUtil(self.config.get('reebill',
                                                    'nexus_web_host'),
                                    offline_cache=cache)

        # load users database
        self.user_dao = UserDAO(**dict(self.config.items('mongodb')))

        # create an instance representing the database
        self.state_db = state.StateDB(logger=self.logger)

        s3_connection = S3Connection(
                config.get('aws_s3', 'aws_access_key_id'),
                config.get('aws_s3', 'aws_secret_access_key'),
                is_secure=config.get('aws_s3', 'is_secure'),
                port=config.get('aws_s3', 'port'),
                host=config.get('aws_s3', 'host'),
                calling_format=config.get('aws_s3', 'calling_format'))
        utilbill_loader = UtilBillLoader(Session())
        # TODO: ugly. maybe put entire url_format in config file.
        url_format = '%s://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
                'https' if config.get('aws_s3', 'is_secure') is True else
                'http', config.get('aws_s3', 'host'),
                config.get('aws_s3', 'port'))
        self.bill_file_handler = BillFileHandler(s3_connection,
                                     config.get('aws_s3', 'bucket'),
                                     utilbill_loader, url_format)

        # create a FuzzyPricingModel
        self.ratestructure_dao = FuzzyPricingModel(utilbill_loader,
                                                   logger=self.logger)

        # configure journal:
        # create a MongoEngine connection "alias" named "journal" with which
        # journal.Event subclasses (in journal.py) can associate themselves by
        # setting meta = {'db_alias': 'journal'}.
        journal_config = dict(self.config.items('mongodb'))
        mongoengine.connect(
            journal_config['database'],
            host=journal_config['host'], port=int(journal_config['port']),
            alias='journal')
        self.journal_dao = journal.JournalDAO()

        # set the server sessions key which is used to return credentials
        # in a client side cookie for the 'rememberme' feature
        if self.config.get('reebill', 'sessions_key'):
            self.sessions_key = self.config.get('reebill', 'sessions_key')

        # create a Splinter
        if self.config.get('reebill', 'mock_skyliner'):
            self.splinter = mock_skyliner.MockSplinter()
        else:
            self.splinter = Splinter(
                self.config.get('reebill', 'oltp_url'),
                skykit_host=self.config.get('reebill', 'olap_host'),
                skykit_db=self.config.get('reebill', 'olap_database'),
                olap_cache_host=self.config.get('reebill', 'olap_host'),
                olap_cache_db=self.config.get('reebill', 'olap_database'),
                monguru_options={
                    'olap_cache_host': self.config.get('reebill', 'olap_host'),
                    'olap_cache_db': self.config.get('reebill',
                                                     'olap_database'),
                    'cartographer_options': {
                        'olap_cache_host': self.config.get('reebill',
                                                           'olap_host'),
                        'olap_cache_db': self.config.get('reebill',
                                                         'olap_database'),
                        'measure_collection': 'skymap',
                        'install_collection': 'skyit_installs',
                        'nexus_host': self.config.get('reebill',
                                                      'nexus_db_host'),
                        'nexus_db': 'nexus',
                        'nexus_collection': 'skyline',
                    },
                },
                cartographer_options={
                    'olap_cache_host': self.config.get('reebill', 'olap_host'),
                    'olap_cache_db': self.config.get('reebill',
                                                     'olap_database'),
                    'measure_collection': 'skymap',
                    'install_collection': 'skyit_installs',
                    'nexus_host': self.config.get('reebill', 'nexus_db_host'),
                    'nexus_db': 'nexus',
                    'nexus_collection': 'skyline',
                },
            )

        # create a ReebillRenderer
        self.reebill_file_handler = reebill_file_handler.ReebillFileHandler(
                self.config.get('reebill', 'reebill_file_path'),
                self.config.get('reebill', 'teva_accounts'))
        mailer_opts = dict(self.config.items("mailer"))
        server = smtplib.SMTP()
        self.bill_mailer = Mailer(mailer_opts['mail_from'],
                mailer_opts['originator'],
                mailer_opts['password'],
                mailer_opts['template_file_name'],
                server,
                mailer_opts['smtp_host'],
                mailer_opts['smtp_port'],
                mailer_opts['bcc_list'])

        self.ree_getter = fbd.RenewableEnergyGetter(self.splinter, self.logger)

        self.utilbill_processor = UtilbillProcessor(
            self.ratestructure_dao, self.bill_file_handler, self.nexus_util,
            logger=self.logger)
        self.reebill_processor = ReebillProcessor(
            self.state_db, self.nexus_util, self.bill_mailer,
            self.reebill_file_handler, self.ree_getter, self.journal_dao,
            logger=self.logger)

        # determine whether authentication is on or off
        self.authentication_on = self.config.get('reebill', 'authenticate')

        self.reconciliation_report_dir = self.config.get(
            'reebillreconciliation', 'report_directory')
        self.estimated_revenue_report_dir = self.config.get(
            'reebillestimatedrevenue', 'report_directory')

    def dumps(self, data):

        # accept only dictionaries so that additional keys may be added
        if type(data) is not dict:
            raise ValueError("Dictionary required.")

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


class RESTResource(WebResource):
    """
    Base class for providing a RESTful interface to a resource.

    To use this class, simply derive a class from it and implement the methods
    you want to support.  The list of possible methods are:
    handle_get
    handle_put
    handle_post
    handle_delete
    """
    @cherrypy.expose
    @cherrypy.tools.authenticate_ajax()
    @cherrypy.tools.json_in(force=False)
    @db_commit
    def default(self, *vpath, **params):
        method = getattr(self,
                         "handle_" + cherrypy.request.method.lower(),
                         None)

        if not method:
            methods = [x.replace("handle_", "")
                       for x in dir(self) if x.startswith("handle_")]
            cherrypy.response.headers["Allow"] = ",".join(methods)
            raise cherrypy.HTTPError(405, "Method not implemented.")
        response = method(*vpath, **params)

        if type(response) != tuple:
            raise ValueError("%s.handle_%s must return a tuple ("
                             "True/False, {}) where True/False is a boolean "
                             "indicating the success of the request and {} "
                             "is a python dict containing the response to be "
                             "sent back to the client."
                             "" % (self.__class__.__name__,
                                   cherrypy.request.method.lower()))
        else:
            success, return_value = response

        if cherrypy.request.method == 'POST' and success is True:
            cherrypy.response.status = "201 Created"

        if cherrypy.request.method == 'GET' and not return_value:
            if success is True:
                cherrypy.response.status = "204 No Content"
            else:
                raise cherrypy.HTTPError(404, "Not Found")


        return self.dumps(return_value)

    def check_modifiable(self, sequence, version):
        if (sequence, version) != (None, None):
            raise IssuedBillError('Issued reebills cannot be modified')


class AccountsResource(RESTResource):

    def handle_get(self, *vpath, **params):
        """Handles AJAX request for "Account Processing Status" grid in
        "Accounts" tab."""
        count, rows = self.reebill_processor.list_account_status()
        return True, {'rows': rows, 'results': count}

    def handle_post(self,*vpath, **params):
        """ Handles the creation of a new account
        """
        row = cherrypy.request.json
        billing_address = {
            'addressee': row['ba_addressee'],
            'street': row['ba_street'],
            'city': row['ba_city'],
            'state': row['ba_state'],
            'postal_code': row['ba_postal_code'],
        }
        service_address = {
            'addressee': row['sa_addressee'],
            'street': row['sa_street'],
            'city': row['sa_city'],
            'state': row['sa_state'],
            'postal_code': row['sa_postal_code'],
        }

        # TODO: for some reason Ext JS converts null into emtpy string
        if row['service_type'] == '':
            row['service_type'] = None
        self.reebill_processor.create_new_account(
                row['account'], row['name'], row['service_type'],
                float(row['discount_rate']), float(row['late_charge_rate']),
                billing_address, service_address, row['template_account'],
                row['utility_account_number'])

        journal.AccountCreatedEvent.save_instance(cherrypy.session['user'],
                row['account'])

        count, result = self.reebill_processor.list_account_status(row['account'])
        print count, result
        return True, {'rows': result, 'results': count}

    def handle_put(self, *vpath, **params):
        """ Handles the updates to existing account
        """
        row = cherrypy.request.json
        self.utilbill_processor.update_utility_account_number(
            row['utility_account_id'], row['utility_account_number'])
        return True, {}


class IssuableReebills(RESTResource):

    def handle_get(self, *vpath, **params):
        issuable_reebills = self.reebill_processor.get_issuable_reebills_dict()
        return True, {'rows': issuable_reebills,
                      'results': len(issuable_reebills)}

    def handle_put(self, reebill_id, *vpath, **params):
        row = cherrypy.request.json
        # Handle email address update
        self.reebill_processor.update_bill_email_recipient(
            row['account'], row['sequence'], row['mailto'])

        row['action'] = ''
        row['action_value'] = ''
        return True, {'row': row, 'results': 1}

    @cherrypy.expose
    @cherrypy.tools.authenticate_ajax()
    @db_commit
    def issue_and_mail(self, reebills, **params):
        bills = json.loads(reebills)
        reebills_with_corrections = []
        for bill in bills:
            account, sequence = bill['account'], int(bill['sequence'])
            recipient_list = bill['recipients']
            try:
                result = self.reebill_processor.issue_and_mail(
                    bill['apply_corrections'],
                    account=account, sequence=sequence, recipients=recipient_list)
            except ConfirmAdjustment as e:
                reebills_with_corrections.append({'account': bill['account'],
                        'sequence': bill['sequence'],
                        'recipients': bill['recipients'],
                        'apply_corrections': False,
                        'corrections': e.correction_sequences,
                        'adjustment': e.total_adjustment})
        if not reebills_with_corrections:
            for bill in bills:
                version = self.state_db.max_version(bill['account'],
                                                    bill['sequence'])
                journal.ReeBillIssuedEvent.save_instance(
                        cherrypy.session['user'], bill['account'],
                        bill['sequence'], version,
                        applied_sequence=version if version!=0 else None)
            journal.ReeBillMailedEvent.save_instance(
                cherrypy.session['user'], bill['account'], bill['sequence'],
                bill['recipients'])
            return self.dumps({'success': True, 'issued': bills})
        else:
            return self.dumps({'success': True,
                    'reebills': reebills_with_corrections,
                    'corrections': True})

    @cherrypy.expose
    @cherrypy.tools.authenticate_ajax()
    @db_commit
    def issue_processed_and_mail(self, **kwargs):
        params = cherrypy.request.params
        bills = self.reebill_processor.issue_processed_and_mail(apply_corrections=True)
        for bill in bills:
            version = self.state_db.max_version(bill['account'], bill['sequence'])
            journal.ReeBillIssuedEvent.save_instance(
                    cherrypy.session['user'], bill['account'], bill['sequence'],
                    version, applied_sequence=bill['sequence']
                if version != 0 else None)
            if version == 0:
                journal.ReeBillMailedEvent.save_instance(
                        cherrypy.session['user'], bill['account'],
                        bill['sequence'], bill['mailto'])
        return self.dumps({'success': True,
                    'issued': bills})

class ReebillVersionsResource(RESTResource):

    def handle_get(self, account, sequence, *vpath, **params):
        result = self.reebill_processor.list_all_versions(account, sequence)
        return True, {'rows': result, 'results': len(result)}

class ReebillsResource(RESTResource):

    def handle_get(self, account, start, limit, sort='account', dir='DESC',
                   *vpath, **params):
        start, limit = int(start), int(limit)

        '''Handles GET requests for reebill grid data.'''
        # this is inefficient but length is always <= 120 rows
        rows = sorted(self.reebill_processor.get_reebill_metadata_json(
            account), key=itemgetter(sort))
        if dir == 'DESC':
            rows.reverse()

        # "limit" means number of rows to return, so the real limit is
        # start + limit
        result = rows[start: start + limit]
        return True, {'rows': result, 'results': len(rows)}

    def handle_post(self, account, *vpath, **params):
        """ Handles Reebill creation """
        params = cherrypy.request.json
        start_date = params['period_start'] if params['period_start'] else None
        if start_date is not None:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        reebill = self.reebill_processor.roll_reebill(account, start_date=start_date)

        journal.ReeBillRolledEvent.save_instance(
            cherrypy.session['user'], account, reebill.sequence)
        # Process.roll includes attachment
        # TODO "attached" is no longer a useful event;
        # see https://www.pivotaltracker.com/story/show/55044870
        journal.ReeBillAttachedEvent.save_instance(cherrypy.session['user'],
            reebill.get_account(), reebill.sequence, reebill.version)
        journal.ReeBillBoundEvent.save_instance(
            cherrypy.session['user'],account, reebill.sequence, reebill.version)

        return True, {'rows': reebill.column_dict(), 'results': 1}

    def handle_put(self, reebill_id, *vpath, **params):
        row = cherrypy.request.json
        r = self.state_db.get_reebill_by_id(reebill_id)
        sequence, account = r.sequence, r.get_account()
        action = row.pop('action')
        action_value = row.pop('action_value')
        rtn = None

        if action == 'bindree':
            self.reebill_processor.bind_renewable_energy(account, sequence)
            reebill = self.state_db.get_reebill(account, sequence)
            journal.ReeBillBoundEvent.save_instance(cherrypy.session['user'],
                account, sequence, r.version)
            rtn = reebill.column_dict()

        elif action == 'render':
            self.reebill_processor.render_reebill(int(account), int(sequence))
            rtn = row

        elif action == 'mail':
            if not action_value:
                raise ValueError("Got no value for row['action_value']")

            recipients = action_value
            recipient_list = [rec.strip() for rec in recipients.split(',')]

            self.reebill_processor.mail_reebills(account, [int(sequence)], recipient_list)

            # journal mailing of every bill
            journal.ReeBillMailedEvent.save_instance(
                cherrypy.session['user'], account, sequence, recipients)
            rtn = row

        elif action == 'updatereadings':
            rb = self.reebill_processor.update_reebill_readings(account, sequence)
            rtn = rb.column_dict()

        elif action == 'compute':
            rb = self.reebill_processor.compute_reebill(account, sequence, 'max')
            rtn = rb.column_dict()

        elif action == 'newversion':
            rb = self.reebill_processor.new_version(account, sequence)

            journal.NewReebillVersionEvent.save_instance(cherrypy.session['user'],
                    rb.get_account(), rb.sequence, rb.version)
            rtn = rb.column_dict()

        elif not action:
            # Regular PUT request. In this case this means updated
            # Sequential Account Information
            discount_rate = float(row['discount_rate'])
            late_charge_rate = float(row['late_charge_rate'])

            ba = row['billing_address']
            sa = row['service_address']

            # rely on client-side validation
            assert discount_rate >= 0 and discount_rate <= 1
            assert late_charge_rate >= 0 and late_charge_rate <= 1

            rb = self.reebill_processor.update_sequential_account_info(
                account, sequence,
                discount_rate=discount_rate,
                late_charge_rate=late_charge_rate,
                ba_addressee=ba['addressee'], ba_street=ba['street'],
                ba_city=ba['city'], ba_state=ba['state'],
                ba_postal_code=ba['postal_code'],
                sa_addressee=sa['addressee'], sa_street=sa['street'],
                sa_city=sa['city'], sa_state=sa['state'],
                sa_postal_code=sa['postal_code'],
                processed=row['processed'])

            rtn = rb.column_dict()

        # Reset the action parameters, so the client can coviniently submit
        # the same action again
        rtn['action'] = ''
        rtn['action_value'] = ''
        return True, {'rows': rtn, 'results': 1}

    def handle_delete(self, reebill_id, *vpath, **params):
        r = self.state_db.get_reebill_by_id(reebill_id)

        sequence, account = r.sequence, r.get_account()
        deleted_version = self.reebill_processor.delete_reebill(account,
                                                                sequence)
        # deletions must all have succeeded, so journal them
        journal.ReeBillDeletedEvent.save_instance(cherrypy.session['user'],
            account, sequence, deleted_version)

        return True, {}

    @cherrypy.expose
    @cherrypy.tools.authenticate_ajax()
    @db_commit
    def toggle_processed(self, **params):
        params = cherrypy.request.params
        r = self.state_db.get_reebill_by_id(int(params['reebill']))
        try:
            self.reebill_processor.toggle_reebill_processed(
                r.get_account(), r.sequence,
                params['apply_corrections'] == 'true')
        except ConfirmAdjustment as e:
            return self.dumps({
                'unissued_corrections': e.correction_sequences,
                'adjustment': e.total_adjustment,
                'corrections': True
            })
        return self.dumps({'success': True, 'reebill': r.column_dict()})

class UtilBillResource(RESTResource):

    def handle_get(self, account, *vpath, **params):
        rows, total_count = self.utilbill_processor.get_all_utilbills_json(
            account)
        return True, {'rows': rows, 'results': total_count}

    def handle_post(self, *vpath, **params):
        """ Handles Utilitybill creation. Since this information is sent by a
        form and contains a file object we have to manually parse the data """
        # pre-process parameters
        params = cherrypy.request.params
        account = params['account']
        service = params['service'].lower()
        total_charges = float(params['total_charges'])
        begin_date = datetime.strptime(params['begin_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(params['end_date'], '%Y-%m-%d').date()

        # NOTE 'fileobj.file' is always a CherryPy object; if no
        # file was specified, 'fileobj.file' will be None
        fileobj = params['file_to_upload']

        billstate = UtilBill.Complete if fileobj.file else \
            UtilBill.Estimated
        self.utilbill_processor.upload_utility_bill(
            account, fileobj.file, start=begin_date, end=end_date,
            service=service, utility=None, rate_class=None, total=total_charges,
            state=billstate)

        # Since this is initated by an Ajax request, we will still have to
        # send a {'success', 'true'} parameter
        return True, {'success': 'true'}

    def handle_put(self, utilbill_id, *vpath, **params):
        row = cherrypy.request.json
        action = row.pop('action')
        action_value = row.pop('action_value')
        result= {}

        if action == 'regenerate_charges':
            ub = self.utilbill_processor.regenerate_uprs(utilbill_id)
            result = ub.column_dict()

        elif action == 'compute':
            ub = self.utilbill_processor.compute_utility_bill(utilbill_id)
            result = ub.column_dict()

        elif action == '': 
            result = self.utilbill_processor.update_utilbill_metadata(
                utilbill_id,
                period_start=datetime.strptime(row['period_start'], ISO_8601_DATE).date(),
                period_end=datetime.strptime(row['period_end'], ISO_8601_DATE).date(),
                service=row['service'].lower(),
                target_total=row['target_total'],
                processed=row['processed'],
                rate_class=row['rate_class'],
                utility=row['utility'],
                supplier=row['supplier']).column_dict()

        # Reset the action parameters, so the client can coviniently submit
        # the same action again
        result['action'] = ''
        result['action_value'] = ''
        return True, {'rows': result, 'results': 1}

    def handle_delete(self, utilbill_id, account, *vpath, **params):
        utilbill, deleted_path = self.utilbill_processor.delete_utility_bill_by_id(
            utilbill_id)
        journal.UtilBillDeletedEvent.save_instance(
            cherrypy.session['user'], account,
            utilbill.period_start, utilbill.period_end,
            utilbill.service, deleted_path)
        return True, {}


class ReebillChargesResource(RESTResource):

    def handle_get(self, reebill_id, *vpath, **params):
        charges = self.reebill_processor.get_hypothetical_matched_charges(reebill_id)
        return True, {'rows': charges, 'total': len(charges)}


class RegistersResource(RESTResource):


    def handle_get(self, utilbill_id, *vpath, **params):
        # get dictionaries describing all registers in all utility bills
        registers_json = self.utilbill_processor.get_registers_json(utilbill_id)
        return True, {"rows": registers_json, 'results': len(registers_json)}

    def handle_post(self, *vpath, **params):
        r = self.utilbill_processor.new_register(**cherrypy.request.json)
        return True, {"rows": r.column_dict(), 'results': 1}

    def handle_put(self, register_id, *vpath, **params):
        updated_reg = cherrypy.request.json

        # all arguments should be strings, except "quantity",
        # which should be a number
        if 'quantity' in updated_reg:
            assert isinstance(updated_reg['quantity'], (float, int))

        register = self.utilbill_processor.update_register(register_id, updated_reg)
        return True, {"rows": register.column_dict(), 'results': 1}

    def handle_delete(self, register_id, *vpath, **params):
        self.utilbill_processor.delete_register(register_id)
        return True, {}


class ChargesResource(RESTResource):

    def handle_get(self, utilbill_id, *vpath, **params):
        charges = self.utilbill_processor.get_utilbill_charges_json(utilbill_id)
        return True, {'rows': charges, 'results': len(charges)}

    def handle_put(self, charge_id, *vpath, **params):
        c = self.utilbill_processor.update_charge(cherrypy.request.json,
                                       charge_id=charge_id)
        return True, {'rows': c.column_dict(),  'results': 1}

    def handle_post(self, *vpath, **params):
        c = self.utilbill_processor.add_charge(**cherrypy.request.json)
        return True, {'rows': c.column_dict(),  'results': 1}

    def handle_delete(self, charge_id, *vpath, **params):
        self.utilbill_processor.delete_charge(charge_id)
        return True, {}


class SuppliersResource(RESTResource):

    def handle_get(self, *vpath, **params):
        suppliers = self.utilbill_processor.get_all_suppliers_json()
        return True, {'rows': suppliers, 'results': len(suppliers)}


class UtilitiesResource(RESTResource):

    def handle_get(self, *vpath, **params):
        utilities = self.utilbill_processor.get_all_utilities_json()
        return True, {'rows': utilities, 'results': len(utilities)}


class RateClassesResource(RESTResource):

    def handle_get(self, *vpath, **params):
        rate_classes = self.utilbill_processor.get_all_rate_classes_json()
        return True, {'rows': rate_classes, 'results': len(rate_classes)}


class PaymentsResource(RESTResource):

    def handle_get(self, account, start, limit, *vpath, **params):
        start, limit = int(start), int(limit)
        rows = self.reebill_processor.get_payments(account)
        return True, {'rows': rows[start:start+limit],  'results': len(rows)}

    def handle_post(self, account, *vpath, **params):
        d = cherrypy.request.json['date_received']
        d = datetime.strptime(d, '%Y-%m-%d %H:%M:%S')
        print "\n\n\n\n", d, type(d)
        new_payment = self.reebill_processor.create_payment(account, d, "New Entry", 0, d)
        return True, {"rows": new_payment.column_dict(), 'results': 1}

    def handle_put(self, payment_id, *vpath, **params):
        row = cherrypy.request.json
        self.reebill_processor.update_payment(
            int(payment_id),
            row['date_applied'],
            row['description'],
            row['credit'],
        )
        return True, {"rows": row, 'results': 1}

    def handle_delete(self, payment_id, *vpath, **params):
        self.reebill_processor.delete_payment(payment_id)
        return True, {}


class JournalResource(RESTResource):

    def handle_get(self, account, *vpath, **params):
        journal_entries = self.journal_dao.load_entries(account)
        return True, {'rows': journal_entries,  'results': len(journal_entries)}

    def handle_post(self,  *vpath, **params):
        account = cherrypy.request.json['account']
        sequence = cherrypy.request.json['sequence']
        sequence = sequence if sequence else None
        message = cherrypy.request.json['msg']
        note = journal.Note.save_instance(cherrypy.session['user'], account,
                                          message, sequence=sequence)
        return True, {'rows': note.to_dict(), 'results': 1}


class PreferencesResource(RESTResource):

    def handle_get(self, *vpath, **params):
        rows = [{'key': k, 'value': v} for k, v in cherrypy.session[
            'user'].preferences.items()]
        rows.append({'key': 'username', 'value': cherrypy.session[
            'user'].username})
        return True, {'rows': rows,  'results': len(rows)}

    def handle_put(self, *vpath, **params):
        row = cherrypy.request.json
        cherrypy.session['user'].preferences[row['key']] = row['value']
        self.user_dao.save_user(cherrypy.session['user'])
        return True, {'rows': row,  'results': 1}

    def handle_post(self, *vpath, **params):
        row = cherrypy.request.json
        cherrypy.session['user'].preferences[row['key']] = row['value']
        self.user_dao.save_user(cherrypy.session['user'])
        return True, {'rows': row,  'results': 1}

class ReportsResource(WebResource):

    @cherrypy.expose
    @cherrypy.tools.authenticate()
    def default(self, *vpath, **params):
        row = cherrypy.request.params
        print row
        account = row['account'] if row['account'] != '' else None
        begin_date = datetime.strptime(row['period_start'], '%m/%d/%Y').date() \
            if row['period_start'] != '' else None
        end_date = datetime.strptime(row['period_end'], '%m/%d/%Y').date() if \
            row['period_end'] != '' else None

        if row['type'] == 'utilbills':
            """
            Responds with an excel spreadsheet containing all actual charges for all
            utility bills for the given account, or every account (1 per sheet) if
            'account' is not given, or all utility bills for the account(s) filtered
            by time, if 'start_date' and/or 'end_date' are given.
            """
            if account is not None:
                spreadsheet_name = account + '.xls'
            else:
                spreadsheet_name = 'all_accounts.xls'
            exporter = Exporter(self.state_db)

            # write excel spreadsheet into a StringIO buffer (file-like)
            buf = StringIO()
            exporter.export_account_charges(buf, account, begin_date, end_date)

            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=%s' % spreadsheet_name

            return buf.getvalue()

        elif row['type'] == 'energy_usage':
            """
            Responds with an excel spreadsheet containing all actual charges, total
            energy and rate structure for all utility bills for the given account,
            or every account (1 per sheet) if 'account' is not given,
            """
            if account is not None:
                spreadsheet_name = account + '.xls'
            else:
                spreadsheet_name = 'brokerage_accounts.xls'
            exporter = Exporter(self.state_db)

            buf = StringIO()
            exporter.export_energy_usage(buf, account)

            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = \
                'attachment; filename=%s' % spreadsheet_name

            return buf.getvalue()

        elif row['type'] == 'reebill_details':
            """
            Responds with an excel spreadsheet containing all actual charges, total
            energy and rate structure for all utility bills for the given account,
            or every account (1 per sheet) if 'account' is not given,
            """
            exporter = Exporter(self.state_db)

            # write excel spreadsheet into a StringIO buffer (file-like)
            buf = StringIO()
            exporter.export_reebill_details(buf, account, begin_date, end_date)

            # set MIME type for file download
            cherrypy.response.headers['Content-Type'] = 'application/excel'
            cherrypy.response.headers['Content-Disposition'] = \
                    'attachment; filename=%s.xls'%datetime.now().strftime("%Y%m%d")
            return buf.getvalue()

        elif row['type'] == '12MonthRevenue':
            """Responds with the data from the estimated revenue report
             in the form of an Excel spreadsheet."""
            spreadsheet_name =  'estimated_revenue.xls'

            with open(os.path.join(self.estimated_revenue_report_dir,
                                   'estimated_revenue_report.xls')) as xls_file:
                cherrypy.response.headers['Content-Type'] = 'application/excel'
                cherrypy.response.headers['Content-Disposition'] = \
                    'attachment; filename=%s' % spreadsheet_name

                return xls_file.read()

    @cherrypy.expose
    @cherrypy.tools.authenticate()
    def reconciliation(self, start, limit, *vpath, **params):
        start, limit = int(start), int(limit)
        with open(os.path.join(
                self.reconciliation_report_dir,
                'reconciliation_report.json')) as json_file:
            items = ju.loads('[' + ', '.join(json_file.readlines()) + ']')
            return self.dumps({
                'rows': items[start:start+limit],
                'results': len(items)
            })

    @cherrypy.expose
    @cherrypy.tools.authenticate()
    def estimated_revenue(self, start, limit, *vpath, **params):
        start, limit = int(start), int(limit)
        with open(os.path.join(self.estimated_revenue_report_dir,
                               'estimated_revenue_report.json')) as json_file:
            items = ju.loads(json_file.read())['rows']
            return self.dumps({
                'rows': items[start:start+limit],
                'results': len(items) # total number of items
            })


class ReebillWSGI(WebResource):
    accounts = AccountsResource()
    reebills = ReebillsResource()
    utilitybills = UtilBillResource()
    registers = RegistersResource()
    charges = ChargesResource()
    payments = PaymentsResource()
    reebillcharges = ReebillChargesResource()
    reebillversions = ReebillVersionsResource()
    journal = JournalResource()
    reports = ReportsResource()
    preferences = PreferencesResource()
    issuable = IssuableReebills()
    suppliers = SuppliersResource()
    utilities = UtilitiesResource()
    rateclasses = RateClassesResource()

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
            return json.dumps({
                'success': False,
                'error': 'Incorrect username or password'
            })

        cherrypy.session['user'] = user

        if rememberme == 'on':
            # Create a random session string
            credentials = ''.join('%02x' % ord(x) for x in os.urandom(16))

            user.session_token = credentials
            self.user_dao.save_user(user)

            # this cookie has no expiration,
            # so lasts as long as the browser is open
            cherrypy.response.cookie['username'] = user.username
            cherrypy.response.cookie['c'] = credentials

        self.logger.info(
            'user "%s" logged in: remember me: "%s"' % (username, rememberme))
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
            self.logger.info(
                'user "%s" logged out' % cherrypy.session['user'].username)
            del cherrypy.session['user']

        raise cherrypy.HTTPRedirect('login')

    @cherrypy.expose
    @cherrypy.tools.authenticate_ajax()
    @cherrypy.tools.json_out()
    def ui_configuration(self, **kwargs):
        """Returns the UI javascript file."""
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

        return config_dict

cherrypy.request.hooks.attach('on_end_resource', Session.remove, priority=80)

if __name__ == '__main__':
    app = ReebillWSGI()

    class CherryPyRoot(object):
        reebill = app

    ui_root = join(dirname(realpath(__file__)), 'ui')
    cherrypy_conf = {
        '/': {
            'tools.sessions.on': True,
            'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
        },
        '/reebill/login.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "login.html")
        },
        '/reebill/index.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "index.html")
        },
        '/reebill/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(ui_root, "static")
        },
        '/reebills': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': app.config.get('reebill',
                                                  'reebill_file_path')
        }
    }

    cherrypy.config.update({
        'server.socket_host': app.config.get("reebill", "socket_host"),
        'server.socket_port': app.config.get("reebill", "socket_port")})
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, False)
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, True,
                                     stream=sys.stdout)
    cherrypy.quickstart(CherryPyRoot(), "/", config=cherrypy_conf)
else:
    # WSGI Mode
    ui_root = join(dirname(realpath(__file__)), 'ui')
    cherrypy_conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': ui_root,
            'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
        },
        '/login.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "login.html")
        },
        '/index.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "index.html")
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        },
        '/static/revision.txt': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "../../revision.txt")
        }

    }
    cherrypy.config.update({
        'environment': 'embedded',
        'tools.sessions.on': True,
        'tools.sessions.timeout': 240,
        'request.show_tracebacks': True

    })

    if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
        cherrypy.engine.start()
        atexit.register(cherrypy.engine.stop)
    application = cherrypy.Application(
        ReebillWSGI(), script_name=None, config=cherrypy_conf)
