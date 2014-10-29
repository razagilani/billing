from shutil import rmtree
import subprocess
from time import sleep
from boto.s3.connection import S3Connection
from billing.test import init_test_config
from billing.util.file_utils import make_directories_if_necessary

init_test_config()

import sys
import unittest
from datetime import date
import logging
from mock import Mock

import mongoengine

from os.path import join
from billing import init_config, init_model
from billing.test import testing_utils as test_utils
from billing.core import pricing
from billing.core.model import Supplier, UtilBillLoader, RateClass
from billing.reebill import journal
from billing.reebill.process import Process
from billing.reebill.state import StateDB, Customer, Session, UtilBill, \
    Register, Address
from billing.core.model import Utility
from billing.core.bill_file_handler import BillFileHandler
from billing.reebill.fetch_bill_data import RenewableEnergyGetter
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

from billing.reebill.reebill_file_handler import ReebillFileHandler
from testfixtures import TempDirectory



class TestCaseWithSetup(test_utils.TestCase):
    '''Contains setUp/tearDown code for all test cases that need to use ReeBill
    databases.'''

    @classmethod
    def setUpClass(cls):
        from billing import config
        # create root directory on the filesystem for the FakeS3 server,
        # and inside it, a directory to be used as an "S3 bucket".
        cls.fakes3_root_dir = TempDirectory()
        bucket_name = config.get('bill', 'bucket')
        make_directories_if_necessary(join(cls.fakes3_root_dir.path,
                                           bucket_name))

        # start FakeS3 as a subprocess
        fakes3_args = ['fakes3', '--port', '4567', '--root',
                   cls.fakes3_root_dir.path]
        cls.fakes3_process = subprocess.Popen(fakes3_args)

        # make sure FakeS3 is actually running (and did not immediately exit
        # because, for example, another instance of it is already
        # running and occupying the same port)
        sleep(0.5)
        assert cls.fakes3_process.poll() is None

    @classmethod
    def tearDownClass(cls):
        cls.fakes3_process.kill()
        cls.fakes3_process.wait()
        cls.fakes3_root_dir.cleanup()

    @staticmethod
    def truncate_tables(session):
        for t in ["utilbill_reebill", "register", "payment", "reebill",
                  "charge", "utilbill",  "reading", "reebill_charge",
                  "customer", "rate_class", "supplier", "company", "address"]:
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
        TestCaseWithSetup.truncate_tables(session)
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

        uc = Utility('Test Utility Company Template', ca1, '')
        supplier = Supplier('Test Supplier', ca1, '')

        ca2 = Address('Test Other Utilco Address',
                      '123 Utilco Street',
                      'Utilco City',
                      'XX', '12345')

        other_uc = Utility('Other Utility', ca1, '')
        other_supplier = Supplier('Other Supplier', ca1, '')

        session.add_all([fa_ba1, fa_sa1, fa_ba2, fa_sa2, ub_sa1, ub_ba1,
                        ub_sa2, ub_ba2, uc, ca1, ca2, other_uc, supplier,
                        other_supplier])
        session.flush()
        rate_class = RateClass('Test Rate Class Template', uc)
        session.add(Customer('Test Customer', '99999', .12, .34,
                             'example@example.com', uc, supplier,
                             rate_class,
                             fa_ba1, fa_sa1))

        #Template Customer aka "Template Account" in UI
        c2 = Customer('Test Customer 2', '100000', .12, .34,
                             'example2@example.com', uc, supplier,
                             rate_class,
                             fa_ba2, fa_sa2)
        session.add(c2)

        u1 = UtilBill(c2, UtilBill.Complete, 'gas', uc, supplier,
                             rate_class,
                             ub_ba1, ub_sa1,
                             account_number='Acct123456',
                             period_start=date(2012, 1, 1),
                             period_end=date(2012, 1, 31),
                             target_total=50.00,
                             date_received=date(2011, 2, 3),
                             processed=True)

        u2 = UtilBill(c2, UtilBill.Complete, 'gas', uc, supplier,
                             rate_class,
                             ub_ba2, ub_sa2,
                             account_number='Acct123456',
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

        session.add_all([u1r1, u2r1])
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
        other_rate_class = RateClass('Other Rate Class', other_uc)
        c4 = Customer('Test Customer 3 No Rate Strucutres', '100001', .12, .34,
                             'example2@example.com', other_uc, other_supplier,
                             other_rate_class, c4ba, c4sa)

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

        u = UtilBill(c4, UtilBill.Complete, 'gas', other_uc, other_supplier,
                         other_rate_class, ub_ba, ub_sa,
                         account_number='Acct123456',
                         period_start=date(2012, 1, 1),
                         period_end=date(2012, 1, 31),
                         target_total=50.00,
                         date_received=date(2011, 2, 3),
                         processed=True)
        session.add(u)

    def init_dependencies(self):
        """Configure connectivity to various other systems and databases.
        """
        from billing import config

        logger = logging.getLogger('test')

        # TODO most or all of these dependencies do not need to be instance
        # variables because they're not accessed outside __init__
        self.state_db = StateDB(logger)
        s3_connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                  config.get('aws_s3', 'aws_secret_access_key'),
                                  is_secure=config.get('aws_s3', 'is_secure'),
                                  port=config.get('aws_s3', 'port'),
                                  host=config.get('aws_s3', 'host'),
                                  calling_format=config.get('aws_s3',
                                                            'calling_format'))
        utilbill_loader = UtilBillLoader(Session())
        # TODO make this entire URL configurable instead of just the parts
        url_format = 'https://%s/%%(bucket_name)s/utilbill/%%(key_name)s' % (
                config.get('aws_s3', 'host'))
        self.billupload = BillFileHandler(s3_connection,
                                     config.get('bill', 'bucket'),
                                     utilbill_loader, url_format)

        mock_install_1 = MockSkyInstall(name='example-1')
        mock_install_2 = MockSkyInstall(name='example-2')
        self.splinter = MockSplinter(deterministic=True,
                installs=[mock_install_1, mock_install_2])

        self.rate_structure_dao = pricing.FuzzyPricingModel(utilbill_loader,
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
                config.get('reebillrendering', 'template_directory'),
                config.get('bill', 'billpath'),
                config.get('reebillrendering', 'teva_accounts'))

        ree_getter = RenewableEnergyGetter(self.splinter, logger)

        journal_dao = journal.JournalDAO()

        self.process = Process(self.state_db, self.rate_structure_dao,
                self.billupload, self.nexus_util, bill_mailer, reebill_file_handler,
                ree_getter, journal_dao, logger=logger)

        mongoengine.connect('test', host='localhost', port=27017,
                            alias='journal')

    def setUp(self):
        """Sets up "test" databases in Mongo and MySQL, and crates DAOs:
        ReebillDAO, FuzzyPricingModel, StateDB, Splinter, Process,
        NexusUtil."""
        # make sure FakeS3 server is still running (in theory one of the
        # tests or some other process could cause it to exit)
        assert self.__class__.fakes3_process.poll() is None

        init_config('test/tstsettings.cfg')
        init_model()
        self.maxDiff = None # show detailed dict equality assertion diffs
        self.init_dependencies()
        self.session = Session()
        self.truncate_tables(self.session)
        TestCaseWithSetup.insert_data()

    def tearDown(self):
        '''Clears out databases.'''
        # this helps avoid a "lock wait timeout exceeded" error when a test
        # fails to commit the SQLAlchemy session
        self.session.rollback()
        self.truncate_tables(self.session)
        Session.remove()

        self.temp_dir.cleanup()



if __name__ == '__main__':
    unittest.main()
