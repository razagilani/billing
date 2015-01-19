from os.path import dirname, realpath, join
import smtplib
from boto.s3.connection import S3Connection
from sqlalchemy import desc
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
from datetime import datetime, timedelta
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
from core.model import Session, UtilityAccount, Charge
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
        utilbill_loader = UtilBillLoader()
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


class UtilBillResource(RESTResource):

    def handle_get(self, *vpath, **params):
        s = Session()
        # TODO: pre-join with Charge to make this faster, and get rid of limit
        utilbills = s.query(UtilBill).join(UtilityAccount).order_by(
            UtilityAccount.account,
                             desc(UtilBill.period_start)).limit(100).all()
        rows = [{
            'id': ub.id,
            'account': ub.utility_account.account,
            'period_start': ub.period_start,
            'period_end': ub.period_end,
            'service': 'Unknown' if ub.service is None
            else ub.service.capitalize(),
            'total_energy': ub.get_total_energy(),
            'total_charges': ub.target_total,
            'computed_total': ub.get_total_charges(),
            'computed_total': 0,
            # TODO: should these be names or ids or objects?
            'utility': ub.get_utility_name(),
            'supplier': ub.get_supplier_name(),
            'rate_class': ub.get_rate_class_name(),
            'pdf_url': self.bill_file_handler.get_s3_url(ub),
            'service_address': str(ub.service_address),
            'next_estimated_meter_read_date': ub.period_end + timedelta(30),
            'supply_total': 0, # TODO
            'utility_account_number': ub.get_utility_account_number(),
            'secondary_account_number': '', # TODO
            'processed': ub.processed,
        } for ub in utilbills]
        return True, {'rows': rows, 'results': len(rows)}

    def handle_put(self, utilbill_id, *vpath, **params):
        row = cherrypy.request.json
        action = row.pop('action')
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
                supplier=row['supplier'],
                ).column_dict()
            if 'total_energy' in row:
                ub = Session().query(UtilBill).filter_by(id=utilbill_id).one()
                ub.set_total_energy(row['total_energy'])
            self.utilbill_processor.compute_utility_bill(utilbill_id)

        # Reset the action parameters, so the client can coviniently submit
        # the same action again
        result['action'] = ''
        result['action_value'] = ''
        return True, {'rows': result, 'results': 1}

    def handle_delete(self, utilbill_id, *vpath, **params):
        utilbill, deleted_path = self.utilbill_processor.delete_utility_bill_by_id(
            utilbill_id)
        journal.UtilBillDeletedEvent.save_instance(
            cherrypy.session['user'], utilbill.get_nextility_account_number(),
            utilbill.period_start, utilbill.period_end,
            utilbill.service, deleted_path)
        return True, {}


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


class ReebillWSGI(WebResource):
    utilitybills = UtilBillResource()
    registers = RegistersResource()
    charges = ChargesResource()
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
        utilitybills = app

    ui_root = join(dirname(realpath(__file__)), 'ui')
    cherrypy_conf = {
        '/': {
            'tools.sessions.on': True,
            'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
        },
        '/utilitybills/index.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "index.html")
        },
        '/utilitybills/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(ui_root, "static")
        },
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
