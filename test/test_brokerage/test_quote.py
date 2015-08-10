from datetime import datetime
from unittest import TestCase
from brokerage.brokerage_model import Quote, MatrixQuote, \
    load_rate_class_aliases, RateClassAlias, RateClass
from core import init_altitude_db, init_model
from core.model import AltitudeSession
from exc import ValidationError
from test import init_test_config, clear_db, create_tables


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

class TestLoadRateClassAliases(TestCase):

    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()
        init_altitude_db()

    def setUp(self):
        clear_db()
        s = AltitudeSession()
        s.add_all([
            RateClass(rate_class_id=1),
            RateClass(rate_class_id=2),
            RateClass(rate_class_id=3),
            RateClass(rate_class_id=4),
        ])
        s.add_all([
            # 1 to 1
            RateClassAlias(rate_class_alias='a', rate_class_id=1),
            # b and c both map to 2
            RateClassAlias(rate_class_alias='b', rate_class_id=2),
            RateClassAlias(rate_class_alias='c', rate_class_id=2),
            # c also maps to 3
            RateClassAlias(rate_class_alias='c', rate_class_id=3)
        ])

    def tearDown(self):
        clear_db()

    def test_load_rate_class_aliases_normal(self):
        expected = {
            'a': [1],
            'b': [2],
            'c': [2, 3],
        }
        self.assertEqual(expected, load_rate_class_aliases())

    def test_load_rate_class_aliases_empty(self):
        AltitudeSession.expunge_all()
        self.assertEqual({}, load_rate_class_aliases())
