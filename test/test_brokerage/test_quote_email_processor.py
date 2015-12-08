from cStringIO import StringIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import Message, email
import os
from email.mime.base import MIMEBase
from unittest import TestCase

from mock import Mock, MagicMock
import statsd

from brokerage.brokerage_model import Company, Quote, MatrixQuote, MatrixFormat
from brokerage.quote_email_processor import QuoteEmailProcessor, EmailError, \
    UnknownSupplierError, QuoteDAO, MultipleErrors, NoFilesError, NoQuotesError, \
    UnknownFormatError
from brokerage.quote_parsers import CLASSES_FOR_FORMATS
from brokerage.quote_parser import QuoteParser
from core import init_altitude_db, init_model, ROOT_PATH
from core.model import Supplier, Session, AltitudeSession
from core.exceptions import ValidationError
from test import init_test_config, clear_db, create_tables

EMAIL_FILE_PATH = os.path.join(ROOT_PATH, 'test', 'test_brokerage',
                               'quote_files', 'quote_email.txt')

def setUpModule():
    init_test_config()

class TestQuoteEmailProcessor(TestCase):
    """Unit tests for QuoteEmailProcessor.
    """
    def setUp(self):
        self.supplier = Supplier(id=1, name='The Supplier')
        self.format_1 = MatrixFormat(matrix_format_id=1)
        self.quote_dao = Mock(autospec=QuoteDAO)
        self.quote_dao.get_supplier_objects_for_message.return_value = (
            self.supplier, Company(company_id=2, name='The Supplier'))
        self.quote_dao.get_matrix_format_for_file.return_value = self.format_1

        self.quotes = [Mock(autospec=Quote), Mock(autospec=Quote)]
        self.quote_parser = Mock(autospec = QuoteParser)
        # QuoteEmailProcessor expects QuoteParser.extract_quotes to return a
        # generator, not a list
        self.quote_parser.extract_quotes.return_value = (q for q in self.quotes)
        self.quote_parser.get_count.return_value = len(self.quotes)
        QuoteParserClass1 = Mock()
        QuoteParserClass1.return_value = self.quote_parser

        # a second QuoteParser for testing handing of multiple file formats
        # in the same email
        QuoteParserClass2 = Mock()
        self.quote_parser_2 = Mock(autospec=QuoteParser)
        QuoteParserClass2.return_value = self.quote_parser_2
        self.quote_parser_2.extract_quotes.return_value = (
            q for q in self.quotes)
        self.quote_parser_2.get_count.return_value = len(self.quotes)
        self.format_2 = MatrixFormat(matrix_format_id=2)
        self.supplier.matrix_formats = [self.format_1, self.format_2]

        # might as well use real objects for StatsD metrics; they don't need
        # to connect to a server
        self.email_counter = statsd.Counter('email')
        self.quote_counter = statsd.Counter('quote')

        self.qep = QuoteEmailProcessor(
            {1: QuoteParserClass1, 2: QuoteParserClass2}, self.quote_dao)

        self.message = Message()
        self.sender, self.recipient, self.subject = (
            'Sender', 'Recipient', 'Subject')
        self.message['From'] = self.sender
        self.message['To'] = 'Original Recipient'
        self.message['Delivered-To'] = self.recipient
        self.message['Subject'] = self.subject

    def test_process_email_malformed(self):
        with self.assertRaises(EmailError):
            self.qep.process_email(StringIO('wtf'))

        self.assertEqual(
            0, self.quote_dao.get_supplier_objects_for_message.call_count)
        #self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.begin.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(0, self.quote_parser.load_file.call_count)
        self.assertEqual(0, self.quote_parser.extract_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_no_supplier(self):
        self.quote_dao.get_supplier_objects_for_message.side_effect = \
            UnknownSupplierError

        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(StringIO(self.message.as_string()))

        self.quote_dao.get_supplier_objects_for_message.assert_called_once_with(
            self.recipient)
        #self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.begin.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_no_attachment(self):
        # email has no attachment in it
        with self.assertRaises(NoFilesError):
            self.qep.process_email(StringIO(self.message.as_string()))

        # supplier objects are looked up and found, but there is nothing else
        # to do
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        #self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.begin.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(0, self.quote_parser.load_file.call_count)
        self.assertEqual(0, self.quote_parser.extract_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_non_matching_attachment(self):
        self.quote_dao.get_matrix_format_for_file.side_effect = \
            UnknownFormatError
        email_file = StringIO(self.message.as_string())
        with self.assertRaises(NoFilesError):
            self.qep.process_email(email_file)

        # supplier objects are looked up and found, but nothing else happens
        # because the file is ignored
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        #self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.begin.call_count)
        self.assertEqual(0, self.quote_parser.load_file.call_count)
        self.assertEqual(0, self.quote_parser.extract_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_invalid_attachment(self):
        self.message.add_header('Content-Disposition', 'attachment',
                                filename='filename.xls')
        email_file = StringIO(self.message.as_string())
        self.quote_parser.extract_quotes.side_effect = ValidationError

        with self.assertRaises(MultipleErrors):
            self.qep.process_email(email_file)

        # quote parser doesn't like the file format, so no quotes are extracted
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        #self.assertEqual(1, self.quote_dao.begin_nested.call_count)
        self.assertEqual(1, self.quote_dao.begin.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(1, self.quote_parser.load_file.call_count)
        self.quote_parser.extract_quotes.assert_called_once_with()
        self.quote_dao.rollback.assert_called_once_with()
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_good_attachment(self):
        self.format_1.matrix_attachment_name = 'filename.xls'
        self.message.add_header('Content-Disposition', 'attachment',
                                filename='fileNAME.XLS')
        email_file = StringIO(self.message.as_string())

        self.qep.process_email(email_file)

        # normal situation: quotes are extracted from the file and committed
        # in a nested transaction
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        #self.assertEqual(1, self.quote_dao.begin_nested.call_count)
        self.assertEqual(1, self.quote_dao.begin.call_count)
        self.assertEqual(len(self.quotes),
                         self.quote_dao.insert_quotes.call_count)
        self.assertEqual(1, self.quote_parser.load_file.call_count)
        self.quote_parser.extract_quotes.assert_called_once_with()
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(1, self.quote_dao.commit.call_count)

    def test_process_email_no_quotes(self):
        self.message.add_header('Content-Disposition', 'attachment',
                                filename='filename.xls')
        email_file = StringIO(self.message.as_string())

        self.quote_parser.extract_quotes.return_value = []
        self.quote_parser.get_count.return_value = 0

        with self.assertRaises(NoQuotesError):
            self.qep.process_email(email_file)

        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        #self.assertEqual(1, self.quote_dao.begin_nested.call_count)
        self.assertEqual(1, self.quote_dao.begin.call_count)
        self.assertEqual(1, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(1, self.quote_parser.load_file.call_count)
        self.quote_parser.extract_quotes.assert_called_once_with()
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(1, self.quote_dao.commit.call_count)

    def test_multiple_formats(self):
        """One email with 2 attachments, each of which should be read by a
        different QuoteParser class depending on the file name.
        """
        self.quote_dao.get_matrix_format_for_file.side_effect = [
            self.format_1, self.format_2]

        # can't figure out how to create a well-formed email with 2 attachments
        # using the Python "email" module, so here's one from a file
        with open('test/test_brokerage/quote_files/quote_email.txt') as f:
            self.qep.process_email(f)

        # the 2 files are processed by 2 separate QuoteParsers
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        self.assertEqual(
            2, self.quote_dao.get_matrix_format_for_file.call_count)
        #self.assertEqual(2, self.quote_dao.begin_nested.call_count)
        self.assertEqual(2, self.quote_dao.begin.call_count)
        self.assertEqual(2 * len(self.quotes),
                         self.quote_dao.insert_quotes.call_count)
        self.assertEqual(1, self.quote_parser.load_file.call_count)
        self.quote_parser.extract_quotes.assert_called_once_with()
        self.quote_parser_2.extract_quotes.assert_called_once_with()
        self.assertEqual(1, self.quote_parser_2.load_file.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(2, self.quote_dao.commit.call_count)

class TestQuoteDAO(TestCase):
    @classmethod
    def setUpClass(self):
        create_tables()
        init_model()
        clear_db()

    def setUp(self):
        self.dao = QuoteDAO()
        self.format1 = MatrixFormat()
        self.format2 = MatrixFormat()
        self.supplier = Supplier(name='Supplier',
                                 matrix_formats=[self.format1, self.format2])
        Session().add(self.supplier)

    def tearDown(self):
        clear_db()

    def test_get_matrix_format_for_file(self):
        # multiple matches with blank file name pattern
        with self.assertRaises(UnknownFormatError):
            self.dao.get_matrix_format_for_file(self.supplier, 'a')

        # multiple matches: note that both "a" and None match "a"
        self.format1.matrix_attachment_name = 'a'
        with self.assertRaises(UnknownFormatError):
            self.dao.get_matrix_format_for_file(self.supplier, 'a')

        # exactly one match
        self.format2.matrix_attachment_name = 'b'
        self.assertEqual(self.format1, self.dao.get_matrix_format_for_file(
            self.supplier, 'a'))

        # no matches
        with self.assertRaises(UnknownFormatError):
            self.dao.get_matrix_format_for_file(self.supplier, 'c')

        # multiple matches with non-blank file name patterns
        self.format2.matrix_attachment_name = 'a'
        with self.assertRaises(UnknownFormatError):
            self.dao.get_matrix_format_for_file(self.supplier, 'a')


class TestQuoteEmailProcessorWithDB(TestCase):
    """Integration test using a real email with QuoteEmailProcessor,
    QuoteDAO, and QuoteParser, including the database.
    """
    @classmethod
    def setUpClass(self):
        create_tables()
        init_model()
        init_altitude_db()
        clear_db()

    def setUp(self):
        # example email containing a USGE matrix spreadsheet, matches the
        # Supplier object below. this has 2 quote file attachments but only 1
        #  has a corresponding QuoteParser class.
        self.email_file = open(EMAIL_FILE_PATH)
        self.quote_dao = QuoteDAO()
        email_counter, quote_counter = MagicMock(), MagicMock()
        self.qep = QuoteEmailProcessor(CLASSES_FOR_FORMATS, self.quote_dao)

        # add a supplier to match the example email
        clear_db()
        self.supplier = Supplier(
            id=199, name='USGE',
            matrix_email_recipient='recipient1@nextility.example.com',
            matrix_formats=[
            # TODO: update this id when MatrixFormats are put in the database
                MatrixFormat(matrix_format_id=199,
                             matrix_attachment_name='2. USGE Gas.xlsx')])
        self.altitude_supplier = Company(name=self.supplier.name)

        # extra supplier that will never match any email, to make sure the
        # right one is chosen
        Session().add(Supplier(name='Wrong Supplier',
                               matrix_email_recipient='wrong@example.com'))

    def tearDown(self):
        self.email_file.close()
        clear_db()

    def test_process_email(self):
        Session().add(self.supplier)
        a = AltitudeSession()
        a.add(self.altitude_supplier)
        self.assertEqual(0, a.query(Quote).count())

        self.qep.process_email(self.email_file)
        self.assertEqual(2144, a.query(Quote).count())

        # TODO: tests block forever without this here. it doesn't even work
        # when this is moved to tearDown because AltitudeSession (unlike
        # Session) returns a different object each time it is called. i
        # haven't figured out why that is yet.
        a.rollback()

    def test_process_email_no_supplier_match(self):
        # supplier is missing but altitude_supplier is present
        AltitudeSession().add(self.altitude_supplier)
        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(self.email_file)

        # both are present but supplier doesn't match the email's recipient
        # address
        self.email_file.seek(0)
        Session().add(self.supplier)
        self.supplier.matrix_email_recipient = 'nobody@example.com'
        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(self.email_file)

    def test_process_email_no_altitude_supplier(self):
        # TODO: this should not be necessary here--clear_db() should take
        # care of it. but without these lines, the test fails except when run
        #  by itself (presumably because of data left over from previous tests)
        a = AltitudeSession()
        a.query(MatrixQuote).delete()
        a.query(Company).delete()

        Session().add(self.supplier)
        self.qep.process_email(self.email_file)
        self.assertEqual(2144, a.query(Quote).count())
