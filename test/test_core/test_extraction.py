from datetime import date, datetime
from celery.exceptions import TaskRevokedError
import os
from unittest import TestCase, skip

from boto.s3.connection import S3Connection
from celery.result import AsyncResult
from mock import Mock, NonCallableMock

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from core.extraction.task import test_bill, reduce_bill_results
from test import init_test_config
init_test_config()

from core import init_model, ROOT_PATH
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Field, Extractor, Main, TextExtractor, \
    verify_field, ExtractorResult, LayoutExtractor
from core.extraction.applier import Applier
from core.model import UtilityAccount, Utility, Session, Address, \
    RateClass, Charge, LayoutElement
from core.model.utilbill import UtilBill, Charge
from core.utilbill_loader import UtilBillLoader
from exc import ConversionError, ExtractionError, MatchError, ApplicationError
from test import init_test_config, clear_db, create_tables
from test.setup_teardown import FakeS3Manager
from util.layout import TEXTLINE, IMAGE, TEXTBOX, PAGE


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

    def test_apply_values(self):
        # TODO: maybe make this independent of UtilBill; it should be in a
        # test for the generic Applier when that is separated from utilbill
        extractor = Mock(autospec=Extractor)
        good = {Applier.START: date(2000,1,1), Applier.CHARGES: 'wrong type',
                'wrong key': 1}
        extractor_errors = {Applier.END: ExtractionError('an error')}
        extractor.get_values.return_value = (good, extractor_errors)
        bfh = Mock(autospec=BillFileHandler)

        success_count, applier_errors = self.applier.apply_values(
            extractor, self.bill, bfh)
        self.assertEqual(1, success_count)
        self.assertEqual(3, len(applier_errors))
        self.assertIsInstance(applier_errors['wrong key'], ApplicationError)
        self.assertIsInstance(applier_errors[Applier.CHARGES], ApplicationError)

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
        f3.get_value = Mock(return_value=date(2000, 1, 1))
        f4 = Field(applier_key='c', enabled=False)

        self.e = Extractor()
        self.e.fields = [f1, f2, f3, f4]
        self.e._prepare_input = Mock(return_value='input string')

        self.utilbill = Mock(autospec=UtilBill)
        self.bill_file_handler = Mock(autospec=BillFileHandler)

        # applying f1 succeeds, applying f3 fails (and f2 never gets applied
        # because its value couldn't be extracted)
        self.applier = Mock(autospec=Applier)
        self.applier.apply.side_effect = [None, ApplicationError]

    def test_get_values(self):
        good, errors = self.e.get_values(self.utilbill, self.bill_file_handler)
        self.assertEqual({'a': 123, 'c': date(2000, 1, 1)}, good)
        self.assertEqual(['b'], errors.keys())
        self.assertIsInstance(errors['b'], ExtractionError)


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

        # multiple matches
        with self.assertRaises(MatchError):
            field_multiple_matches = TextExtractor.TextField(regex=r'(\d+) ('
                                                                   r'\d+)',
                type=Field.FLOAT)
            print self.field.get_value('3342 2321')


class TextExtractorTest(TestCase):
    def setUp(self):
        self.text = 'Bill Text 1234.5 More Text  '
        self.bfh = Mock(autospec=BillFileHandler)
        self.te = TextExtractor()
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_text.return_value = self.text

    def test_prepare_input(self):
        self.assertEqual(self.text, self.te._prepare_input(self.bill, self.bfh))

