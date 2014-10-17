import unittest
from datetime import date

from billing.test.setup_teardown import TestCaseWithSetup
from billing import init_config, init_model
from billing.core.model import Customer, UtilBill, Session, \
    Address, UtilBillLoader, Utility
from billing.exc import NoSuchBillException


class UtilbillLoaderTest(TestCaseWithSetup):

    def setUp(self):
        # clear out database
        init_config('test/tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables(self.session)
        blank_address = Address()
        customer = Customer('Test Customer', 99999, .12, .34,
                            'example@example.com', Utility('Test Utility',
                            Address(), ''), 'FB Test Rate Class', blank_address,
                            blank_address)
        self.session.add(customer)
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
        pepco = Utility('pepco', Address(), '')

        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          date(2001,1,1))

        # one bill
        empty_address = Address()
        gas_bill_1 = UtilBill(customer, 0, 'gas', washington_gas,
                              'DC Non Residential Non Heat', empty_address, empty_address,
                              period_start=date(2000,1,1), period_end=date(2000,2,1))
        self.session.add(gas_bill_1)

        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', end=date(2000,2,1)))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000,1,31))

        # two bills
        electric_bill = UtilBill(customer, 0, 'electric', pepco,
                                 'whatever', empty_address, empty_address,
                                 period_start=date(2000,1,2), period_end=date(2000,2,2))
        self.assertEqual(electric_bill,
                         self.ubl.get_last_real_utilbill('99999',
                         end=date(2000, 3, 1)))
        self.assertEqual(electric_bill,
                         self.ubl.get_last_real_utilbill('99999',
                                                         end=date(2000, 2, 2)))
        self.assertEqual(gas_bill_1,
                         self.ubl.get_last_real_utilbill('99999',
                                                         end=date(2000, 2, 1)))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000, 1, 31))

        # electric bill is ignored if service "gas" is specified
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', date(2000,2,2), service='gas'))
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill(
            '99999', date(2000,2,1), service='gas'))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          date(2000,1,31), service='gas')

        # filter by utility and rate class
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill('99999',
                end=date(2000, 3, 1), utility=gas_bill_1.utility))
        self.assertEqual(gas_bill_1, self.ubl.get_last_real_utilbill('99999',
                         end=date(2000, 3, 1),
                         rate_class='DC Non Residential Non Heat'))
        self.assertEqual(electric_bill,
                         self.ubl.get_last_real_utilbill('99999',
                        end=date(2000,3, 1), utility=pepco,
                        rate_class='whatever'))
        self.assertEqual(electric_bill,
                         self.ubl.get_last_real_utilbill('99999',
                        end=date(2000,3, 1), rate_class='whatever'))
        self.assertEqual(electric_bill,
                         self.ubl.get_last_real_utilbill('99999',
                                                         end=date(2000, 3, 1),
                                                         utility=pepco,
                                                         rate_class='whatever'))
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999',
                          end=date(2000,1,31), utility=washington_gas,
                          rate_class='whatever')

        # hypothetical utility bills are always ignored
        gas_bill_1.state = UtilBill.Hypothetical
        electric_bill.state = UtilBill.Hypothetical
        self.assertRaises(NoSuchBillException,
                          self.ubl.get_last_real_utilbill, '99999', date(2000,3,1))


if __name__ == '__main__':
    unittest.main()
