import unittest
from reebill.reebill_model import ReeBillCustomer


class ReeBillCustomerTest(unittest.TestCase):
    """Unit tests for ReeBillCustomer.
    """
    def setUp(self):
        self.reebill_customer = ReeBillCustomer()

    def test_tag(self):
        self.assertEqual('', self.reebill_customer.tag)
        self.reebill_customer.set_tag('a')
        self.assertEqual('a', self.reebill_customer.get_tag())
        self.reebill_customer.set_tag('b')
        self.assertEqual('b', self.reebill_customer.get_tag())