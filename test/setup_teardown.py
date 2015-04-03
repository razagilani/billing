import sys
import unittest
from datetime import date
import logging
from os.path import join
from subprocess import CalledProcessError, Popen
from time import sleep
import subprocess

from mock import Mock
import mongoengine
from boto.s3.connection import S3Connection
from reebill.payment_dao import PaymentDAO
from reebill.reebill_dao import ReeBillDAO

from test import init_test_config
from util.file_utils import make_directories_if_necessary


from core import init_model

from test import testing_utils as test_utils
from core import pricing
from core.model import Supplier, RateClass, UtilityAccount
from core.utilbill_loader import UtilBillLoader
from reebill import journal
from reebill.reebill_model import Session, UtilBill, \
    Register, Address, ReeBillCustomer
from core.model import Utility
from core.bill_file_handler import BillFileHandler
from reebill.fetch_bill_data import RenewableEnergyGetter
from reebill.reebill_processor import ReebillProcessor
from core.utilbill_processor import UtilbillProcessor
from reebill.views import Views
from nexusapi.nexus_util import MockNexusUtil
from skyliner.mock_skyliner import MockSplinter, MockSkyInstall


def init_logging():
    """Initialize logging to debug before we import anything else"""

    ch = logging.StreamHandler(sys.stderr)  #Log to stdout
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)

    rootlogger = logging.getLogger('root')
    rootlogger.setLevel(logging.DEBUG)
    rootlogger.addHandler(ch)

    for logger_name in ['test', 'reebill']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = True

init_logging()

from reebill.reebill_file_handler import ReebillFileHandler
from testfixtures import TempDirectory


