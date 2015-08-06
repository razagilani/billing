from cStringIO import StringIO
from email.message import Message
from unittest import TestCase
from mock import Mock, call
from brokerage.brokerage_model import Company, Quote
from brokerage.quote_email_processor import QuoteEmailProcessor, EmailError, \
    UnknownSupplierError, QuoteDAO, CLASSES_FOR_SUPPLIERS
from brokerage.quote_parsers import QuoteParser
from core import init_altitude_db, init_model
from core.model import Supplier, Session, AltitudeSession
from exc import ValidationError
from test import init_test_config, clear_db, create_tables

EMAIL_FILE_PATH = 'quote_email.txt'

def setUpModule():
    init_test_config()
    create_tables()
    init_model()
    init_altitude_db()

class TestQuoteEmailProcessor(TestCase):
    """Unit tests for QuoteEmailProcessor.
    """
    def setUp(self):
        self.supplier = Supplier(id=1, name='The Supplier')
        self.quote_dao = Mock(autospec=QuoteDAO)
        self.quote_dao.get_supplier_objects_for_message.return_value = (
            self.supplier, Company(company_id=2, name='The Supplier'))

        self.quotes = [Mock(autospec=Quote), Mock(autospec=Quote)]
        self.quote_parser = Mock(autospec = QuoteParser)
        # QuoteEmailProcessor expects QuoteParser.extract_quotes to return a
        # generator, not a list
        self.quote_parser.extract_quotes.return_value = (q for q in self.quotes)
        QuoteParserClass = Mock()
        QuoteParserClass.return_value = self.quote_parser

        self.qep = QuoteEmailProcessor({1: QuoteParserClass}, self.quote_dao)

        self.message = Message()
        self.sender, self.recipient, self.subject = (
            'Sender', 'Recipient', 'Subject')
        self.message['From'] = self.sender
        self.message['To'] = self.recipient
        self.message['Subject'] = self.subject

    def test_process_email_malformed(self):
        with self.assertRaises(EmailError):
            self.qep.process_email(StringIO('wtf'))

        self.assertEqual(
            0, self.quote_dao.get_supplier_objects_for_message.call_count)
        self.assertEqual(0, self.quote_dao.begin_nested.call_count)
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

        self.quote_dao.get_supplier_objects_for_message.assert_has_calls([
            call(self.sender, self.recipient, self.subject)])
        self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_no_attachment(self):
        # email has no attachment in it
        self.qep.process_email(StringIO(self.message.as_string()))

        # supplier objects are looked up and found, but there is nothing else
        # to do
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(0, self.quote_parser.load_file.call_count)
        self.assertEqual(0, self.quote_parser.extract_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_non_matching_attachment(self):
        # supplier requires a specific attachment name, which doesn't match
        # the one in the email
        self.supplier.matrix_file_name = 'matrix_file.xls'
        self.message.add_header('Content-Disposition', 'attachment',
                                filename='unknown.xyz')
        email_file = StringIO(self.message.as_string())
        self.qep.process_email(email_file)

        # supplier objects are looked up and found, but nothing else happens
        # because the file is ignored
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        self.assertEqual(0, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(0, self.quote_parser.load_file.call_count)
        self.assertEqual(0, self.quote_parser.extract_quotes.call_count)
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_invalid_attachment(self):
        self.message.add_header('Content-Disposition', 'attachment',
                                filename='filename.xls')
        email_file = StringIO(self.message.as_string())
        self.quote_parser.extract_quotes.side_effect = ValidationError

        with self.assertRaises(ValidationError):
            self.qep.process_email(email_file)

        # quote parser doesn't like the file firmat, so no quotes are extracted
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        self.assertEqual(1, self.quote_dao.begin_nested.call_count)
        self.assertEqual(0, self.quote_dao.insert_quotes.call_count)
        self.assertEqual(1, self.quote_parser.load_file.call_count)
        self.quote_parser.extract_quotes.assert_called_once_with()
        self.quote_dao.rollback.assert_called_once_with()
        self.assertEqual(0, self.quote_dao.commit.call_count)

    def test_process_email_good_attachment(self):
        self.message.add_header('Content-Disposition', 'attachment',
                                filename='filename.xls')
        email_file = StringIO(self.message.as_string())

        self.qep.process_email(email_file)

        # normal situation: quotes are extracted from the file and committed
        # in a nested transaction
        self.assertEqual(
            1, self.quote_dao.get_supplier_objects_for_message.call_count)
        self.assertEqual(1, self.quote_dao.begin_nested.call_count)
        self.assertEqual(len(self.quotes),
                         self.quote_dao.insert_quotes.call_count)
        self.assertEqual(1, self.quote_parser.load_file.call_count)
        self.quote_parser.extract_quotes.assert_called_once_with()
        self.assertEqual(0, self.quote_dao.rollback.call_count)
        self.assertEqual(1, self.quote_dao.commit.call_count)


class TestQuoteEmailProcessorWithDB(TestCase):
    """Integration test using a real email with QuoteEmailProcessor,
    QuoteDAO, and QuoteParser, including the database.
    """
    def setUp(self):
        # example email containing a USGE matrix spreadsheet, matches the
        # Supplier object below. this has 2 quote file attachments but only 1
        #  has a corresponding QuoteParser class.
        self.email_file = open(EMAIL_FILE_PATH)
        self.quote_dao = QuoteDAO()
        self.qep = QuoteEmailProcessor(CLASSES_FOR_SUPPLIERS, self.quote_dao)

        # add a supplier to match the example email
        clear_db()
        self.supplier = Supplier(
            id=199, name='USGE',
            matrix_email_sender='Sender Name <sender@supplier.example.com>',
            matrix_file_name='2. USGE Gas.xlsx',
            matrix_email_subject="Today's Matrix Rates",
            matrix_email_recipient=('Recipient1 '
                                   '<recipient2@nextility.example.com>, '
                                   'Recipient2 <recipient1@nextility.com>'),
        )
        self.altitude_supplier = Company(name=self.supplier.name)

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

    def test_process_email_no_supplier_match(self):
        # supplier is missing but altitude_supplier is present
        AltitudeSession().add(self.altitude_supplier)
        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(self.email_file)

        # both are present but supplier doesn't match the email
        self.email_file.seek(0)
        Session().add(self.supplier)
        self.supplier.matrix_email_recipient = 'nobody@example.com'
        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(self.email_file)

    def test_process_email_no_altitude_supplier(self):
        Session().add(self.supplier)
        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(self.email_file)
