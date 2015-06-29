from datetime import date, datetime
import os
from unittest import TestCase, skip

from boto.s3.connection import S3Connection
from celery.result import AsyncResult
from mock import Mock, NonCallableMock

from core import init_model, ROOT_PATH
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Field, Extractor, Main, TextExtractor
from core.extraction.applier import Applier
from core.model import UtilBill, UtilityAccount, Utility, Session, Address, \
    RateClass, Charge
from core.utilbill_loader import UtilBillLoader
from exc import ConversionError, ExtractionError, MatchError, ApplicationError
from test import init_test_config, clear_db, create_tables
from test.setup_teardown import FakeS3Manager


class FieldTest(TestCase):
    def setUp(self):
        self.field = Field()
        self.field._extract = Mock(return_value='value string')
        self.input = 'input string'

        # mock the type conversion function by putting a mock into the TYPES
        # dictionary. maybe there's a way to do this without modifying the
        # class.
        self.type_convert_func = Mock(return_value=1)
        self.field.TYPES[Field.STRING] = self.type_convert_func

    def test_get_value(self):
        value = self.field.get_value(self.input)
        self.field._extract.assert_called_once_with(self.input)
        self.type_convert_func.assert_called_once_with('value string')
        self.assertEqual(1, value)

    def test_convert_error(self):
        self.type_convert_func.side_effect = Exception
        with self.assertRaises(ConversionError):
            self.field.get_value(self.input)


class ApplierTest(TestCase):
    def setUp(self):
        self.applier = Applier.get_instance()
        self.bill = NonCallableMock()
        self.bill.set_total_energy = Mock()
        self.bill.set_next_meter_read_date = Mock()

    def test_default_applier(self):
        d = date(2000,1,1)
        self.applier.apply(Applier.START, d, self.bill)
        self.assertEqual(d, self.bill.period_start)

        self.bill.reset_mock()
        self.applier.apply(Applier.END, d, self.bill)
        self.assertEqual(d, self.bill.period_end)

        self.bill.reset_mock()
        self.applier.apply(Applier.NEXT_READ, d, self.bill)
        self.bill.set_next_meter_read_date.assert_called_once_with(d)

        self.bill.reset_mock()
        self.applier.apply(Applier.ENERGY, 123.456, self.bill)
        self.bill.set_total_energy.assert_called_once_with(123.456)

    def test_errors(self):
        # wrong key
        with self.assertRaises(ApplicationError):
            self.applier.apply('wrong key', 1, self.bill)

        # wrong value type
        with self.assertRaises(ApplicationError):
            self.applier.apply(Applier.START, 1, self.bill)

        # exception in target method
        self.bill.reset_mock()
        self.bill.set_total_energy.side_effect = Exception
        with self.assertRaises(ApplicationError):
            self.applier.apply(Applier.ENERGY, 123.456, self.bill)


class ExtractorTest(TestCase):
    def setUp(self):
        # a Mock can't be used as a Field because it lacks SQLAlchemy
        # attributes, but its methods can be mocked.
        f1 = Field(applier_key='a')
        f1.get_value = Mock(return_value=123)
        f2 = Field(applier_key='b')
        f2.get_value = Mock(side_effect=ExtractionError)
        f3 = Field(applier_key='c')
        f3.get_value = Mock(return_value=date(2000,1,1))

        self.e = Extractor()
        self.e.fields = [f1, f2, f3]
        self.e._prepare_input = Mock(return_value='input string')

        self.utilbill = Mock(autospec=UtilBill)
        self.bill_file_handler = Mock(autospec=BillFileHandler)

        # applying f1 succeeds, applying f3 fails (and f2 never gets applied
        # because its value couldn't be extracted)
        self.applier = Mock(autospec=Applier)
        self.applier.apply.side_effect = [None, ApplicationError]

    def test_apply_values(self):
        count, errors = self.e.apply_values(
            self.utilbill, self.bill_file_handler, self.applier)
        self.assertEqual(1, count)
        self.assertEqual(2, len(errors))
        applier_keys, exceptions = zip(*errors)
        self.assertEqual(('b', 'c'), applier_keys)
        self.assertIsInstance(exceptions[0], ExtractionError)
        self.assertIsInstance(exceptions[1], ApplicationError)


