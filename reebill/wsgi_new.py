"""
File: wsgi.py
"""
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
user_dao = UserDAO(**dict(config.items('usersdb')))


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
    if not config.get('authentication', 'authenticate'):
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

        user = user_dao.load_by_session_token(credentials)
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


class WebResource(object):

    def __init__(self):
        self.config = config
        self.logger = logging.getLogger('reebill')

        self.session = None

        # create a NexusUtil
        self.nexus_util = NexusUtil(self.config.get('skyline_backend',
                                                    'nexus_web_host'))

        # load users database
        self.user_dao = UserDAO(**dict(self.config.items('usersdb')))

        # create an instance representing the database
        self.statedb_config = dict(self.config.items("statedb"))
        self.state_db = state.StateDB(Session, logger=self.logger)

        # create one BillUpload object to use for all BillUpload-related methods
        self.billUpload = BillUpload(self.config, self.logger)

        # create a MongoReeBillDAO
        self.billdb_config = dict(self.config.items("billdb"))
        self.reebill_dao = mongo.ReebillDAO(
            self.state_db,
            pymongo.Connection(
                self.billdb_config['host'],
                int(self.billdb_config['port'])
            )[self.billdb_config['database']])

        # create a RateStructureDAO
        rsdb_config_section = dict(self.config.items("rsdb"))
        mongoengine.connect(
            rsdb_config_section['database'],
            host=rsdb_config_section['host'],
            port=int(rsdb_config_section['port']),
            alias='ratestructure')
        self.ratestructure_dao = rs.RateStructureDAO(logger=self.logger)

        # configure journal:
        # create a MongoEngine connection "alias" named "journal" with which
        # journal.Event subclasses (in journal.py) can associate themselves by
        # setting meta = {'db_alias': 'journal'}.
        journal_config = dict(self.config.items('journaldb'))
        mongoengine.connect(
            journal_config['database'],
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
                olap_cache_db=self.config.get('skyline_backend',
                                              'olap_database'),
                monguru_options={
                    'olap_cache_host': self.config.get('skyline_backend',
                                                       'olap_host'),
                    'olap_cache_db': self.config.get('skyline_backend',
                                                     'olap_database'),
                    'cartographer_options': {
                        'olap_cache_host': self.config.get('skyline_backend',
                                                           'olap_host'),
                        'olap_cache_db': self.config.get('skyline_backend',
                                                         'olap_database'),
                        'measure_collection': 'skymap',
                        'install_collection': 'skyit_installs',
                        'nexus_host': self.config.get('skyline_backend',
                                                      'nexus_db_host'),
                        'nexus_db': 'nexus',
                        'nexus_collection': 'skyline',
                    },
                },
                cartographer_options={
                    'olap_cache_host': self.config.get('skyline_backend',
                                                       'olap_host'),
                    'olap_cache_db': self.config.get('skyline_backend',
                                                     'olap_database'),
                    'measure_collection': 'skymap',
                    'install_collection': 'skyit_installs',
                    'nexus_host': self.config.get('skyline_backend',
                                                  'nexus_db_host'),
                    'nexus_db': 'nexus',
                    'nexus_collection': 'skyline',
                },
            )

        self.integrate_skyline_backend = self.config.get(
            'runtime',
            'integrate_skyline_backend')

        # create a ReebillRenderer
        self.renderer = render.ReebillRenderer(
            dict(self.config.items('reebillrendering')), self.state_db,
            self.reebill_dao, self.logger)

        self.bill_mailer = Mailer(dict(self.config.items("mailer")))

        self.ree_getter = fbd.RenewableEnergyGetter(self.splinter,
                                                    self.reebill_dao,
                                                    self.logger)

        # create one Process object to use for all related bill processing
        self.process = process.Process(
            self.state_db, self.reebill_dao, self.ratestructure_dao,
            self.billUpload, self.nexus_util, self.bill_mailer, self.renderer,
            self.ree_getter, logger=self.logger)

        # determine whether authentication is on or off
        self.authentication_on = self.config.get('authentication',
                                                 'authenticate')

        self.reconciliation_log_dir = self.config.get(
            'reebillreconciliation', 'log_directory')
        self.reconciliation_report_dir = self.config.get(
            'reebillreconciliation', 'report_directory')

        self.estimated_revenue_log_dir = self.config.get(
            'reebillestimatedrevenue', 'log_directory')
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
    def default(self, *vpath, **params):
        method = getattr(self,
                         "handle_" + cherrypy.request.method.lower(),
                         None)

        if not method:
            methods = [x.replace("handle_", "")
                       for x in dir(self) if x.startswith("handle_")]
            cherrypy.response.headers["Allow"] = ",".join(methods)
            raise cherrypy.HTTPError(405, "Method not implemented.")

        return_value = {}

        self.session = Session()
        try:
            response = method(*vpath, **params)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

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

