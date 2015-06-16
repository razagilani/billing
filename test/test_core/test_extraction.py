from datetime import date, datetime
import os
from unittest import TestCase, skip

from boto.s3.connection import S3Connection
from celery.result import AsyncResult
from mock import Mock, NonCallableMock
from pdfminer.layout import LTPage, LTTextLine

from core import init_model, ROOT_PATH
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import TextExtractor, Field, Applier, \
    Extractor, Main, LayoutExtractor, set_rate_class
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
        self.bill.set_rate_class = Mock()
        def side_effect(arg):
            print arg
        self.bill.set_rate_class = Mock(side_effect=side_effect)

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

        # self.bill.reset_mock()
        # self.applier.apply(Applier.RATE_CLASS, "some rate class", self.bill)
        # self.bill.set_rate_class.assert_called_once_with(RateClass(
        #     utility=self.bill.utility, name="some rate class"))


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
        self.assertIsInstance(errors[0], ExtractionError)
        self.assertIsInstance(errors[1], ApplicationError)

class TextFieldTest(TestCase):
    def setUp(self):
        self.field = TextExtractor.TextField(
            regex=r'([A-Za-z]+ [0-9]{1,2}, [0-9]{4})', type=Field.DATE)
        self.address_field = TextExtractor.TextField(regex=r'(.*)', type=Field.ADDRESS)

    def test_get_value(self):
        self.assertEqual(date(2000, 1, 1),
                         self.field.get_value('January 1, 2000'))

        # regex doesn't match
        with self.assertRaises(MatchError):
            print self.field.get_value('xyz')

        # matched a string but couldn't convert to a date
        with self.assertRaises(ConversionError):
            print self.field.get_value('Somemonth 0, 7689')

    def test_convert_address(self):
        address_str = "MT RAINIER, MD 20712\n2703 QUEENS CHAPEL RD\n"
        address = Address(street="2703 QUEENS CHAPEL RD",
                            city="MT RAINIER", state="MD",
                            postal_code="20712")
        retrieved_address = self.address_field.get_value(address_str)
        self.assertEquals(address, retrieved_address)

class BoundingBoxFieldTest(TestCase):
    def setUp(self):
        #sample extractor
        self.field = LayoutExtractor.BoundingBoxField(
            regex=r"Rate Class:\s+(.*)\s?$", page_num=1,
            bbminx=39, bbminy=715, bbmaxx=105, bbmaxy=725,
            type=Field.STRING,
            applier_key=Applier.RATE_CLASS)

        #sample layout for a bill
        page = Mock(spec=LTPage)
        sample_text = Mock(spec=LTTextLine)
        sample_text.x0 = 39
        sample_text.y0 = 715
        sample_text.x1 = 105
        sample_text.xy = 725
        sample_text.get_text.return_value = "Rate Class: Example"
        page._objs = [sample_text]
        self.pages = [page]

    def test_get_value(self):
        self.assertEqual("Example", self.field.get_value(
            self.pages))

class TextExtractorTest(TestCase):
    def setUp(self):
        self.text = 'Bill Text 1234.5 More Text  '
        self.bfh = Mock(autospec=BillFileHandler)
        self.te = TextExtractor()
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_text.return_value = self.text

    def test_prepare_input(self):
        self.assertEqual(self.text, self.te._prepare_input(self.bill, self.bfh))

class LayoutExtractorTest(TestCase):
    def setUp(self):
        self.layout = [LTPage(pageid=1, bbox=(0,0,0,0), rotate=0)]
        self.bfh = Mock(autospec=BillFileHandler)
        self.le = LayoutExtractor()
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_layout.return_value = self.layout

    def test_prepare_input(self):
        self.assertEqual(self.layout, self.le._prepare_input(self.bill,
            self.bfh))

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
        self.assertEqual([
            Charge('DISTRIBUTION_CHARGE', name='Distribution Charge',
                   target_total=158.7, type=D),
            Charge('CUSTOMER_CHARGE', name='Customer Charge', target_total=14.0,
                   type=D),
            Charge('PGC', name='PGC', target_total=417.91, type=S),
            Charge('PEAK_USAGE_CHARGE', name='Peak Usage Charge',
                   target_total=15.79, type=D),
            Charge('RIGHT_OF_WAY', name='DC Rights-of-Way Fee',
                   target_total=13.42, type=D),
            Charge('SETF', name='Sustainable Energy Trust Fund',
                   target_total=7.06, type=D),
            Charge('EATF', name='Energy Assistance Trust Fund',
                   target_total=3.03, type=D),
            Charge('DELIVERY_TAX', name='Delivery Tax', target_total=39.24,
                   type=D),
            Charge('SALES_TAX', name='Sales Tax', target_total=38.48, type=D),
        ], self.bill.charges)
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

    def test_set_rate_class(self):
        s = Session()
        rate_class = RateClass(utility=self.bill.utility,
                                name="existing test rate class")
        s.add(rate_class)
        s.flush()

        # set bill's rate class to an existing rate class in the database
        set_rate_class(self.bill, "existing test rate class")
        self.assertEqual(rate_class, self.bill.rate_class)

        #set bill's rate class to a new rate class
        set_rate_class(self.bill, "new test rate class")
        self.assertEqual(self.bill.rate_class.utility, self.bill.utility)
        self.assertEqual(self.bill.rate_class.name, "new test rate class")