class FakeS3Manager(object):
    '''Encapsulates starting and stopping the FakeS3 server process for tests
    that use it.
    This replaces the code related to TestCaseWithSetup.
    '''
    def start(self):
        from core import config
        self.fakes3_root_dir = TempDirectory()
        bucket_name = config.get('aws_s3', 'bucket')
        make_directories_if_necessary(join(self.fakes3_root_dir.path,
                                           bucket_name))

        # start FakeS3 as a subprocess
        # redirect both stdout and stderr because it prints all its log
        # messages to both
        self.fakes3_command = 'fakes3 --port %s --root %s' % (
            config.get('aws_s3', 'port'), self.fakes3_root_dir.path)
        self.fakes3_process = Popen(self.fakes3_command.split(),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        # make sure FakeS3 is actually running (and did not immediately exit
        # because, for example, another instance of it is already
        # running and occupying the same port)
        sleep(0.5)
        self.check()

    def check(self):
        exit_status = self.fakes3_process.poll()
        if exit_status is not None:
            raise CalledProcessError(exit_status, self.fakes3_command)

    def stop(self):
        self.fakes3_process.kill()
        self.fakes3_process.wait()
        self.fakes3_root_dir.cleanup()

class TestCaseWithSetup(test_utils.TestCase):
    '''Shared setup and teardown code for various tests. This class should go
    away, so don't add any new uses of it.
    '''

    @classmethod
    def check_fakes3_process(cls):
        exit_status = cls.fakes3_process.poll()
        if exit_status is not None:
            raise CalledProcessError(exit_status, cls.fakes3_command)

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()
        from core import config
        # create root directory on the filesystem for the FakeS3 server,
        # and inside it, a directory to be used as an "S3 bucket".
        cls.fakes3_root_dir = TempDirectory()
        bucket_name = config.get('aws_s3', 'bucket')
        make_directories_if_necessary(join(cls.fakes3_root_dir.path,
                                           bucket_name))

        # start FakeS3 as a subprocess
        # redirect both stdout and stderr because it prints all its log
        # messages to both
        cls.fakes3_command = 'fakes3 --port %s --root %s' % (
            config.get('aws_s3', 'port'), cls.fakes3_root_dir.path)
        cls.fakes3_process = Popen(cls.fakes3_command.split(),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        # make sure FakeS3 is actually running (and did not immediately exit
        # because, for example, another instance of it is already
        # running and occupying the same port)
        sleep(0.5)
        cls.check_fakes3_process()
        # stdin, stout = cls.fakes3_process.communicate()
        # print stdin.read()
        pass

    @classmethod
    def tearDownClass(cls):
        cls.fakes3_process.kill()
        cls.fakes3_process.wait()
        cls.fakes3_root_dir.cleanup()

    @staticmethod
    def truncate_tables():
        session = Session()
        Session.rollback()
        for t in [
            "altitude_utility",
            "altitude_supplier",
            "altitude_account",
            "altitude_bill",
            "utilbill_reebill",
            "register",
            "payment",
            "reebill",
            "charge",
            "utilbill",
            "reading",
            "reebill_charge",
            "reebill_customer",
            "brokerage_account",
            "utility_account",
            "rate_class",
            "supplier",
            "utility",
            "address",
            "billentry_role_user",
            "billentry_user",
            "billentry_role"
        ]:
            session.execute("delete from %s" % t)
        session.commit()

    @staticmethod
    def init_logging():
        """Setup NullHandlers for test and root loggers.
        """
        testlogger = logging.getLogger('test')
        testlogger.addHandler(logging.NullHandler())
        testlogger.propagate = False

    @staticmethod
    def insert_data():
        session = Session()
        TestCaseWithSetup.truncate_tables()
        #Customer Addresses
        fa_ba1 = Address('Test Customer 1 Billing',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        fa_sa1 = Address('Test Customer 1 Service',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        fa_ba2 = Address('Test Customer 2 Billing',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        fa_sa2 = Address('Test Customer 2 Service',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        #Utility Bill Addresses
        ub_sa1 = Address('Test Customer 2 UB 1 Service',
                         '123 Test Street',
                         'Test City',
                         'XX',
                         '12345')
        ub_ba1 = Address('Test Customer 2 UB 1 Billing',
                         '123 Test Street',
                         'Test City',
                         'XX',
                         '12345')
        ub_sa2 = Address('Test Customer 2 UB 2 Service',
                         '123 Test Street',
                         'Test City',
                         'XX',
                         '12345')
        ub_ba2 = Address('Test Customer 2 UB 2 Billing',
                         '123 Test Street',
                         'Test City',
                         'XX',
                         '12345')

        ca1 = Address('Test Utilco Address',
                      '123 Utilco Street',
                      'Utilco City',
                      'XX', '12345')

        uc = Utility(name='Test Utility Company Template', address=ca1)
        supplier = Supplier(name='Test Supplier', address=ca1)

        ca2 = Address('Test Other Utilco Address',
                      '123 Utilco Street',
                      'Utilco City',
                      'XX', '12345')

        other_uc = Utility(name='Other Utility', address=ca1)
        other_supplier = Supplier(name='Other Supplier', address=ca1)

        session.add_all([fa_ba1, fa_sa1, fa_ba2, fa_sa2, ub_sa1, ub_ba1,
                        ub_sa2, ub_ba2, uc, ca1, ca2, other_uc, supplier,
                        other_supplier])
        session.flush()
        rate_class = RateClass(name='Test Rate Class Template', utility=uc,
                               service='gas')
        utility_account = UtilityAccount(
            'Test Customer', '99999', uc, supplier, rate_class, fa_ba1, fa_sa1,
            account_number='1')
        reebill_customer = ReeBillCustomer(name='Test Customer',
                                discount_rate=.12, late_charge_rate=.34,
                                service='thermal',
                                bill_email_recipient='example@example.com',
                                utility_account=utility_account)
        session.add(utility_account)
        session.add(reebill_customer)

        #Template Customer aka "Template Account" in UI
        utility_account2 = UtilityAccount(
            'Test Customer 2', '100000', uc, supplier, rate_class, fa_ba2,
            fa_sa2, account_number='2')
        reebill_customer2 = ReeBillCustomer(name='Test Customer 2',
                                discount_rate=.12, late_charge_rate=.34,
                                service='thermal',
                                bill_email_recipient='example2@example.com',
                                utility_account=utility_account2)
        session.add(utility_account2)
        session.add(reebill_customer2)

        u1 = UtilBill(utility_account2, uc,
                             rate_class, supplier=supplier,
                             billing_address=ub_ba1, service_address=ub_sa1,
                             period_start=date(2012, 1, 1),
                             period_end=date(2012, 1, 31),
                             target_total=50.00,
                             date_received=date(2011, 2, 3),
                             processed=True)

        u2 = UtilBill(utility_account2, uc, rate_class, supplier=supplier,
                             billing_address=ub_ba2, service_address=ub_sa2,
                             period_start=date(2012, 2, 1),
                             period_end=date(2012, 2, 28),
                             target_total=65.00,
                             date_received=date(2011, 3, 3),
                             processed=True)

        u1r1 = Register(u1, "test description", "M60324",
                        'therms', False, "total", None, "M60324",
                        quantity=123.45,
                        register_binding="REG_TOTAL")
        u2r1 = Register(u2, "test description", "M60324",
                      'therms', False, "total", None, "M60324",
                      quantity=123.45,
                      register_binding='REG_TOTAL')

        session.add_all([u1, u2, u1r1, u2r1])
        session.flush()
        session.commit()

        #Utility BIll with no Rate structures
        c4ba = Address('Test Customer 1 Billing',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        c4sa = Address('Test Customer 1 Service',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        other_rate_class = RateClass(name='Other Rate Class',
                                     utility=other_uc, service='gas')
        utility_account4 = UtilityAccount(
            'Test Customer 3 No Rate Strucutres', '100001', other_uc,
            other_supplier, other_rate_class, c4ba, c4sa)
        reebill_customer4 = ReeBillCustomer(
            name='Test Customer 3 No Rate Strucutres', discount_rate=.12,
            late_charge_rate=.34, service='thermal',
            bill_email_recipient='example2@example.com',
            utility_account=utility_account4)

        session.add(utility_account4)
        session.add(reebill_customer4)

        ub_sa = Address('Test Customer 3 UB 1 Service',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')
        ub_ba = Address('Test Customer 3 UB 1 Billing',
                     '123 Test Street',
                     'Test City',
                     'XX',
                     '12345')

        u = UtilBill(utility_account4, other_uc, other_rate_class,
                     supplier=other_supplier, billing_address=ub_ba,
                     service_address=ub_sa, period_start=date(2012, 1, 1),
                     period_end=date(2012, 1, 31), target_total=50.00,
                     date_received=date(2011, 2, 3), processed=True)
        session.add(u)
        session.flush()
        session.commit()

    def init_dependencies(self):
        """Configure connectivity to various other systems and databases.
        """
        from core import config

        logger = logging.getLogger('test')

        # TODO most or all of these dependencies do not need to be instance
        # variables because they're not accessed outside __init__
        self.state_db = ReeBillDAO()
        s3_connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                  config.get('aws_s3', 'aws_secret_access_key'),
                                  is_secure=config.get('aws_s3', 'is_secure'),
                                  port=config.get('aws_s3', 'port'),
                                  host=config.get('aws_s3', 'host'),
                                  calling_format=config.get('aws_s3',
                                                            'calling_format'))
        utilbill_loader = UtilBillLoader()
        url_format = 'http://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
                config.get('aws_s3', 'host'), config.get('aws_s3', 'port'))
        self.billupload = BillFileHandler(s3_connection,
                                     config.get('aws_s3', 'bucket'),
                                     utilbill_loader, url_format)

        mock_install_1 = MockSkyInstall(name='example-1')
        mock_install_2 = MockSkyInstall(name='example-2')
        self.splinter = MockSplinter(deterministic=True,
                installs=[mock_install_1, mock_install_2])

        self.pricing_model = pricing.FuzzyPricingModel(utilbill_loader,
                                                            logger=logger)

        # TODO: 64956642 do not hard code nexus names
        self.nexus_util = MockNexusUtil([
            {
                'billing': '99999',
                'olap': 'example-1',
                'casualname': 'Example 1',
                'primus': '1785 Massachusetts Ave.',
            },
            {
                'billing': '88888',
                'olap': 'example-2',
                'casualname': 'Example 2',
                'primus': '1786 Massachusetts Ave.',
            },
            {
                'billing': '100000',
                'olap': 'example-3',
                'casualname': 'Example 3',
                'primus': '1787 Massachusetts Ave.',
            },
            {
                'billing': '100001',
                'olap': 'example-4',
                'casualname': 'Example 4',
                'primus': '1788 Massachusetts Ave.',
                },
        ])
        mailer_opts = dict(config.items("mailer"))
        bill_mailer = Mock()

        self.temp_dir = TempDirectory()
        reebill_file_handler = ReebillFileHandler(
                config.get('reebill', 'reebill_file_path'),
                config.get('reebill', 'teva_accounts'))

        ree_getter = RenewableEnergyGetter(self.splinter, logger)
        journal_dao = journal.JournalDAO()
        self.payment_dao = PaymentDAO()

        self.utilbill_processor = UtilbillProcessor(
            self.pricing_model, self.billupload, logger=logger)
        self.views = Views(self.state_db, self.billupload, self.nexus_util,
                           journal_dao)
        self.reebill_processor = ReebillProcessor(
            self.state_db, self.payment_dao, self.nexus_util, bill_mailer,
            reebill_file_handler, ree_getter, journal_dao, logger=logger)

        mongoengine.connect('test', host='localhost', port=27017,
                            alias='journal')

    def setUp(self):
        """Sets up "test" databases in Mongo and MySQL, and crates DAOs:
        ReebillDAO, FuzzyPricingModel, ReeBillDAO, Splinter, Process,
        NexusUtil."""
        # make sure FakeS3 server is still running (in theory one of the
        # tests or some other process could cause it to exit)
        self.__class__.check_fakes3_process()

        self.maxDiff = None # show detailed dict equality assertion diffs
        self.init_dependencies()
        self.session = Session()
        self.truncate_tables()
        TestCaseWithSetup.insert_data()
        self.session.flush()

    def tearDown(self):
        '''Clears out databases.'''
        # this helps avoid a "lock wait timeout exceeded" error when a test
        # fails to commit the SQLAlchemy session
        Session.remove()
        self.session.rollback()
        self.truncate_tables()
        self.temp_dir.cleanup()



if __name__ == '__main__':
    unittest.main()
