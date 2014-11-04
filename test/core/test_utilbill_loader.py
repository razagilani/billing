import unittest
from datetime import date

from billing.test.setup_teardown import TestCaseWithSetup
from billing import init_config, init_model
from billing.core.model import Customer, UtilBill, Session, \
    Address, UtilBillLoader, Utility, Supplier, RateClass
from billing.exc import NoSuchBillException


class UtilbillLoaderTest(TestCaseWithSetup):

    def setUp(self):
        # clear out database
        init_config('test/tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables(self.session)
        blank_address = Address()
        utility =  Utility('Test Utility', Address(), '')
        self.customer = Customer('Test Customer', 99999, .12, .34,
                            'example@example.com', utility,
                            Supplier('Test Supplier', Address(), ''),
                            RateClass('FB Test Rate Class', utility),
                            blank_address, blank_address)
        self.session.add(self.customer)
        self.session.commit()

        self.session = Session()
        self.ubl = UtilBillLoader(self.session)

    def tearDown(self):
        self.session.commit()
        # clear out tables in mysql test database (not relying on StateDB)
        #mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        #self._clear_tables(mysql_connection)

    def test_get_last_real_utilbill(self):
        customer = self.session.query(Customer).one()
        washington_gas = customer.fb_utility
        supplier = customer.fb_supplier
        pepco = Utility('pepco', Address(), '')
        other_supplier = Supplier('Other Supplier', Address(), '')
        rateclass1 = RateClass('DC Non Residential Non Heat', washington_gas)
        rateclass2 = RateClass('whatever', pepco)

        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          date(2001,1,1))

        # one bill
        empty_address = Address()
        gas_bill_1 = UtilBill(customer, 0, 'gas', washington_gas, supplier,
                              rateclass1, empty_address, empty_address,
                              period_start=date(2000,1,1),
                              period_end=date(2000,2,1))
        self.session.add(gas_bill_1)

        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000, 2, 1)))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000,1,31))

        # two bills
        electric_bill = UtilBill(customer, 0, 'electric', pepco, other_supplier,
                                 rateclass2, empty_address, empty_address,
                                 period_start=date(2000,1,2),
                                 period_end=date(2000,2,2))
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
            '99999', date(2000, 2, 2), service='gas'))
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', date(2000, 2, 1), service='gas'))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          date(2000,1,31), service='gas')

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
            UtilBill(self.customer, 0, 'gas', self.customer.fb_utility,
                     self.customer.fb_supplier,
                     RateClass('DC Non Residential Non Heat', self.customer.fb_utility),
                     Address(), Address(), period_start=date(2000, 1, 1),
                     period_end=date(2000, 2, 1), sha256_hexdigest=hash))
        self.assertEqual(1, self.ubl.count_utilbills_with_hash(hash))

        self.session.add(
            UtilBill(self.customer, 0, 'gas', self.customer.fb_utility,
                     self.customer.fb_supplier,
                     RateClass('DC Non Residential Non Heat', self.customer.fb_utility),
                     Address(), Address(), period_start=date(2000, 2, 1),
                     period_end=date(2000, 3, 1), sha256_hexdigest=hash))
        self.assertEqual(2, self.ubl.count_utilbills_with_hash(hash))

        self.session.add(
            UtilBill(self.customer, 0, 'gas', self.customer.fb_utility,
                     self.customer.fb_supplier,
                     RateClass('DC Non Residential Non Heat', self.customer.fb_utility),
                     Address(), Address(), period_start=date(2000, 3, 1),
                     period_end=date(2000, 4, 1),
                     sha256_hexdigest='somethingelse'))
        self.assertEqual(2, self.ubl.count_utilbills_with_hash(hash))

if __name__ == '__main__':
    unittest.main()