class AccountsListResource(RESTResource):

    def handle_get(self, *vpath, **params):
        accounts = self.state_db.listAccounts(self.session)
        rows = [{'account': account, 'name': full_name} for account,
                full_name in zip(accounts,
                self.process.full_names_of_accounts(self.session, accounts))]
        return True, {'rows': rows, 'results': len(rows)}


class AccountsResource(RESTResource):
    list = AccountsListResource()

    def handle_get(self, start, limit, filtername=None, *vpath, **params):

        """Handles AJAX request for "Account Processing Status" grid in
        "Accounts" tab."""

        start, limit = int(start), int(limit)

        if not filtername:
            filtername = cherrypy.session['user'].preferences.get(
                'filtername', '')

        sortcol = params.get('sort', None)
        if not sortcol:
            sortcol = cherrypy.session['user'].preferences.get(
                'default_account_sort_field', None)
        if not sortcol:
            sortcol = 'account'

        sortdir = params.get('dir', None)
        if not sortdir:
            sortdir = cherrypy.session['user'].preferences.get(
                'default_account_sort_direction', None)
        if not sortdir:
            sortdir = "DESC"
        if sortdir == 'ASC':
            sortreverse = False
        else:
            sortreverse = True

        count, rows = self.process.list_account_status(
            self.session, start, limit, filtername, sortcol, sortreverse)

        cherrypy.session['user'].preferences[
            'default_account_sort_field'] = sortcol
        cherrypy.session['user'].preferences[
            'default_account_sort_direction'] = sortdir
        cherrypy.session['user'].preferences[
            'filtername'] = filtername
        self.user_dao.save_user(cherrypy.session['user'])

        return True, {'rows': rows, 'results': count}


class IssuableReebills(RESTResource):

    def handle_get(self, start, limit, sort='account', dir='DESC',
                   *vpath, **params):
        start, limit = int(start), int(limit)
        try:
            allowable_diff = cherrypy.session['user'].preferences[
                'difference_threshold']
        except KeyError:
            allowable_diff = UserDAO.default_user.preferences[
                'difference_threshold']

        issuable_reebills = self.process.get_issuable_reebills_dict(
            self.session)
        for reebill_info in issuable_reebills:
            reebill_info['id'] = reebill_info['account'],
            reebill_info['difference'] = abs(
                reebill_info['reebill_total'] - reebill_info['util_total'])
            reebill_info['matching'] = (reebill_info['difference'] <
                                        allowable_diff)

        issuable_reebills.sort(key=lambda d: d[sort],
                               reverse=(dir == 'DESC'))
        issuable_reebills.sort(key=lambda d: d['matching'], reverse=True)
        return True, {'rows': issuable_reebills[start:start+limit],
                      'results': len(issuable_reebills)}


class ReebillsResource(RESTResource):
    issuable = IssuableReebills()

    def handle_get(self, account, start, limit, sort='account', dir='DESC',
                   *vpath, **params):
        start, limit = int(start), int(limit)

        '''Handles GET requests for reebill grid data.'''
        # this is inefficient but length is always <= 120 rows
        rows = sorted(self.process.get_reebill_metadata_json(
            self.session, account), key=itemgetter(sort))
        if dir == 'DESC':
            rows.reverse()

        # "limit" means number of rows to return, so the real limit is
        # start + limit
        result = rows[start: start + limit]
        return True, {'rows': result, 'results': len(rows)}


