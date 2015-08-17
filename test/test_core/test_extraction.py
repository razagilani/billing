from datetime import date, datetime
from celery.exceptions import TaskRevokedError
from dateutil.relativedelta import relativedelta
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
from billentry.billentry_model import BEUtilBill
from core.extraction.task import test_bill, reduce_bill_results
from core.extraction.type_conversion import convert_unit, convert_address, \
    process_charge, convert_table_charges
from test import init_test_config

from core import init_model, ROOT_PATH
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Field, Extractor, Main, TextExtractor, \
    verify_field, ExtractorResult, LayoutExtractor
from core.extraction.applier import Applier, UtilBillApplier, Validator
from core.model import UtilityAccount, Utility, Session, Address, \
    RateClass, Charge, LayoutElement, BoundingBox
from core.model.utilbill import UtilBill, Charge
from core.utilbill_loader import UtilBillLoader
from exc import ConversionError, ExtractionError, MatchError, ApplicationError
from test import init_test_config, clear_db, create_tables
from test.setup_teardown import FakeS3Manager
from util.layout import TEXTLINE, IMAGE, TEXTBOX, PAGE

def setUpModule():
    init_test_config()

class FieldTest(TestCase):
    def setUp(self):
        self.field = Field()
        self.field._extract = Mock(return_value='value string')
        self.input = 'input string'

        # mock the type conversion function by putting a mock into the TYPES
        # dictionary. maybe there's a way to do this without modifying the
        # class.
        self.type_convert_func = Mock(return_value=1)
        self.old_type_func = self.field.TYPES[Field.STRING]
        self.field.TYPES[Field.STRING] = self.type_convert_func

    def tearDown(self):
        self.field.TYPES[Field.STRING] = self.old_type_func

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
        self.applier = UtilBillApplier.get_instance()
        self.bill = NonCallableMock()
        self.bill.set_total_energy = Mock()
        self.bill.set_next_meter_read_date = Mock()

    def test_default_applier(self):
        d = date(2000,1,1)
        self.applier.apply(UtilBillApplier.START, d, self.bill)
        self.assertEqual(d, self.bill.period_start)

        self.bill.reset_mock()
        self.applier.apply(UtilBillApplier.END, d, self.bill)
        self.assertEqual(d, self.bill.period_end)

        self.bill.reset_mock()
        self.applier.apply(UtilBillApplier.NEXT_READ, d, self.bill)
        self.bill.set_next_meter_read_date.assert_called_once_with(d)

        self.bill.reset_mock()
        self.applier.apply(UtilBillApplier.ENERGY, 123.456, self.bill)
        self.bill.set_total_energy.assert_called_once_with(123.456)

    def test_apply_values(self):
        # one field is good, 2 have ApplicationErrors (one with wrong value
        # type, one with unknown key)
        extractor = Mock(spec=Extractor)
        good = {UtilBillApplier.START: date(2000, 1, 1),
                UtilBillApplier.CHARGES: 'wrong type', 'wrong key': 1}
        extractor_errors = {UtilBillApplier.END: ExtractionError('an error')}
        extractor.get_values.return_value = (good, extractor_errors)
        bfh = Mock(spec=BillFileHandler)
        # validator is tested in ValidatorTest
        Validator.validate_bill = Mock(return_value=UtilBill.SUCCEEDED)

        success_count, applier_errors = self.applier.apply_values(
            extractor, self.bill, bfh)
        self.assertEqual(1, success_count)
        self.assertEqual(3, len(applier_errors))
        self.assertIsInstance(applier_errors['wrong key'], ApplicationError)
        self.assertIsInstance(applier_errors[UtilBillApplier.CHARGES],
                              ApplicationError)

    def test_errors(self):
        # wrong key
        with self.assertRaises(ApplicationError):
            self.applier.apply('wrong key', 1, self.bill)

        # wrong value type
        with self.assertRaises(ApplicationError):
            self.applier.apply(UtilBillApplier.START, 1, self.bill)

        # exception in target method
        self.bill.reset_mock()
        self.bill.set_total_energy.side_effect = Exception
        with self.assertRaises(ApplicationError):
            self.applier.apply(UtilBillApplier.ENERGY, 123.456, self.bill)


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

        self.utilbill = Mock(spec=UtilBill)
        self.bill_file_handler = Mock(spec=BillFileHandler)

        # applying f1 succeeds, applying f3 fails (and f2 never gets applied
        # because its value couldn't be extracted)
        self.applier = Mock(spec=Applier)
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
            self.field.get_value('xyz')

        # matched a string but couldn't convert to a date
        with self.assertRaises(ConversionError):
            self.field.get_value('Somemonth 0, 7689')

        # multiple matches
        with self.assertRaises(MatchError):
            field_multiple_matches = TextExtractor.TextField(regex=r'(\d+) ('
                                                                   r'\d+)',
                type=Field.FLOAT)
            print self.field.get_value('3342 2321')


