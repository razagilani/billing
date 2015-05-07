""" Unit tests for the UtilityAccount class
"""
import unittest
from test import init_test_config
init_test_config()
from core import init_model

from datetime import date
from unittest import TestCase

from test.setup_teardown import clear_db
from exc import RSIError, ProcessedBillError, NotProcessable
from core.model import UtilBill, Session, Charge,\
    Address, Register, Utility, Supplier, RateClass, UtilityAccount
from reebill.reebill_model import Payment, ReeBillCustomer

class UtilityAccountTest(TestCase):

    def setUp(self):
        init_model()
        clear_db()

        self.utility = Utility(name='utility', address=Address())
        self.supplier = Supplier(name='supplier', address=Address())
        self.utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass(name='FB Test Rate Class', utility=self.utility,
                      service='gas'), Address(), Address())
        self.rate_class = RateClass(name='rate class', utility=self.utility,
                                    service='gas')

    def tearDown(self):
        Session.remove()

    def test_get_service_address(self):
        session = Session()

        # Assert that the service address of the first bill is returned
        service_address1 = Address('Jules Watson', '123 Main St.',
                                   'Pleasantville', 'Va', '12345')
        ub1 = UtilBill(self.utility_account,
                       self.utility, self.rate_class, supplier=self.supplier,
                       service_address=service_address1)
        session.add(ub1)
        session.flush()
        self.assertEqual(service_address1,
                         self.utility_account.get_service_address())

        # The service address of the account should not change
        service_address2 = Address('Arthur Dent', '567 Deer Ct.',
                                   'Springfield', 'Il', '67890')
        ub2 = UtilBill(self.utility_account,
               self.utility, self.rate_class, supplier=self.supplier,
               service_address=service_address2)
        session.add(ub2)
        session.flush()
        self.assertEqual(service_address1,
                         self.utility_account.get_service_address())

        # If the account doesn't have any bills, fb_service_address should be
        # returned
        utility_account2 = UtilityAccount(
            'someone', '98987', self.utility, self.supplier,
            self.rate_class, Address(), service_address2)
        session.add(utility_account2)
        session.flush()
        self.assertEqual(service_address2, utility_account2.get_service_address())