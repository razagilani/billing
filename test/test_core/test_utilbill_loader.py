import unittest
from datetime import date

from test import init_test_config
from test.setup_teardown import clear_db, create_tables
from core import init_model
from core.model import UtilBill, Session, \
    Address, Utility, Supplier, RateClass, UtilityAccount
from core.utilbill_loader import UtilBillLoader
from exc import NoSuchBillException


def setUpModule():
    init_test_config()
    create_tables()
    init_model()


class UtilbillLoaderTest(unittest.TestCase):

    def setUp(self):
        clear_db()

        self.session = Session()
        blank_address = Address()
        utility =  Utility(name='Test Utility', address=Address())
        self.utility_account = UtilityAccount('Test Customer', 99999,
                            utility,
                            Supplier(name='Test Supplier', address=Address()),
                            RateClass(name='FB Test Rate Class',
                                      utility=utility, service='gas'),
                            blank_address, blank_address)
        self.session.add(self.utility_account)
        self.session.commit()

        self.session = Session()
        self.ubl = UtilBillLoader()

    def tearDown(self):
        clear_db()

    def test_get_last_real_utilbill(self):
        utility_account = self.session.query(UtilityAccount).one()
        washington_gas = utility_account.fb_utility
        supplier = utility_account.fb_supplier
        pepco = Utility(name='pepco', address=Address())
        other_supplier = Supplier(name='Other Supplier', address=Address())
        rateclass1 = RateClass(name='DC Non Residential Non Heat',
                               utility=washington_gas, service='gas')
        rateclass2 = RateClass(name='whatever', utility=pepco,
                               service='electric')

        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2001,1,1))

        # one bill
        gas_bill_1 = UtilBill(utility_account, washington_gas,
                              rateclass1, supplier=supplier,
                              period_start=date(2000,1,1),
                              period_end=date(2000,2,1))
        self.session.add(gas_bill_1)

        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 2, 1)))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000,1,31))

        # two bills
        electric_bill = UtilBill(utility_account, pepco,
                                 rateclass2, supplier=other_supplier,
                                 period_start=date(2000,1,2),
                                 period_end=date(2000,2,2))
        self.session.add(electric_bill)
        self.assertEqual(electric_bill,
                         self.ubl.get_last_real_utilbill('99999', end=None))
        self.assertEqual(electric_bill, self.ubl.get_last_real_utilbill(
                             '99999', end=date(2000, 3, 1)))
        self.assertEqual(electric_bill, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 2, 2)))
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 2, 1)))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000, 1, 31))

        # electric bill is ignored if service "gas" is specified
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 2, 2), service='gas'))
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 2, 1), service='gas'))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000,1,31), service='gas')

        # filter by utility and rate class
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 3, 1), utility=gas_bill_1.utility))
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 3, 1), rate_class=rateclass1))
        self.assertEqual(electric_bill, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 3, 1), utility=pepco,
            rate_class=rateclass2))
        self.assertEqual(electric_bill, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 3, 1), rate_class=rateclass2))
        self.assertEqual(electric_bill, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 3, 1), utility=pepco,
            rate_class=rateclass2))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000,1,31), utility=washington_gas,
                          rate_class=rateclass2)

    def test_count_utilbills_with_hash(self):
        hash = '01234567890abcdef'
        self.assertEqual(0, self.ubl.count_utilbills_with_hash(hash))

        self.session.add(
            UtilBill(self.utility_account, self.utility_account.fb_utility,
                     RateClass(name='RC1',
                               utility=self.utility_account.fb_utility,
                               service='gas'),
                     supplier=self.utility_account.fb_supplier,
                     period_start=date(2000, 1, 1),
                     period_end=date(2000, 2, 1), sha256_hexdigest=hash))
        self.assertEqual(1, self.ubl.count_utilbills_with_hash(hash))

        self.session.add(
            UtilBill(self.utility_account, self.utility_account.fb_utility,
                     RateClass(name='RC2',
                               utility=self.utility_account.fb_utility,
                               service='gas'),
                     supplier=self.utility_account.fb_supplier,
                     period_start=date(2000, 2, 1),
                     period_end=date(2000, 3, 1), sha256_hexdigest=hash))
        self.assertEqual(2, self.ubl.count_utilbills_with_hash(hash))

        self.session.add(
            UtilBill(self.utility_account, self.utility_account.fb_utility,
                     RateClass(name='RC3',
                               utility=self.utility_account.fb_utility,
                               service='gas'),
                     supplier=self.utility_account.fb_supplier,
                     period_start=date(2000, 3, 1),
                     period_end=date(2000, 4, 1),
                     sha256_hexdigest='somethingelse'))
        self.assertEqual(2, self.ubl.count_utilbills_with_hash(hash))

    def test_get_utilbills_for_account_id(self):
        self.assertEqual([], self.ubl.get_utilbills_for_account_id(
            self.utility_account.id).all())

        other_account = UtilityAccount(
            'other', '1', self.utility_account.fb_utility,
            self.utility_account.fb_supplier,
            self.utility_account.fb_rate_class,
            self.utility_account.fb_billing_address,
            self.utility_account.fb_service_address)
        self.session.add(other_account)
        bills = [
            UtilBill(self.utility_account, self.utility_account.fb_utility,
                     RateClass(name='RC1',
                               utility=self.utility_account.fb_utility,
                               service='gas'),
                     supplier=self.utility_account.fb_supplier,
                     period_start=date(2000, 3, 1),
                     period_end=date(2000, 4, 1),
                     sha256_hexdigest='abc'),
            UtilBill(other_account, self.utility_account.fb_utility,
                     RateClass(name='RC2', utility=other_account.fb_utility,
                               service='gas'),
                     supplier=other_account.fb_supplier,
                     period_start=date(2000, 3, 1), period_end=date(2000, 4, 1),
                     sha256_hexdigest='def'),
        ]
        self.session.add_all(bills)
        self.assertEqual([bills[0]], self.ubl.get_utilbills_for_account_id(
            self.utility_account.id).all())
        self.assertEqual([bills[1]], self.ubl.get_utilbills_for_account_id(
            other_account.id).all())