class UtilBillLastEndDateResource(RESTResource):

    def handle_get(self, account,*vpath, **params):
        the_date = self.state_db.last_utilbill_end_date(self.session, account)
        # (https://www.pivotaltracker.com/story/show/23569087)
        # Date is interpreted as a datetime in the client with 12AM UTC set as
        # its time. This has the effect of the date displayed being off by
        # one day. To fix this we convert to a date time and set it to the
        # end of the dat
        if the_date:
            the_date = datetime(the_date.year, the_date.month, the_date.day,
                                23, 59, 59)
        return True, {'date': the_date}


class UtilBillResource(RESTResource):
    last_end_date = UtilBillLastEndDateResource()

    def handle_get(self, account, start, limit, *vpath, **params):
        start, limit = int(start), int(limit)
        rows, total_count = self.process.get_all_utilbills_json(
            self.session, account, start, limit)
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
        UtilBill.validate_utilbill_period(begin_date, end_date)

        # NOTE 'fileobj.file' is always a CherryPy object; if no
        # file was specified, 'fileobj.file' will be None
        fileobj = params['file_to_upload']

        billstate = UtilBill.Complete if fileobj.file else \
            UtilBill.SkylineEstimated
        self.process.upload_utility_bill(
            self.session, account, service,
            begin_date, end_date, fileobj.file,
            fileobj.filename if fileobj.file else None,
            total=total_charges, state=billstate, utility=None, rate_class=None)

        # Since this is initated by an Ajax request, we will still have to
        # send a {'success', 'true'} parameter
        return True, {'success': 'true'}

    def handle_put(self, utilbill_id, *vpath, **params):
        # convert JSON key/value pairs into arguments for
        # Process.update_utilbill_metadata below
        update_args = {}
        for k, v in cherrypy.request.json.iteritems():
            if k in ('period_start', 'period_end'):
                update_args[k] = datetime.strptime(
                    v, ISO_8601_DATE).date()
            elif k == 'service':
                update_args[k] = v.lower()
            elif k in ('total_charges', 'utility', 'rate_class', 'processed'):
                update_args[k] = v

        self.process.update_utilbill_metadata(self.session, utilbill_id,
                                              **update_args)

        return True, {}

    def handle_delete(self, utilbill_id, account, *vpath, **params):
        utilbill, deleted_path = self.process.delete_utility_bill_by_id(
            self.session, utilbill_id)
        journal.UtilBillDeletedEvent.save_instance(
            cherrypy.session['user'], account,
            utilbill.period_start, utilbill.period_end,
            utilbill.service, deleted_path)
        return True, {}


class ChargesResource(RESTResource):

    def handle_get(self, utilbill_id, reebill_sequence=None,
                   reebill_version=None, *vpath, **params):
        charges_json = self.process.get_utilbill_charges_json(
            self.session, utilbill_id,
            reebill_sequence=reebill_sequence,
            reebill_version=reebill_version)

        return True, {'rows': charges_json, 'total': len(charges_json)}