class TextExtractorTest(TestCase):
    def setUp(self):
        self.text = 'Bill Text 1234.5 More Text  '
        self.bfh = Mock(spec=BillFileHandler)
        self.te = TextExtractor()
        self.bill = Mock(spec=UtilBill)
        self.bill.get_text.return_value = self.text

    def test_prepare_input(self):
        self.assertEqual(self.text, self.te._prepare_input(self.bill, self.bfh))

class VerifyFieldTest(TestCase):
    def setUp(self):
        self.rate_class = Mock(spec=RateClass)
        self.rate_class.name = "Some Rate Class"

    def test_verify_field(self):
        self.assertTrue(verify_field(UtilBillApplier.START, date(2015, 07, 04),
            date(2015, 07, 04)))
        self.assertTrue(verify_field(UtilBillApplier.START, date(2015, 07, 04),
            '2015-07-04'))
        # whitespace in DB is ok
        self.assertTrue(verify_field(UtilBillApplier.START, '2015-07-04',
            '2015-07-04 '))
        # whitespace in extracted value is not ok
        self.assertFalse(verify_field(UtilBillApplier.START, '2015-07-04 ',
            '2015-07-04'))
        self.assertFalse(verify_field(UtilBillApplier.START, '2014-07-04',
            '2015-07-04'))
        self.assertTrue(verify_field(UtilBillApplier.RATE_CLASS, "Some Rate Class",
            self.rate_class))
        # allowances for capitalization, formatting of spaces
        self.assertTrue(verify_field(UtilBillApplier.RATE_CLASS, "Some_rate-class",
            self.rate_class))
        self.assertFalse(verify_field(UtilBillApplier.RATE_CLASS, "Different rate "
                                                          "class",
            self.rate_class))