class TextFieldTest(TestCase):
    def setUp(self):
        self.field = TextExtractor.TextField(
            regex=r'([A-Za-z]+ [0-9]{1,2}, [0-9]{4})', type=Field.DATE)

    def test_get_value(self):
        self.assertEqual(date(2000, 1, 1),
                         self.field.get_value('January 1, 2000'))

        # regex doesn't match
        with self.assertRaises(MatchError):
            print self.field.get_value('xyz')

        # matched a string but couldn't convert to a date
        with self.assertRaises(ConversionError):
            print self.field.get_value('Somemonth 0, 7689')


class TextExtractorTest(TestCase):
    def setUp(self):
        self.text = 'Bill Text 1234.5 More Text  '
        self.bfh = Mock(autospec=BillFileHandler)
        self.te = TextExtractor()
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_text.return_value = self.text

    def test_prepare_input(self):
        self.assertEqual(self.text, self.te._prepare_input(self.bill, self.bfh))


class TestIntegration(TestCase):
    """Integration test for all extraction-related classes with real bill and
    database.
    """
    EXAMPLE_FILE_PATH = os.path.join(ROOT_PATH,
                                     'test/test_core/data/utility_bill.pdf')

    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()
        FakeS3Manager.start()

    @classmethod
    def tearDownClass(cls):
        FakeS3Manager.stop()

    def setUp(self):
        clear_db()

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
        self.bfh = BillFileHandler(s3_connection, config.get('aws_s3', 'bucket'),
                              UtilBillLoader(), url_format)

        # create utility and rate class
        utility = Utility(name='washington gas')
        utility.charge_name_map = {
            'Distribution Charge': 'DISTRIBUTION_CHARGE',
            'Customer Charge': 'CUSTOMER_CHARGE',
            'PGC': 'PGC',
            'Peak Usage Charge': 'PEAK_USAGE_CHARGE',
            'DC Rights-of-Way Fee': 'RIGHT_OF_WAY',
            'Sustainable Energy Trust Fund': 'SETF',
            'Energy Assistance Trust Fund': 'EATF',
            'Delivery Tax': 'DELIVERY_TAX',
            'Sales Tax': 'SALES_TAX',
        }
        rate_class = RateClass(utility=utility)
        account = UtilityAccount('', '123', None, None, None, Address(),
                                 Address())

        # create bill with file
        self.bill = UtilBill(account, utility, rate_class)
        with open(self.EXAMPLE_FILE_PATH, 'rb') as bill_file:
            self.bfh.upload_file_for_utilbill(self.bill, bill_file)
        self.bill.date_extracted = None

        # create extractor
        e1 =  TextExtractor(name='Example')
        date_format = r'[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4}'
        num_format = r'[0-9,\.]+'
        e1.fields = [
            TextExtractor.TextField(
                regex=r'(%s)-%s\s*\(\d+ Days\)' % (date_format, date_format),
                type=Field.DATE, applier_key='start'),
            TextExtractor.TextField(regex=r'%s-(%s)\s*\(\d+ Days\)' % (
                date_format, date_format),
                type=Field.DATE, applier_key='end'),
            TextExtractor.TextField(
                regex=r"Distribution Charge\s+(%s)" % num_format,
                type=Field.FLOAT, applier_key='energy'),
            TextExtractor.TextField(regex=r'Your next meter reading date is ('
                                          r'%s)' % date_format,
                type=Field.DATE, applier_key='next read'),
            TextExtractor.TextField(regex=r'(DISTRIBUTION SERVICE.*?(?:Total Washington Gas Charges This Period|the easiest way to pay))',
                           type=Field.WG_CHARGES, applier_key='charges')
        ]
        # wg_service_address_regex = r'(?:Days\)|Service address:)\s+(.+?)\s+(?:Questions|Please)'
        # # for billing address, before "check here to donate", get all characters that are not a double newline
        # wg_billing_address_regex = r'\n\n([^\n]|\n(?!\n))*\n\nCheck here to donate'
        # wg_rate_class_regex = r'rate class:\s+meter number:\s+([^\n]+)'

        e2 = TextExtractor(name='Another')
        Session().add_all([self.bill, e1, e2])
        self.e1, self.e2 = e1, e2

    def tearDown(self):
        clear_db()

    def test_extract_real_bill(self):
        Main(self.bfh).extract(self.bill)

        self.assertEqual(date(2014, 3, 19), self.bill.period_start)
        self.assertEqual(date(2014, 4, 16), self.bill.period_end)
        self.assertEqual(504.6, self.bill.get_total_energy())
        self.assertEqual(date(2014, 5, 15),
                         self.bill.get_next_meter_read_date())
        D, S = Charge.DISTRIBUTION, Charge.SUPPLY
        expected = [
            Charge('DISTRIBUTION_CHARGE', name='Distribution Charge',
                   target_total=158.7, type=D, unit='therms'),
            Charge('CUSTOMER_CHARGE', name='Customer Charge', target_total=14.0,
                   type=D, unit='therms'),
            Charge('PGC', name='PGC', target_total=417.91, type=S,
                   unit='therms'),
            Charge('PEAK_USAGE_CHARGE', name='Peak Usage Charge',
                   target_total=15.79, type=D, unit='therms'),
            Charge('RIGHT_OF_WAY', name='DC Rights-of-Way Fee',
                   target_total=13.42, type=D, unit='therms'),
            Charge('SETF', name='Sustainable Energy Trust Fund',
                   target_total=7.06, type=D, unit='therms'),
            Charge('EATF', name='Energy Assistance Trust Fund',
                   target_total=3.03, type=D, unit='therms'),
            Charge('DELIVERY_TAX', name='Delivery Tax', target_total=39.24,
                   type=D, unit='therms'),
            Charge('SALES_TAX', name='Sales Tax', target_total=38.48, type=D,
                   unit='therms')]
        self.assertEqual(expected, self.bill.charges)
        self.assertIsInstance(self.bill.date_extracted, datetime)

    @skip('not working yet')
    def test_created_modified(self):
        self.assertIsNone(self.e1.created)
        self.assertIsNone(self.e1.modified)

        s = Session()
        s.add(self.e1)
        s.flush()
        modified = self.e1.modified
        self.assertIsNotNone(self.e1.created)
        self.assertIsNotNone(modified)
        self.assertLessEqual(self.e1.created, modified)

        self.e1.fields[0].name = 'new name'
        s.flush()
        self.assertGreater(self.e1.modified, modified)

    @skip('this task was deleted, might come back')
    def test_test_extractor(self):
        # TODO: it might be possible to write this as a unit test, without the
        # database. database queries in tasks would be moved to a DAO like
        # UtilbillLoader, which could be mocked.

        # do everything in memory without requiring real celery server
        from core import celery
        celery.conf.update(
            dict(BROKER_BACKEND='memory', CELERY_ALWAYS_EAGER=True))

        # primary keys need to be set so they can be queried. also,
        # the transaction needs to be committed because the task is a
        # separate thread so it has a different transaction
        Session().commit()
        # TODO: session is gone after committing here, so we would have to
        # create a new session and re-load all the objects that are used in
        # the assertions below.

        result = test_extractor.apply(args=[self.e1.extractor_id])
        metadata = AsyncResult(result.task_id).info
        self.assertEqual((1, 1, 1), result.get())
        self.assertEqual({'all_count': 1, 'any_count': 1, 'total_count': 1},
            metadata)

        result = test_extractor.apply(args=[self.e2.extractor_id])
        metadata = AsyncResult(result.task_id).info
        self.assertEqual((0, 0, 1), result.get())
        self.assertEqual({'all_count': 0, 'any_count': 0, 'total_count': 1},
                         metadata)