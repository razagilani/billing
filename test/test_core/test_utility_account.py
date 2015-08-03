""" Unit tests for the UtilityAccount class
"""
from datetime import date
from unittest import TestCase
from exc import NoSuchBillException

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from test import init_test_config
init_test_config()

from test import create_tables, clear_db
from core import init_model
from core.model import UtilBill, Session, Address, Utility, Supplier, \
    RateClass, UtilityAccount

class UtilityAccountUnitTest(TestCase):
    """Unit tests for UtilityAccount."""
    def setUp(self):
        # self.utility = Utility(name='utility', address=Address())
        # self.supplier = Supplier(name='supplier', address=Address())
        # self.rate_class = RateClass(name='rate class', utility=self.utility,
        #                             service='gas')
        self.ua = UtilityAccount('example', '1', None, None, None, Address(),
                                 Address())
        self.u1 = UtilBill(self.ua, None, None, period_start=date(2000, 1, 2),
                           period_end=date(2000, 2, 1), processed=True)
        self.u2 = UtilBill(self.ua, None, None, period_start=date(2000, 1, 1),
                           period_end=date(2000, 2, 2), processed=False)

    def test_get_last_bill(self):
        self.assertEqual(self.u2, self.ua.get_last_bill())
        self.assertEqual(self.u1, self.ua.get_last_bill(processed=True))
        self.assertEqual(self.u2, self.ua.get_last_bill(end=date(2000, 2, 2)))
        self.assertEqual(self.u1, self.ua.get_last_bill(end=date(2000, 2, 1)))

        self.ua.utilbills = [self.u1]
        self.assertEqual(self.u1, self.ua.get_last_bill())

        # no bills, or bills without period_end date, causes exception
        self.ua.utilbills = []
        with self.assertRaises(NoSuchBillException):
            self.ua.get_last_bill()
        self.ua.utilbills = [
            UtilBill(self.ua, None, None, period_start=date(2000, 1, 3),
                     period_end=None, processed=False)]
        with self.assertRaises(NoSuchBillException):
            self.ua.get_last_bill()

    def test_get_utility(self):
        a = Utility(name='a')
        b = Utility(name='b')

        self.ua.fb_utility = a

        # the account has 2 bills, so even though fb_utility is 'a',
        # the bills with utility None override that
        self.assertIsNone(self.ua.get_utility())

        # any bill may be used to determine the utility
        self.u1.set_utility(b)
        self.u2.set_utility(b)
        self.assertEqual(b, self.ua.get_utility())

        # when there are no bills, fb_utility is used
        self.ua.utilbills = []
        self.assertEqual(a, self.ua.get_utility())


class UtilityAccountTest(TestCase):
    """Integration test using the database."""

    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()

    def setUp(self):
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
        # TODO: this test can be moved to UtilityAccountUnitTest above,
        # since the code does not require explicit database queries. it can
        # look just like test_get_utility.

        session = Session()

        # Assert that the service address of the first bill is returned
        service_address1 = Address(addressee='Jules Watson',
                                   street='123 Main St.', city='Pleasantville',
                                   state='Va', postal_code='12345')
        ub1 = UtilBill(self.utility_account,
                       self.utility, self.rate_class, supplier=self.supplier,
                       service_address=service_address1)
        session.add(ub1)
        session.flush()
        self.assertEqual(service_address1,
                         self.utility_account.get_service_address())

        # The service address of the account should not change
        service_address2 = Address(addressee='Arthur Dent',
                                   street='567 Deer Ct.', city='Springfield',
                                   state='Il', postal_code='67890')
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
        self.assertEqual(service_address2,
                         utility_account2.get_service_address())