class VerifyFieldTest(TestCase):
    def setUp(self):
        self.rate_class = Mock(autospec=RateClass)
        self.rate_class.name = "Some Rate Class"

    def test_verify_field(self):
        self.assertTrue(verify_field(Applier.START, date(2015, 07, 04),
            date(2015, 07, 04)))
        self.assertTrue(verify_field(Applier.START, date(2015, 07, 04),
            '2015-07-04'))
        # whitespace in DB is ok
        self.assertTrue(verify_field(Applier.START, '2015-07-04',
            '2015-07-04 '))
        # whitespace in extracted value is not ok
        self.assertFalse(verify_field(Applier.START, '2015-07-04 ',
            '2015-07-04'))
        self.assertFalse(verify_field(Applier.START, '2014-07-04',
            '2015-07-04'))
        self.assertTrue(verify_field(Applier.RATE_CLASS, "Some Rate Class",
            self.rate_class))
        # allowances for capitalization, formatting of spaces
        self.assertTrue(verify_field(Applier.RATE_CLASS, "Some_rate-class",
            self.rate_class))
        self.assertFalse(verify_field(Applier.RATE_CLASS, "Different rate "
                                                          "class",
            self.rate_class))

class LayoutExtractorTest(TestCase):
    def setUp(self):
        self.le1 = LayoutElement(text='hello', page_num=0, x0=0, y0=0,
            x1=100, y1=200, type=TEXTLINE)
        self.le2 = LayoutElement(text='text', page_num=2, x0=0, y0=0,
            x1=100, y1=200, type=TEXTLINE)
        self.le3 = LayoutElement(text='wot', page_num=0, x0=0, y0=200,
            x1=100, y1=200, type=TEXTLINE)
        self.le4 = LayoutElement(text='sample', page_num=1, x0=0, y0=0,
            x1=100, y1=200, type=TEXTLINE)
        self.layout_elts = [[self.le3, self.le1], [self.le4], [self.le2]]

        self.bfh = Mock(autospec=BillFileHandler)
        self.le = LayoutExtractor()
        self.le_with_align = LayoutExtractor(origin_regex='wot', origin_x=10,
            origin_y=10)
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_layout.return_value = self.layout_elts

    def test_prepare_input(self):
        # layout elements, sorted by page and position
        le_input = self.le._prepare_input(self.bill, self.bfh)
        self.assertEqual((self.layout_elts, 0, 0), le_input)

        # check prepare_input with alignment
        aligned_input = self.le_with_align._prepare_input(
            self.bill, self.bfh)
        self.assertEqual((self.layout_elts, -10, 190), aligned_input)


