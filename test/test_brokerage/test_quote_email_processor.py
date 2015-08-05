from unittest import TestCase
from brokerage.brokerage_model import Company, Quote
from brokerage.quote_file_processor import QuoteEmailProcessor
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
    # Supplier object below
    EMAIL_FILE_PATH = 'quote_email.txt'

    def setUp(self):
        self.email_file = open(self.EMAIL_FILE_PATH)
        self.qep = QuoteEmailProcessor()

        # add a supplier to match the example email
        clear_db()
        s = Session()
        s.add(Supplier(
            id=199, name='USGE',
            matrix_email_sender='Sender Name <sender@supplier.example.com>',
            matrix_file_name='2. USGE Gas.xlsx',
            matrix_email_subject="Today's Matrix Rates",
            matrix_email_recipient=('Recipient1 '
                                   '<recipient2@nextility.example.com>, '
                                   'Recipient2 <recipient1@nextility.com>'),
        ))
        AltitudeSession().add(Company(name='USGE'))

    def tearDown(self):
        self.email_file.close()
        clear_db()

    def test_process_email(self):
        a = AltitudeSession()
        self.assertEqual(0, a.query(Quote).count())

        self.qep.process_email(self.email_file)
        self.assertEqual(2144, a.query(Quote).count())