class LayoutExtractorTest(TestCase):
    def setUp(self):
        self.le1 = LayoutElement(text='hello', page_num=0,
            bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=200), type=TEXTLINE)
        self.le2 = LayoutElement(text='text', page_num=2,
            bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=200), type=TEXTLINE)
        self.le3 = LayoutElement(text='wot', page_num=0,
            bounding_box=BoundingBox(x0=0, y0=200, x1=100, y1=200),
            type=TEXTLINE)
        self.le4 = LayoutElement(text='sample', page_num=1,
            bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=200), type=TEXTLINE)
        self.layout_elts = [[self.le3, self.le1], [self.le4], [self.le2]]

        self.bfh = Mock(spec=BillFileHandler)
        self.le = LayoutExtractor()
        self.le_with_align = LayoutExtractor(origin_regex='wot', origin_x=10,
            origin_y=10)
        self.bill = Mock(spec=UtilBill)
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
        self.le1 = LayoutElement(text='hello', page_num=0,
            bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=200), type=TEXTLINE)
        self.le2 = LayoutElement(text='text', page_num=2,
            bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=200), type=TEXTLINE)
        self.le3 = LayoutElement(text='wot', page_num=0,
            bounding_box=BoundingBox(x0=0, y0=200, x1=100, y1=200),
            type=TEXTLINE)
        self.le4 = LayoutElement(text='sample', page_num=1,
            bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=200), type=TEXTLINE)
        self.le5 = LayoutElement(text='', page_num=1,
            bounding_box=BoundingBox(x0=50, y0=50, x1=70, y1=70), type=TEXTLINE)
        self.le6 = LayoutElement(text='woo', page_num=2,
            bounding_box=BoundingBox(x0=50, y0=50, x1=70, y1=70), type=TEXTLINE)
        self.layout_elts = [[self.le1, self.le3], [self.le4, self.le5],
                            [self.le2, self.le6]]
        self.bfh = Mock(spec=BillFileHandler)
        self.bill = Mock(spec=UtilBill)

        #add a mis-alignment for testing
        self.input = (self.layout_elts, 5, 5)

    def test_not_enough_pages(self):
        bb_field = LayoutExtractor.BoundingBoxField(page_num=44)
        with self.assertRaises(ExtractionError):
            bb_field.get_value(self.input)

    def test_get_bounding_box(self):
        bb_field = LayoutExtractor.BoundingBoxField(bounding_box=BoundingBox(
            x0=0-5, y0=0-5, x1=100-5, y1=200-5), page_num=2,
            bbregex='([a-z]ampl[a-z])', corner=0)
        self.assertEqual('sample', bb_field.get_value(self.input))

    def test_bbox_alignment_error(self):
        # in this test, forget to align by 5 pixels
        bb_field = LayoutExtractor.BoundingBoxField(bounding_box=BoundingBox(
            x0=0, y0=0, x1=100, y1=200), page_num=2, bbregex='([a-z]ampl['
                                                             'a-z])', corner=0)
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
            offset_regex=r'text', corner=0, bounding_box=BoundingBox(x0=50,
                y0=50, x1=60, y1=60))
        self.assertEqual('woo', bb_offset.get_value(self.input))

    def test_match_empty_text(self):
        """ Test match for an empty string, e.g. in the case of an empty
        layout element or a regex returning an empty string
        """
        bb_field_fail = LayoutExtractor.BoundingBoxField(
            bounding_box=BoundingBox(x0=50-5, y0=50-5, x1=60-5, y1=60-5),
            page_num=2, corner=0)
        with self.assertRaises(ExtractionError):
            bb_field_fail.get_value(self.input)


class TableFieldTest(TestCase):
    """
    Tests for layout extractor of bounding box fields
    """
    def setUp(self):
        # generate of table of elements
        # The table is copied on two pages.
        self.layout_elements_pg1 = []
        self.layout_elements_pg2 = []
        for y in range(100, 10, -10):
            for x in range(20, 50, 10):
                elt1 = LayoutElement(bounding_box=BoundingBox(x0=x, y0=y,
                    x1=x+5, y1=y + 5), text="%d %d text" % (x, y),
                    type=TEXTLINE, page_num=1)
                elt2 = LayoutElement(bounding_box=BoundingBox(x0=x, y0=y,
                    x1=x+5, y1=y + 5), text="%d %d text" % (x, y),
                    type=TEXTLINE, page_num=1)
                self.layout_elements_pg1.append(elt1)
                self.layout_elements_pg2.append(elt2)
        self.layout_elements_pg1.append(LayoutElement(bounding_box=BoundingBox(
            x0=0, y0=0, x1=5, y1=5), text="not in table", type=TEXTLINE,
            page_num=1))
        self.layout_elements_pg2.append(LayoutElement(bounding_box=BoundingBox(
            x0=0, y0=0, x1=5, y1=5), text="not in table", type=TEXTLINE,
            page_num=2))

        # Create processed input data
        # Table is copied onto two pages.
        self.input = ([self.layout_elements_pg1, self.layout_elements_pg2],
        0, 0)

    def test_get_table_boundingbox(self):
        """ Test getting tabular data wihtin a bounding box
        """
        tablefield = LayoutExtractor.TableField(page_num=1,
            bounding_box=BoundingBox(x0=30, y0=30, x1=45, y1=45))
        expected_output = [["30 40 text", "40 40 text"],
                            ["30 30 text", "40 30 text"]]
        self.assertEqual(expected_output, tablefield._extract(self.input))

    def test_start_stop_regex(self):
        regex_tablefield = LayoutExtractor.TableField(page_num=1,
            bounding_box=BoundingBox(x0=30, y0=20, x1=45, y1=55),
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
            bounding_box=BoundingBox(x0=30, y0=30, x1=45, y1=45), multipage_table=True,
            nextpage_top=35, maxpage=2)
        # 1st and 2nd rows come from 1st page, 3rd row from 2nd page
        expected_output = [["30 40 text", "40 40 text"],
                            ["30 30 text", "40 30 text"],
                            ["30 30 text", "40 30 text"]]
        actual_output = multipage_tablefield._extract(self.input)
        self.assertEqual(expected_output, actual_output)

    def test_no_values_found(self):
        tablefield= LayoutExtractor.TableField(page_num=1,
            bounding_box=BoundingBox(x0=30, y0=30, x1=45, y1=45))
        with self.assertRaises(ExtractionError):
            # give tablefield data representing a single empty page.
            tablefield._extract(([[]], 0, 0))