class BoundingBoxFieldTest(TestCase):
    """
    Tests for layout extractor of bounding box fields
    """
    def setUp(self):
        self.le1 = LayoutElement(text='hello', page_num=0, x0=0, y0=0,
            x1=100, y1=200, type=TEXTLINE)
        self.le2 = LayoutElement(text='text', page_num=2, x0=0, y0=0,
            x1=100, y1=200, type=TEXTLINE)
        self.le3 = LayoutElement(text='wot', page_num=0, x0=0, y0=200,
            x1=100, y1=200, type=TEXTLINE)
        self.le4 = LayoutElement(text='sample', page_num=1, x0=0, y0=0,
            x1=100, y1=200, type=TEXTLINE)
        self.le5 = LayoutElement(text='', page_num=1, x0=50, y0=50,
            x1=70, y1=70, type=TEXTLINE)
        self.le6 = LayoutElement(text='woo', page_num=2, x0=50, y0=50,
            x1=70, y1=70, type=TEXTLINE)
        self.layout_elts = [[self.le1, self.le3], [self.le4, self.le5],
                            [self.le2, self.le6]]
        self.bfh = Mock(autospec=BillFileHandler)
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_layout.return_value = self.layout_elts

        # TODO: explicitly create this rather than using LayoutExtractor to
        # do it, so this test doesn't depend on LayoutExtractor
        self.input = LayoutExtractor()._prepare_input(self.bill, self.bfh)

        #add a mis-alignment for testing
        self.input = (self.input[0], 5, 5)

    def test_not_enough_pages(self):
        bb_field = LayoutExtractor.BoundingBoxField(page_num=44)
        with self.assertRaises(ExtractionError):
            bb_field.get_value(self.input)

    def test_get_bounding_box(self):
        bb_field = LayoutExtractor.BoundingBoxField(bbminx=0-5, bbminy=0-5,
            bbmaxx=100-5, bbmaxy=200-5, page_num=2, bbregex='([a-z]ampl[a-z])',
            corner=0)
        self.assertEqual('sample', bb_field.get_value(self.input))

    def test_bbox_alignment_error(self):
        # in this test, forget to align by 5 pixels
        bb_field = LayoutExtractor.BoundingBoxField(bbminx=0, bbminy=0,
        bbmaxx=100, bbmaxy=200, page_num=2, bbregex='([a-z]ampl[a-z])',
        corner=0)
        with self.assertRaises(ExtractionError):
            bb_field.get_value(self.input)

    def test_get_without_bbox(self):
        """
        Test extraction with only a regular expression, instead of a bounding box
        """
        bb_field = LayoutExtractor.BoundingBoxField(page_num=2,
            bbregex='([a-z]ampl[a-z])')
        self.assertEqual('sample', bb_field.get_value(self.input))

        #This should fail with a MatchError, since no layout element matches
        # the regex
        bb_field_fail = LayoutExtractor.BoundingBoxField(
            page_num=2, bbregex='fail', corner=0)
        with self.assertRaises(MatchError):
            bb_field_fail.get_value(self.input)

    def test_multipage_search(self):
        """ Test searching through multiple pages for a field
        """
        bb_multipage_field = LayoutExtractor.BoundingBoxField(
            page_num=1, maxpage=3, bbregex='([a-z]ampl[a-z])')
        self.assertEqual('sample', bb_multipage_field.get_value(self.input))

    def test_offset_regex(self):
        """ Tests using a piece of text as a reference for the actual field.
        In this case, bounding box coordinates are relative to the text that
        matches offset_regex.
        """
        bb_offset = LayoutExtractor.BoundingBoxField(page_num=1, maxpage=3,
            offset_regex=r'text', corner=0, bbminx=50, bbminy=50,
            bbmaxx=60, bbmaxy=60)
        self.assertEqual('woo', bb_offset.get_value(self.input))

    def test_match_empty_text(self):
        """ Test match for an empty string, e.g. in the case of an empty
        layout element or a regex returning an empty string
        """
        bb_field_fail = LayoutExtractor.BoundingBoxField(bbminx=50-5,
            bbminy=50-5, bbmaxx=60-5, bbmaxy=60-5, page_num=2, corner=0)
        with self.assertRaises(ExtractionError):
            bb_field_fail.get_value(self.input)


