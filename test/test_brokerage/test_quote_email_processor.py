from cStringIO import StringIO
from unittest import TestCase
from brokerage.brokerage_model import Company, Quote
from brokerage.quote_email_processor import QuoteEmailProcessor, EmailError, \
    UnknownSupplierError
from core import init_altitude_db, init_model
from core.model import Supplier, Session, AltitudeSession
from test import init_test_config, clear_db, create_tables


def setUpModule():
    init_test_config()
    create_tables()
    init_model()
    init_altitude_db()

class TestQuoteEmailProcessor(TestCase):
    """Integration test of receiving a supplier's matrix quote email from
    stdin, deterimining which supplier it belongs to, reading quotes from an
    attached spreadsheet file, and inserting the quotes into the database.
    """
    # example email containing a USGE matrix spreadsheet, matches the
    # Supplier object below. this has 2 quote file attachments but only 1 has a
    # corresponding QuoteParser class.
    EMAIL_FILE_PATH = 'quote_email.txt'

    def setUp(self):
        self.email_file = open(self.EMAIL_FILE_PATH)
        self.qep = QuoteEmailProcessor()

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

    def test_process_email_malformed(self):
        with self.assertRaises(EmailError):
            self.qep.process_email(StringIO('bad email'))

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
        AltitudeSession().add(self.altitude_supplier)
        with self.assertRaises(UnknownSupplierError):
            self.qep.process_email(self.email_file)

    def test_process_email_no_attachment(self):
        pass
        # TODO: make an example email with no attachment