class TestTypeConversion(TestCase):
    """ Test type conversion functions
    """
    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()
        # FakeS3Manager.start()

    @classmethod
    def tearDownClass(cls):
        # FakeS3Manager.stop()
        pass

    def tearDown(self):
        clear_db()

    def setUp(self):
        clear_db()

    def test_convert_unit(self):
        # for units already in CHARGE_UNITS, just return them
        for cu in Charge.CHARGE_UNITS:
            self.assertEqual(convert_unit(cu), cu)
        # when there is no unit, assume dollars
        self.assertEqual(convert_unit(''), 'dollars')
        self.assertEqual(convert_unit('th'), 'therms')
        self.assertEqual(convert_unit('$'), 'dollars')
        with self.assertRaises(ConversionError):
            convert_unit('lol not a unit')

    def test_process_charge(self):
        # simple test with name & value
        sample_charge_row = ['Bagels', '$1,500.40']
        sample_charge = process_charge(sample_charge_row)
        self.assertEqual(sample_charge.description, 'Bagels')
        self.assertEqual(sample_charge.target_total, 1500.40)

        # full charge test, with more fields and a name that matches an
        # existing charge in the database with an rsi binding
        charge_row = ['Energy charges 251.2 kWh x $0.0034', "$0.85408"]
        charge = process_charge(charge_row, Charge.SUPPLY)
        self.assertEqual(charge.description, 'Energy charges')
        self.assertEqual(charge.unit, 'dollars')
        self.assertEqual(charge.rate, 0.0034)
        self.assertEqual(charge.type, Charge.SUPPLY)
        self.assertEqual(charge.target_total, 0.85408)

    def test_convert_table_charges(self):
        """ Tests the conversion function that takes tabular data and outputs a
        list of charges. Uses a list of known charges and inputs.
        """
        table_charges_rows = [
            [u'DISTRIBUTION SERVICE'],
            [u'Distribution Charge   206.0  TH x .3158', u'$ 65.05'],
            [u'Customer Charge', u'$ 33.00'],
            [u'NATURAL GAS SUPPLY SERVICE'],
            [u'PGC 206.0 TH x .5542', u'$ 114.17'],
            [u'TAXES'],
            [u'DC Rights-of-Way Fee', u'$ 5.77'],
            [u'Sustainable Energy Trust Fund 206.0 TH x .01400', u'$ 2.88'],
            [u'Energy Assistance Trust Fund 206.0 TH x .006000', u'$ 1.24'],
            [u'Delivery Tax 206.0 TH x .070700', u'$ 14.56'],
            [u'Total Current Washington Gas Charges', u'$ 236.67']]

        expected_charges = [
            Charge(None, description='Distribution Charge', unit='dollars',
                rate=0.3158, type=Charge.DISTRIBUTION, target_total=65.05),
            Charge(None, description='Customer Charge', unit='dollars',
                type=Charge.DISTRIBUTION, target_total=33.00),
            Charge(None, description='PGC', unit='dollars',
                rate=0.5542, type=Charge.SUPPLY, target_total=114.17),
            Charge(None, description='DC Rights-of-Way Fee',
                unit='dollars',
                type=Charge.DISTRIBUTION, target_total=5.77),
            Charge(None, description='Sustainable Energy Trust Fund',
            unit='dollars',
                rate=0.014, type=Charge.DISTRIBUTION, target_total=2.88),
            Charge(None, description='Energy Assistance Trust Fund',
                unit='dollars',
                rate=0.006, type=Charge.DISTRIBUTION, target_total=1.24),
            Charge(None, description='Delivery Tax', unit='dollars',
                rate=0.0707, type=Charge.DISTRIBUTION, target_total=14.56),
            Charge(None, description='Total Current Washington Gas Charges',
                unit='dollars', type=Charge.DISTRIBUTION, target_total=236.67)
        ]

        output_charges = convert_table_charges(table_charges_rows)
        self.assertListEqual(expected_charges, output_charges)


    def test_convert_address(self):
        """ Tests the address conversion function. Takes into account
        formatting issues, such as switching street and city/state lines. 
        """

        # simple address test, with C/O line
        lines = "\n".join(("John Smith", "C/O Smith Johnson", "",
        "1234 Everton Road", "Baltimore, MD 12345"))
        address = convert_address(lines)
        self.assertEqual(address.addressee, "John Smith C/O Smith Johnson")
        self.assertEqual(address.street, "1234 Everton Road")
        self.assertEqual(address.city, "Baltimore")
        self.assertEqual(address.state, "MD")
        self.assertEqual(address.postal_code, "12345")

        # street and city/state out of order, with ATTN line and 9-digit
        # postal code
        lines = "\n".join(("ATTN: Michael Chapin",
                            "15 35th Street", "Seattle, WA 54321-9494"))
        address = convert_address(lines)
        self.assertEqual(address.addressee, "Michael Chapin")
        self.assertEqual(address.street, "15 35th Street")
        self.assertEqual(address.city, "Seattle")
        self.assertEqual(address.state, "WA")
        self.assertEqual(address.postal_code, "54321-9494")

        # address with no adressee
        lines = "\n".join(("2010 KALORAMA RD NW", "WASHINGTON DC 20009"))
        address = convert_address(lines)
        self.assertIsNone(address.addressee)
        self.assertEqual(address.street, "2010 KALORAMA RD NW")
        self.assertEqual(address.city, "WASHINGTON")
        self.assertEqual(address.state, "DC")
        self.assertEqual(address.postal_code, "20009")


    def test_convert_wg_charges_std(self):
        pass


