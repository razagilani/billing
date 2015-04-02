from unittest import TestCase
from core import init_model, get_private_data_column_names
from test import init_test_config


def setUpModule():
    init_test_config()
    init_model()

class TestGetPrivateDataColumns(TestCase):

    def test_1(self):
        expected = [('reebill_customer', 'bill_email_recipient',
                     "'example@example.com'"),
                    ('reebill', 'email_recipient', "'example@example.com'")]
        actual = get_private_data_column_names()
        self.assertEqual(expected, actual)