from datetime import date
import logging
from os.path import join
import os
from subprocess import CalledProcessError, Popen
from time import sleep
import subprocess
import smtplib

from mock import Mock
from boto.s3.connection import S3Connection
from testfixtures import TempDirectory

from reebill.payment_dao import PaymentDAO
from util.file_utils import make_directories_if_necessary
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
from reebill.users import UserDAO
from reebill.reebill_dao import ReeBillDAO
from reebill import fetch_bill_data as fbd
from reebill.journal import JournalDAO
from nexusapi.nexus_util import MockNexusUtil
from skyliner.mock_skyliner import MockSplinter, MockSkyInstall
from reebill.reebill_file_handler import ReebillFileHandler
from reebill.views import Views
from reebill.bill_mailer import Mailer


def create_nexus_util():
    return MockNexusUtil([
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


def create_bill_file_handler():
    """Return a BillFileHandler instance.

    Note: a BillFileHandler should only be used with a single FakesS3 server
    process. If FakeS3 is stopped and started again the connection will be
    invalid.
    """
    from core import config
    s3_connection = S3Connection(
        config.get('aws_s3', 'aws_access_key_id'),
        config.get('aws_s3', 'aws_secret_access_key'),
        is_secure=config.get('aws_s3', 'is_secure'),
        port=config.get('aws_s3', 'port'),
        host=config.get('aws_s3', 'host'),
        calling_format=config.get('aws_s3', 'calling_format'))
    url_format = 'http://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
        config.get('aws_s3', 'host'), config.get('aws_s3', 'port'))
    return BillFileHandler(s3_connection,
                                   config.get('aws_s3', 'bucket'),
                                   UtilBillLoader(), url_format)


def create_bill_mailer():
    from core import config
    mailer_opts = dict(config.items("mailer"))
    return Mailer(
        mailer_opts['mail_from'],
        mailer_opts['originator'],
        mailer_opts['password'],
        smtplib.SMTP(),
        mailer_opts['smtp_host'],
        mailer_opts['smtp_port'],
        mailer_opts['bcc_list']
    )


def create_utilbill_processor():
        file_handler = create_bill_file_handler()
        pricing_model = pricing.FuzzyPricingModel(UtilBillLoader())
        return UtilbillProcessor(pricing_model, file_handler)


def create_utility_bill_views():
    file_handler = create_bill_file_handler()
    nexus_util = create_nexus_util()
    reebill_dao = ReeBillDAO()
    journal_dao = JournalDAO()
    return Views(reebill_dao, file_handler, nexus_util, journal_dao)


def create_reebill_file_handler():
    from core import config
    return ReebillFileHandler(
        config.get('reebill', 'reebill_file_path'),
        config.get('reebill', 'teva_accounts'))


def create_reebill_objects():
    logger = logging.getLogger('test')

    # TODO most or all of these dependencies do not need to be instance
    # variables because they're not accessed outside __init__
    state_db = ReeBillDAO()
    mock_install_1 = MockSkyInstall(name='example-1')
    mock_install_2 = MockSkyInstall(name='example-2')
    splinter = MockSplinter(deterministic=True,
                                 installs=[mock_install_1, mock_install_2])
    # TODO: 64956642 do not hard code nexus names
    nexus_util = create_nexus_util()
    bill_mailer = Mock()
    reebill_file_handler = create_reebill_file_handler()

    ree_getter = RenewableEnergyGetter(splinter, nexus_util, logger)
    journal_dao = journal.JournalDAO()
    payment_dao = PaymentDAO()

    reebill_processor = ReebillProcessor(
        state_db, payment_dao, nexus_util, bill_mailer,
        reebill_file_handler, ree_getter, journal_dao, logger=logger)
    reebill_views = Views(state_db, create_bill_file_handler(), nexus_util,
                          journal_dao)
    return reebill_processor, reebill_views


def create_reebill_resource_objects():
    from core import config
    logger = logging.getLogger('test')
    nexus_util = create_nexus_util()
    bill_file_handler = create_bill_file_handler()
    utilbill_processor = create_utilbill_processor()
    reebill_processor, _ = create_reebill_objects()
    user_dao = UserDAO()
    journal_dao = JournalDAO()
    payment_dao = PaymentDAO()
    reebill_dao = ReeBillDAO()
    splinter = MockSplinter()
    reebill_file_handler = create_reebill_file_handler()
    utilbill_views = create_utility_bill_views()
    bill_mailer = create_bill_mailer()
    ree_getter = fbd.RenewableEnergyGetter(splinter, nexus_util, logger)
    return (config, logger, nexus_util, user_dao, payment_dao, reebill_dao,
            bill_file_handler, journal_dao, splinter, reebill_file_handler,
            bill_mailer, ree_getter, utilbill_views, utilbill_processor,
            reebill_processor)

class FakeS3Manager(object):
    '''Encapsulates starting and stopping the FakeS3 server process for tests
    that use it.
    This replaces the code related to TestCaseWithSetup.
    '''
    @classmethod
    def start(cls):
        from core import config
        cls.fakes3_root_dir = TempDirectory()
        bucket_name = config.get('aws_s3', 'bucket')
        make_directories_if_necessary(join(cls.fakes3_root_dir.path,
                                           bucket_name))

        # start FakeS3 as a subprocess
        # redirect both stdout and stderr because it prints all its log
        # messages to both
        cls.fakes3_command = 'fakes3 --port %s --root %s' % (
            config.get('aws_s3', 'port'), cls.fakes3_root_dir.path)

        # On Thomas' computer FakeS3 needs to write its output to somewhere,
        # because othewise requests to fakes3 raise a socket timeout.
        cls.fakes3_process = Popen(cls.fakes3_command.split(),
                                   stdout=open(os.devnull, 'w'),
                                   stderr=subprocess.STDOUT)

        # make sure FakeS3 is actually running (and did not immediately exit
        # because, for example, another instance of it is already
        # running and occupying the same port)
        sleep(1)
        cls.check()

    @classmethod
    def check(cls):
        exit_status = cls.fakes3_process.poll()
        if exit_status is not None:
            raise CalledProcessError(exit_status, cls.fakes3_command)

    @classmethod
    def stop(cls):
        cls.fakes3_process.kill()
        cls.fakes3_process.wait()
        cls.fakes3_root_dir.cleanup()
        exit_status = cls.fakes3_process.poll()
        # don't care if it exited with 0 or not
        assert exit_status is not None


class TestCaseWithSetup(test_utils.TestCase):
    '''Shared setup and teardown code for various tests. This class should go
    away, so don't add any new uses of it.
    '''
    def __init__(self):
        raise DeprecationWarning

    @staticmethod
    def insert_data():
        session = Session()
        #Customer Addresses
        fa_ba1 = Address(addressee='Test Customer 1 Billing',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        fa_sa1 = Address(addressee='Test Customer 1 Service',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        fa_ba2 = Address(addressee='Test Customer 2 Billing',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                    postal_code='12345')
        fa_sa2 = Address(addressee='Test Customer 2 Service',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        #Utility Bill Addresses
        ub_sa1 = Address(addressee='Test Customer 2 UB 1 Service',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ub_ba1 = Address(addressee='Test Customer 2 UB 1 Billing',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ub_sa2 = Address(addressee='Test Customer 2 UB 2 Service',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ub_ba2 = Address(addressee='Test Customer 2 UB 2 Billing',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')

        ca1 = Address(addressee='Test Utilco Address',
                      street='123 Utilco Street',
                      city='Utilco City',
                      state='XX',
                      postal_code='12345')

        uc = Utility(name='Test Utility Company Template', address=ca1)
        supplier = Supplier(name='Test Supplier', address=ca1)

        ca2 = Address(addressee='Test Other Utilco Address',
                      street='123 Utilco Street',
                      city='Utilco City',
                      state='XX',
                      postal_code='12345')

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
                                utility_account=utility_account2,
                                payee="Someone Else!")
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

        # replaced registers that were automatically created by the rate class
        # because old tests rely on these specific values
        u1.registers = []
        u1r1 = Register(Register.TOTAL, 'therms', quantity=123.45,
                        description='test description', identifier="M60324",
                        meter_identifier="M60324", reg_type='total')
        u1r1.utilbill = u1
        u2.registers = []
        u2r1 = Register(Register.TOTAL, 'therms', quantity=123.45,
                        description='test description', identifier="M60324",
                        meter_identifier="M60324", reg_type='total')
        u2r1.utilbill = u2
        session.add_all([u1, u2, u1r1, u2r1])
        session.flush()
        session.commit()

        #Utility BIll with no Rate structures
        c4ba = Address(addressee='Test Customer 1 Billing',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        c4sa = Address(addressee='Test Customer 1 Service',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        other_rate_class = RateClass(name='Other Rate Class',
                                     utility=other_uc, service='gas')
        utility_account4 = UtilityAccount(
            'Test Customer 3 No Rate Strucutres', '100001', other_uc,
            other_supplier, other_rate_class, c4ba, c4sa)
        reebill_customer4 = ReeBillCustomer(
            name='Test Customer 3 No Rate Strucutres', discount_rate=.12,
            late_charge_rate=.34, service='thermal',
            bill_email_recipient='example2@example.com',
            utility_account=utility_account4,
            payee="Nextility")

        session.add(utility_account4)
        session.add(reebill_customer4)

        ub_sa = Address(addressee='Test Customer 3 UB 1 Service',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        ub_ba = Address(addressee='Test Customer 3 UB 1 Billing',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')

        u = UtilBill(utility_account4, other_uc, other_rate_class,
                     supplier=other_supplier, billing_address=ub_ba,
                     service_address=ub_sa, period_start=date(2012, 1, 1),
                     period_end=date(2012, 1, 31), target_total=50.00,
                     date_received=date(2011, 2, 3), processed=True)
        session.add(u)
        session.flush()
        session.commit()

