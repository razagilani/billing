from datetime import datetime
from unittest import TestCase
from brokerage.brokerage_model import Quote, MatrixQuote
from exc import ValidationError


class QuoteTest(TestCase):
    """Unit tests for Quote.
    """
    def setUp(self):
        self.quote = Quote(start_from=datetime(2000, 3, 1),
                           start_until=datetime(2000, 4, 1), term_months=3,
                           valid_from=datetime(2000, 1, 1),
                           valid_until=datetime(2000, 1, 2), price=0.1)

    def test_validate(self):
        self.quote.validate()

        q = self.quote.clone()
        q.start_from = datetime(2000, 4, 1)
        self.assertRaises(ValidationError, q.validate)

        q = self.quote.clone()
        q.valid_until = datetime(2000, 1, 1)
        self.assertRaises(ValidationError, q.validate)

        q = self.quote.clone()
        q.term_months = 0
        self.assertRaises(ValidationError, q.validate)
        q.term_months = 37
        self.assertRaises(ValidationError, q.validate)

        q = self.quote.clone()
        q.price = 0.001
        self.assertRaises(ValidationError, q.validate)
        q.price = 10
        self.assertRaises(ValidationError, q.validate)


class MatrixQuoteTest(TestCase):
    """Unit tests for MatrixQuote.
    """
    def setUp(self):
        self.quote = MatrixQuote(start_from=datetime(2000, 3, 1),
                                 start_until=datetime(2000, 4, 1),
                                 term_months=3, valid_from=datetime(2000, 1, 1),
                                 valid_until=datetime(2000, 1, 2), price=0.1,
                                 min_volume=0, limit_volume=100)

    def test_validate(self):
        # TODO
        pass