class ValidatorTest(TestCase):
    """ Test bill validation. (i.e making sure extracted data has reasonable
    values)
    """
    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()

    @classmethod
    def tearDownClass(cls):
        pass

    def tearDown(self):
        clear_db()

    def setUp(self):
        clear_db()
        self.utilbill = Mock(spec=UtilBill)
        self.utilbill.utility_account_id = 1
        self.utilbill.period_start=date(2014, 1, 1)
        self.utilbill.period_end=date(2014, 1, 31)
        self.utilbill.next_meter_read_date=date(2014, 2, 28)

        self.utilbill_no_dates = Mock(spec=UtilBill)
        self.utilbill_no_dates.utility_account_id = 1
        self.utilbill_no_dates.period_start=None
        self.utilbill_no_dates.period_end=None
        self.utilbill_no_dates.next_meter_read_date=None

        self.bill2 = Mock(spec=UtilBill)
        self.bill2.utility_account_id=1
        self.bill2.period_start=date(2014, 2, 1)
        self.bill2.period_end=date(2014, 2, 28)
        self.bill2.next_meter_read_date=date(2014, 3, 31)
        self.bill2.validation_state=UtilBill.SUCCEEDED
        self.bill2.billing_address=Address(addressee="Bob Billingsworth",
            street="1234 Nextility St", city="Baltimore", state="MD")
        self.bill2.service_address=Address(addressee=None,
            street="15 35th St", city="Baltimore", state="MD")

        self.bill3 = Mock(spec=UtilBill)
        self.bill3.utility_account_id=1
        self.bill3.period_start=date(2014, 3, 1)
        self.bill3.period_end=date(2014, 3, 31)
        self.bill3.next_meter_read_date=date(2014, 4, 30)
        self.bill3.validation_state=UtilBill.SUCCEEDED

        self.bill4 = Mock(spec=UtilBill)
        self.bill4.utility_account_id=1
        self.bill4.period_start=date(2014, 4, 1)
        self.bill4.period_end=date(2014, 4, 30)
        self.bill4.next_meter_read_date=date(2014, 5, 31)
        self.bill4.validation_state=UtilBill.SUCCEEDED
        self.other_bills = [self.bill2, self.bill3, self.bill4]


    def test_worst_validation_state(self):
        with self.assertRaises(ValueError):
            Validator.worst_validation_state([])

        self.assertEqual(UtilBill.SUCCEEDED,
            Validator.worst_validation_state([UtilBill.SUCCEEDED,
                UtilBill.SUCCEEDED]))

        self.assertEqual(UtilBill.REVIEW, Validator.worst_validation_state([
            UtilBill.SUCCEEDED, UtilBill.REVIEW, UtilBill.SUCCEEDED]))

        self.assertEqual(UtilBill.FAILED, Validator.worst_validation_state([
            UtilBill.SUCCEEDED, UtilBill.REVIEW,
            UtilBill.FAILED, UtilBill.SUCCEEDED]))

    def test_set_bill_state_if_unprocessed(self):
        # by default, only updates bill if new state is worst
        self.utilbill.validation_state=UtilBill.FAILED
        Validator._set_bill_state_if_unprocessed(self.utilbill, UtilBill.REVIEW)
        self.assertEqual(UtilBill.FAILED, self.utilbill.validation_state)

        self.utilbill.validation_state=UtilBill.FAILED
        Validator._set_bill_state_if_unprocessed(self.utilbill,
            UtilBill.REVIEW, checkworst=False)
        self.assertEqual(UtilBill.REVIEW, self.utilbill.validation_state)

        # if a bill is processed, its validation state should not be modified.
        processed_bill = Mock(spec=BEUtilBill)
        processed_bill.billentry_date = date.today()
        processed_bill.validation_state = UtilBill.FAILED
        Validator._set_bill_state_if_unprocessed(processed_bill,
            UtilBill.REVIEW, checkworst=False)
        self.assertNotEqual(UtilBill.REVIEW, processed_bill.validation_state)

    def test_date_utils(self):
        # simple test of _check_date_bounds
        self.assertTrue(Validator._check_date_bounds(date(2014, 6, 7),
            date(2014, 1, 1), date(2014, 12, 30)))
        # bounds are inclusive
        self.assertTrue(Validator._check_date_bounds(date(2014, 6, 7),
            date(2014, 6, 7), date(2014, 12, 30)))
        self.assertTrue(Validator._check_date_bounds(date(2014, 6, 7),
            date(2014, 1, 1), date(2014, 6, 7)))
        # false results:
        self.assertFalse(Validator._check_date_bounds(date(2014, 6, 7),
            date(2014, 8, 1), date(2014, 12, 30)))
        self.assertFalse(Validator._check_date_bounds(date(2014, 6, 7),
            date(2014, 1, 1), date(2014, 2, 7)))

        # testing _overlaps_bill_period
        self.assertTrue(Validator._overlaps_bill_period(self.utilbill,
            date(2014, 1, 15)))
        # start is inclusive
        self.assertTrue(Validator._overlaps_bill_period(self.utilbill,
            date(2014, 1, 1)))
        # end is exclusive
        self.assertFalse(Validator._overlaps_bill_period(self.utilbill,
            date(2014, 1, 31)))
        # false results:
        self.assertFalse(Validator._overlaps_bill_period(self.utilbill,
            date(2012, 2, 23)))
        self.assertFalse(Validator._overlaps_bill_period(self.utilbill,
            date(2014, 2, 23)))
        # return false if bill period dates are None
        self.assertFalse(Validator._overlaps_bill_period(
            self.utilbill_no_dates, date(2014, 1, 15)))

    def test_validate_start(self):
        simple_validation = Validator.validate_start(self.utilbill,
            self.other_bills, date(2014, 1, 1))
        self.assertEqual(UtilBill.SUCCEEDED, simple_validation)

        # a start date from the distant past
        baroque_error = Validator.validate_start(self.utilbill,
            self.other_bills, date(1675, 1, 23))
        self.assertEqual(UtilBill.FAILED, baroque_error)

        # a start date from the future
        future_error = Validator.validate_start(self.utilbill,
            self.other_bills, date.today() + relativedelta(days=100))
        self.assertEqual(UtilBill.FAILED, future_error)

        # start date is out of range, relative to bill's end date
        short_period_error = Validator.validate_start(self.utilbill,
            [], date(2014, 1, 21))
        self.assertEqual(UtilBill.FAILED, short_period_error)
        long_period_error = Validator.validate_start(self.utilbill,
            [], date(2013, 12, 1))
        self.assertEqual(UtilBill.FAILED, long_period_error)

        # start date that overlaps with another bill's period
        bill_overlap_error = Validator.validate_start(self.utilbill_no_dates,
            self.other_bills, date(2014, 2, 15))
        self.assertEqual(UtilBill.FAILED, bill_overlap_error)
        self.assertEqual(UtilBill.FAILED, self.bill2.validation_state)
        self.bill2.validation_state = UtilBill.SUCCEEDED

        # start date that doesn't overlap with other bills, but is unusually
        # close to other start dates.
        bill_short_gap_error = Validator.validate_start(self.utilbill_no_dates,
            self.other_bills, date(2014, 1, 28))
        self.assertEqual(UtilBill.FAILED, bill_short_gap_error)
        self.assertEqual(UtilBill.FAILED, self.bill2.validation_state)
        self.bill2.validation_state = UtilBill.SUCCEEDED

    def test_validate_end(self):
        simple_validation = Validator.validate_end(self.utilbill,
            self.other_bills, date(2014, 1, 31))
        self.assertEqual(UtilBill.SUCCEEDED, simple_validation)

        # an end date from the distant past
        baroque_error = Validator.validate_end(self.utilbill,
            self.other_bills, date(1675, 1, 23))
        self.assertEqual(UtilBill.FAILED, baroque_error)

        # an end date from the future
        future_error = Validator.validate_end(self.utilbill,
            self.other_bills, date.today() + relativedelta(days=100))
        self.assertEqual(UtilBill.FAILED, future_error)

        # end date is out of range, relative to bill's start date
        short_period_error = Validator.validate_end(self.utilbill,
            [], date(2014, 1, 5))
        self.assertEqual(UtilBill.FAILED, short_period_error)
        long_period_error = Validator.validate_end(self.utilbill,
            [], date(2014, 2, 21))
        self.assertEqual(UtilBill.FAILED, long_period_error)

        # end date that overlaps with another bill's period
        bill_overlap_error = Validator.validate_end(self.utilbill_no_dates,
            self.other_bills, date(2014, 2, 15))
        self.assertEqual(UtilBill.FAILED, bill_overlap_error)
        self.assertEqual(UtilBill.FAILED, self.bill2.validation_state)
        self.bill2.validation_state = UtilBill.SUCCEEDED

        # end date that doesn't overlap with other bills, but is unusually
        # close to other end dates.
        bill_short_gap_error = Validator.validate_end(self.utilbill_no_dates,
            self.other_bills, date(2014, 5, 5))
        self.assertEqual(UtilBill.FAILED, bill_short_gap_error)
        self.assertEqual(UtilBill.FAILED, self.bill4.validation_state)
        self.bill4.validation_state = UtilBill.SUCCEEDED

    def test_validate_next_read(self):
        simple_validation = Validator.validate_next_read(self.utilbill,
            self.other_bills, date(2014, 2, 28))
        self.assertEqual(UtilBill.SUCCEEDED, simple_validation)

        # a next read date from the distant past
        baroque_error = Validator.validate_next_read(self.utilbill,
            self.other_bills, date(1675, 1, 23))
        self.assertEqual(UtilBill.FAILED, baroque_error)

        # a next read date from the future
        future_error = Validator.validate_next_read(self.utilbill,
            self.other_bills, date.today() + relativedelta(days=100))
        self.assertEqual(UtilBill.FAILED, future_error)

        # next read date is out of range, relative to bill's end date
        short_period_error = Validator.validate_next_read(self.utilbill,
            [], date(2014, 2, 5))
        self.assertEqual(UtilBill.FAILED, short_period_error)
        long_period_error = Validator.validate_next_read(self.utilbill,
            [], date(2014, 3, 31))
        self.assertEqual(UtilBill.FAILED, long_period_error)

        # next read date  is unusually close to other next read dates.
        bill_short_gap_error = Validator.validate_next_read(self.utilbill_no_dates,
            self.other_bills, date(2014, 4, 27))
        self.assertEqual(UtilBill.REVIEW, bill_short_gap_error)
        self.assertEqual(UtilBill.REVIEW, self.bill3.validation_state)
        self.bill3.validation_state = UtilBill.SUCCEEDED

    def test_validate_billing_address(self):
        # this address matches bill2's address
        correct_address = Address(addressee="Bob Billingsworth",
            street="1234 Nextility St", city="Baltimore", state="MD")
        validation_result = Validator.validate_billing_address(self.utilbill,
            self.other_bills, correct_address)
        self.assertEqual(UtilBill.SUCCEEDED, validation_result)

        # a valid address, but not found elsewhere in the account
        wrong_address = Address(addressee="Not Bob",
            street="5678 Skyline Dr", city="Ithaca", state="NY")
        validation_error = Validator.validate_billing_address(self.utilbill,
            self.other_bills, wrong_address)
        self.assertEqual(UtilBill.REVIEW, validation_error)

        # TODO add address validation so we can test against an invalid address

    def test_validate_service_address(self):
        # this address matches bill2's service address
        correct_address = Address(addressee=None, street="15 35th St",
            city="Baltimore", state="MD")
        validation_result = Validator.validate_service_address(self.utilbill,
            self.other_bills, correct_address)
        self.assertEqual(UtilBill.SUCCEEDED, validation_result)

        # a valid address, but not found elsewhere in the account
        wrong_address = Address(addressee=None,
            street="5 35th St", city="Baltimore", state="MA")
        validation_error = Validator.validate_service_address(self.utilbill,
            self.other_bills, wrong_address)
        self.assertEqual(UtilBill.REVIEW, validation_error)

        # TODO add address validation so we can test against an invalid address

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
        e1.fields = [
            TextExtractor.TextField(regex=wg_start_regex, type=Field.DATE,
                                    applier_key=UtilBillApplier.START),
            TextExtractor.TextField(regex=wg_end_regex, type=Field.DATE,
                                    applier_key=UtilBillApplier.END),
            TextExtractor.TextField(regex=wg_energy_regex, type=Field.FLOAT,
                                    applier_key=UtilBillApplier.ENERGY),
            TextExtractor.TextField(regex=wg_next_meter_read_regex,
                                    type=Field.DATE,
                                    applier_key=UtilBillApplier.NEXT_READ),
            TextExtractor.TextField(regex=wg_charges_regex,
                                    type=Field.WG_CHARGES,
                                    applier_key=UtilBillApplier.CHARGES),
            TextExtractor.TextField(regex=wg_rate_class_regex,
                                    type=Field.STRING,
                                    applier_key=UtilBillApplier.RATE_CLASS),
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
        # Charges are temporarily disabled, until a better way to disable
        # specific fields is put into release 30

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
        
        self.assertEqual(len(expected), len(self.bill.charges))
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

        s = Session()
        s.commit()

        # set bill as processed so that the extractor results can be verified
        #  in test_bill
        self.bill.processed = True

        # get results from test
        results = [test_bill(self.e1.extractor_id, self.bill.id),
            TaskRevokedError("Representing a stopped task"),
            Exception("Representing a failed task"), None]
        total_result = reduce_bill_results(results)

        # set up expected results from test
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
                            'verified_count': 1,
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