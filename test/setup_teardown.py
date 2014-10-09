import smtplib
from billing.test import init_test_config
init_test_config()

import sys
import unittest
from datetime import date
import logging
from boto.s3.connection import S3Connection
from billing import init_config, init_model

import mongoengine

from billing import init_config, init_model
from billing.test import testing_utils as test_utils
from billing.core import rate_structure
from billing.reebill import journal
from billing.reebill.process import Process
from billing.reebill.state import StateDB, Customer, Session, UtilBill, \
    Register, Address
from billing.core.model import Utility
from billing.core.billupload import BillUpload
from billing.reebill.bill_mailer import Mailer
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

from billing.reebill.render import ReebillFileHandler
from testfixtures import TempDirectory



class TestCaseWithSetup(test_utils.TestCase):
    '''Contains setUp/tearDown code for all test cases that need to use ReeBill
    databases.'''

    @staticmethod
    def truncate_tables(session):
        for t in ["utilbill_reebill", "register", "utilbill", "payment",
                  "reebill", "customer", "company", "charge", "address",
                  "reading", "reebill_charge"]:
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

        uc = Utility('Test Utility Company Template', ca1)

        ca2 = Address('Test Other Utilco Address',
                      '123 Utilco Street',
                      'Utilco City',
                      'XX', '12345')

        other_uc = Utility('Other Utility', ca1)

        session.add_all([fa_ba1, fa_sa1, fa_ba2, fa_sa2, ub_sa1, ub_ba1,
                         ub_sa2, ub_ba2, uc, ca1, ca2, other_uc])
        session.flush()

        session.add(Customer('Test Customer', '99999', .12, .34,
                             'example@example.com', uc,
                             'Test Rate Class Template', fa_ba1, fa_sa1))

        #Template Customer aka "Template Account" in UI
        c2 = Customer('Test Customer 2', '100000', .12, .34,
                             'example2@example.com', uc,
                             'Test Rate Class Template', fa_ba2, fa_sa2)
        session.add(c2)

        u1 = UtilBill(c2, UtilBill.Complete, 'gas', uc,
                             'Test Rate Class Template',  ub_ba1, ub_sa1,
                             account_number='Acct123456',
                             period_start=date(2012, 1, 1),
                             period_end=date(2012, 1, 31),
                             target_total=50.00,
                             date_received=date(2011, 2, 3),
                             processed=True)

        u2 = UtilBill(c2, UtilBill.Complete, 'gas', uc,
                             'Test Rate Class Template', ub_ba2, ub_sa2,
                             account_number='Acct123456',
                             period_start=date(2012, 2, 1),
                             period_end=date(2012, 2, 28),
                             target_total=65.00,
                             date_received=date(2011, 3, 3),
                             processed=True)

        u1r1 = Register(u1, "test description", 123.45, "therms", "M60324",
                      False, "total", "REG_TOTAL", None, "M60324")
        u2r1 = Register(u2, "test description", 123.47, "therms", "M60324",
                      False, "total", "REG_TOTAL", None, "M60324")

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
        c4 = Customer('Test Customer 3 No Rate Strucutres', '100001', .12, .34,
                             'example2@example.com', other_uc,
                             'Other Rate Class', c4ba, c4sa)

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
        u = UtilBill(c4, UtilBill.Complete, 'gas', other_uc,
                         'Other Rate Class',  ub_ba, ub_sa,
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
        init_config('test/tstsettings.cfg')
        self.config = config

        # TODO most or all of these dependencies do not need to be instance
        # variables because they're not accessed outside __init__
        self.state_db = StateDB(logger)
        self.billupload = BillUpload.from_config()

        mock_install_1 = MockSkyInstall(name='example-1')
        mock_install_2 = MockSkyInstall(name='example-2')
        self.splinter = MockSplinter(deterministic=True,
                installs=[mock_install_1, mock_install_2])

        self.rate_structure_dao = rate_structure.RateStructureDAO(
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
        mailer_opts = dict(self.config.items("mailer"))
        server = smtplib.SMTP(mailer_opts['smtp_host'], mailer_opts['smtp_port'])
        bill_mailer = Mailer(
                mailer_opts['mail_from'],
                mailer_opts['originator'],
                mailer_opts['password'],
                mailer_opts['template_file_name'],
                server,
                mailer_opts['bcc_list']
        )

        self.temp_dir = TempDirectory()
        reebill_file_handler = ReebillFileHandler(self.temp_dir.path)

        ree_getter = RenewableEnergyGetter(self.splinter, logger)

        journal_dao = journal.JournalDAO()

        self.process = Process(self.state_db, self.rate_structure_dao,
                self.billupload, self.nexus_util, bill_mailer, reebill_file_handler,
                ree_getter, journal_dao, logger=logger)

        mongoengine.connect('test', host='localhost', port=27017,
                            alias='journal')

    def setUp(self):
        """Sets up "test" databases in Mongo and MySQL, and crates DAOs:
        ReebillDAO, RateStructureDAO, StateDB, Splinter, Process,
        NexusUtil."""
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