class TableFieldTest(TestCase):
    """
    Tests for layout extractor of bounding box fields
    """
    def setUp(self):
        # generate of table of elements
        self.layout_elements = [[]]
        for y in range(100, 10, -10):
            for x in range(20, 50, 10):
                elt = LayoutElement(x0=x, y0=y, x1=x+5,
                    y1=y+5, text="%d %d text" % (x, y),
                    type=TEXTLINE)
                self.layout_elements[0].append(elt)
        self.layout_elements[0].append(LayoutElement(x0=0, y0=0, x1=5, y1=5,
            text="not in table", type=TEXTLINE))
        self.bfh = Mock(autospec=BillFileHandler)
        self.bill = Mock(autospec=UtilBill)
        self.bill.get_layout.return_value = self.layout_elements

        # TODO: don't use LayoutExtractor to create this
        self.input = LayoutExtractor()._prepare_input(self.bill, self.bfh)

        #create a second page by copying the first
        self.input[0].extend(self.input[0])

    def test_get_table_boundingbox(self):
        """ Test getting tabular data wihtin a bounding box
        """
        tablefield = LayoutExtractor.TableField(page_num=1, bbminx=30,
            bbminy=30, bbmaxx=45, bbmaxy=45)
        expected_output = [["30 40 text", "40 40 text"],
                            ["30 30 text", "40 30 text"]]
        self.assertEqual(expected_output, tablefield._extract(self.input))

    def test_start_stop_regex(self):
        regex_tablefield = LayoutExtractor.TableField(page_num=1,
            bbminx=30, bbminy=20, bbmaxx=45, bbmaxy=55,
            table_start_regex="30 50 text", table_stop_regex="30 20 text")
        expected_output = [["30 40 text", "40 40 text"],
                            ["30 30 text", "40 30 text"]]
        actual_output = regex_tablefield._extract(self.input)
        self.assertEqual(expected_output, actual_output)

    def test_not_enough_pages(self):
        table_field = LayoutExtractor.TableField(page_num=44)
        with self.assertRaises(ExtractionError):
            table_field.get_value(self.input)

    def test_multipage_table(self):
        multipage_tablefield= LayoutExtractor.TableField(page_num=1,
            bbminx=30, bbminy=30, bbmaxx=45, bbmaxy=45, multipage_table=True,
            nextpage_top=35, maxpage=2)
        # 1st and 2nd rows come from 1st page, 3rd row from 2nd page
        expected_output = [["30 40 text", "40 40 text"],
                            ["30 30 text", "40 30 text"],
                            ["30 30 text", "40 30 text"]]
        actual_output = multipage_tablefield._extract(self.input)
        self.assertEqual(expected_output, actual_output)

    def test_no_values_found(self):
        tablefield= LayoutExtractor.TableField(page_num=1,
            bbminx=30, bbminy=30, bbmaxx=45, bbmaxy=45)
        with self.assertRaises(ExtractionError):
            # give tablefield data representing a single empty page.
            tablefield._extract(([[]], 0, 0))


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
        wg_start_regex = r'(%s)-%s\s*\(\d+ Days\)' % (date_format, date_format)
        wg_end_regex = r'%s-(%s)\s*\(\d+ Days\)' % (date_format, date_format)
        wg_energy_regex = r"Distribution Charge\s+(%s)" % num_format
        wg_next_meter_read_regex = r'Your next meter reading date is (%s)' % \
                                   date_format
        wg_charges_regex = r'(DISTRIBUTION SERVICE.*?(?:Total Washington Gas ' \
                           r'Charges This Period|the easiest way to pay))'
        #wg_rate_class_regex = r'Rate Class:\s+Meter number:\s+(.*\n)\n\n.*'
        # wg_rate_class_regex = r'Rate Class:\s+Meter number:\s+^(.*)$^.*$Next read date'
        wg_rate_class_regex = r'Rate Class:\s+Meter number:\s+([^\n]+).*Next read date'
        tf = TextExtractor.TextField
        e1.fields = [
            TextExtractor.TextField(regex=wg_start_regex, type=Field.DATE,
                                    applier_key=Applier.START),
            TextExtractor.TextField(regex=wg_end_regex, type=Field.DATE,
                                    applier_key=Applier.END),
            TextExtractor.TextField(regex=wg_energy_regex, type=Field.FLOAT,
                                    applier_key=Applier.ENERGY),
            TextExtractor.TextField(regex=wg_next_meter_read_regex,
                                    type=Field.DATE,
                                    applier_key=Applier.NEXT_READ),
            TextExtractor.TextField(regex=wg_charges_regex,
                                    type=Field.WG_CHARGES,
                                    applier_key=Applier.CHARGES),
            TextExtractor.TextField(regex=wg_rate_class_regex,
                                    type=Field.STRING,
                                    applier_key=Applier.RATE_CLASS),
        ]

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
        for expected_charge, actual_charge in zip(expected, self.bill.charges):
            self.assertEqual(expected_charge.rsi_binding,
                             actual_charge.rsi_binding)
            self.assertEqual(expected_charge.name, actual_charge.name)
            self.assertEqual(expected_charge.rate, actual_charge.rate)
            self.assertEqual(expected_charge.target_total,
                             actual_charge.target_total)

        # TODO: this seems to fail with "" as the rate class name, only when
        # run as part of the whole test_extraction module or larger unit,
        # not when run by itself
        # self.assertEqual('Commercial and Industrial Non-heating/Non-cooling',
        #                  self.bill.get_rate_class_name())
        self.assertIsInstance(self.bill.date_extracted, datetime)

    @skip(
        "Broken: when a Field is deleted, the before_update method is called, "
        "but the 'extractor' attribute there is None, and before_delete is "
        "not called")
    def test_created_modified(self):
        self.assertIsNone(self.e1.created)
        self.assertIsNone(self.e1.modified)

        s = Session()
        s.add(self.e1)
        s.add_all(self.e1.fields)
        s.flush()
        last_modified = self.e1.modified
        self.assertIsNotNone(self.e1.created)
        self.assertIsNotNone(last_modified)
        self.assertLessEqual(self.e1.created, last_modified)

        # changing a Field updates the modification date of the Extractor
        self.e1.fields[0].regex = 'something else'
        s.flush()
        self.assertGreater(self.e1.modified, last_modified)
        last_modified = self.e1.modified

        # adding a field
        last_modified = self.e1.modified
        self.e1.fields.append(TextExtractor.TextField(regex='a'))
        s.flush()
        self.assertGreater(self.e1.modified, last_modified)
        last_modified = self.e1.modified

        # deleting a field
        # TODO this doesn't work
        del self.e1.fields[-1]
        s.flush()
        self.assertGreater(self.e1.modified, last_modified)

    def test_test_bill_tasks(self):
        """ Tests the functions in task.py, such as test_bill and
        reduce_bill_results
        """

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
        s = Session()
        s.commit()
        # TODO: session is gone after committing here, so we would have to
        # create a new session and re-load all the objects that are used in
        # the assertions below.

        results = [test_bill(self.e1.extractor_id, self.bill.id),
            TaskRevokedError("Representing a stopped task"),
            Exception("Representing a failed task"), None]
        total_result = reduce_bill_results(results)

        field_names = ['end', 'charges', 'energy', 'start', 'rate class',
            'next read']
        expected_fields = {fname:1 for fname in field_names}
        expected_dates = {'2014-04':
                               {'all_count': 1,
                                'total_count': 1,
                                'any_count': 1,
                                'fields': expected_fields}}
        expected_result = {'total_count': 1,
                           'any_count': 1,
                           'all_count': 1,
                           'nbills': 4,
                           'failed': 1,
                           'stopped': 1,
                           'dates': expected_dates,
                           'fields_fraction':
                               {fname:0 for fname in field_names},
                            'verified_count': 0,
                            'fields': expected_fields}
        self.assertEqual(total_result,expected_result)

        #set up extractor result with non-nullable fields
        extractor_result = ExtractorResult(task_id="", parent_id="",
            bills_to_run=4, started=datetime.utcnow())
        #apply results to extractor result
        extractor_result.set_results(total_result)
        self.assertGreater(extractor_result.finished, extractor_result.started)
        self.assertEqual(extractor_result.total_count, total_result['total_count'])
        self.assertEqual(extractor_result.any_count, total_result['any_count'])
        self.assertEqual(extractor_result.all_count, total_result['all_count'])
        self.assertEqual(extractor_result.verified_count, total_result['verified_count'])

        for fname in expected_fields.keys():
            attr_name = fname.replace(" ", "_")

            #check that field counts are the same
            self.assertEqual(extractor_result.__getattribute__("field_"+attr_name),
                expected_fields[fname])
            # check taht field accuracies
            self.assertEqual(extractor_result.__getattribute__(
                "field_"+attr_name+"_fraction"), expected_result[
                'fields_fraction'][fname])
            #check that monthly field counts are the same
            for date in expected_dates.keys():
                self.assertEqual(extractor_result.__getattribute__(
                    attr_name+"_by_month")[date], str(expected_dates[
                    date]['fields'][fname]))