class RegistersResource(RESTResource):

    def validate_id_components(self, *components):
        if any('/' in c for c in components):
            raise ValueError(('Service names and meter/register ids must '
                              'not contain "/"'))

    def handle_get(self, utilbill_id, reebill_sequence=None,
                   reebill_version=None, *vpath, **params):
        # get dictionaries describing all registers in all utility bills
        registers_json = self.process.get_registers_json(
            self.session, utilbill_id)
        return True, {"rows": registers_json, 'results': len(registers_json)}

    def handle_post(self, utilbill_id, reebill_sequence=None,
                    reebill_version=None, *vpath, **params):
        self.check_modifiable(reebill_sequence, reebill_version)
        new_register = cherrypy.request.json

        self.validate_id_components(new_register.get('meter_id', ''),
                                    new_register.get('register_id', ''))

        # Since the porper response to a REST-POST is only the newly created
        # record, we will request all registers, create a new one, request all
        # registers again and compare the two record register lists
        # TODO: in the future process.new_register should return the newly
        # created register

        # All registers before we create a new one
        registers_json_inital = self.process.get_registers_json(
            self.session, utilbill_id)

        # create the new register
        self.process.new_register(
            self.session, utilbill_id, new_register)

        # All registers after we created a new one
        registers_json = self.process.get_registers_json(
            self.session, utilbill_id)

        # Find the newly added register
        new_register = {}
        for register in registers_json:
            if not register in registers_json_inital:
                new_register = register
                break

        return True, {"rows": new_register, 'results': 1}

    def handle_put(self, service, orig_meter_id, orig_reg_id, utilbill_id,
                   reebill_sequence=None, reebill_version=None, *vpath,
                   **params):
        # Unfortuantely register ids are a string of service, orig_meter_id,
        # and orig_reg_id seperated by '/'
        # ex: gas/new Meter/new Register
        # This means they are passed as arguments in this function
        # Todo: In the future register ids should correspond to the actual
        # register ids in a table, then the id is the only thing that needs
        # to be passed into this function

        self.check_modifiable(reebill_sequence, reebill_version)
        updated_reg = cherrypy.request.json

        self.validate_id_components(orig_meter_id,orig_reg_id)

        # all arguments should be strings, except "quantity",
        # which should be a number
        if 'quantity' in updated_reg:
            assert isinstance(updated_reg['quantity'], (float, int))

        # modify the register using every field in 'updated_reg' except "id"
        del updated_reg['id']
        new_meter_id, new_reg_id = self.process.update_register(
            self.session, utilbill_id, orig_meter_id, orig_reg_id,
            updated_reg)

        registers_json = self.process.get_registers_json(
            self.session, utilbill_id)

        # Only return the updated register
        updated_reg = {}
        for register in registers_json:
            if new_meter_id == register['meter_id'] and new_reg_id == \
                    register['register_id']:
                updated_reg = register
                break

        return True, {"rows": updated_reg, 'results': 1}

    def handle_delete(self, service, orig_meter_id, orig_reg_id, utilbill_id,
                      reebill_sequence=None, reebill_version=None, *vpath,
                      **params):
        # Unfortuantely register ids are a string of service, orig_meter_id,
        # and orig_reg_id seperated by '/'
        # ex: gas/new Meter/new Register
        # This means they are passed as arguments in this function
        # Todo: In the future register ids should correspond to the actual
        # register ids in a table, then the id is the only thing that needs
        # to be passed into this function
        self.check_modifiable(reebill_sequence, reebill_version)

        self.process.delete_register(
            self.session, utilbill_id, orig_meter_id, orig_reg_id,
            reebill_sequence=reebill_sequence, reebill_version=reebill_version)

        return True, {}


class RateStructureResource(RESTResource):

    def handle_get(self, utilbill_id, *vpath, **params):
        rsis = self.process.get_rsis_json(self.session, utilbill_id)
        return True, {'rows': rsis, 'results': len(rsis)}


class PaymentsResource(RESTResource):

    def handle_get(self, account, start, limit, *vpath, **params):
        start, limit = int(start), int(limit)
        payments = self.state_db.payments(self.session, account)
        rows = [payment.to_dict() for payment in payments]
        return True, {'rows': rows[start:start+limit],  'results': len(rows)}

    def handle_post(self, account, *vpath, **params):
        d = cherrypy.request.json['date_received']
        d = datetime.strptime(d, '%Y-%m-%dT%H:%M:%S')
        print "\n\n\n\n", d, type(d)
        new_payment = self.process.create_payment(
            self.session, account, d, "New Entry", 0, d)
        self.session.commit()
        return True, {"rows": new_payment.to_dict(), 'results': 1}

    def handle_put(self, payment_id, *vpath, **params):
        row = cherrypy.request.json
        self.process.update_payment(
            self.session,
            int(payment_id),
            row['date_applied'],
            row['description'],
            row['credit'],
        )
        return True, {"rows": row, 'results': 1}

    def handle_delete(self, account, *vpath, **params):
        return True, {}


class BillToolBridge(WebResource):
    accounts = AccountsResource()
    reebills = ReebillsResource()
    utilitybills = UtilBillResource()
    charges = ChargesResource()
    registers = RegistersResource()
    ratestructure = RateStructureResource()
    payments = PaymentsResource()

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
    cherrypy.quickstart(bridge, "/reebill", config=local_conf)
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
        cherrypy.engine.start()
        atexit.register(cherrypy.engine.stop)
    bridge = BillToolBridge()
    application = cherrypy.Application(bridge, script_name=None, config=None)
