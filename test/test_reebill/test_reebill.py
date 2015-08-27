"""Unit tests (or what should be unit tests) for SQLAlchemy classes in
reebill.reebill_model.
"""
import unittest
from datetime import date, datetime, timedelta
from mock import Mock
from core import init_model

from core.model import Address, \
    Charge, Register, Session, Utility, Supplier, RateClass, UtilityAccount
from core.model.utilbill import UtilBill, Charge
from core.model.model import RegisterTemplate
from exc import NoSuchBillException, NotIssuable
from reebill.reebill_model import ReeBill, ReeBillCustomer, Reading
from reebill.reebill_processor import ReebillProcessor
from test import init_test_config, clear_db, create_tables


def setUpModule():
    init_test_config()
    create_tables()

class ReeBillCustomerTest(unittest.TestCase):
    """Unit tests for the ReeBillCustomer class.
    """
    def setUp(self):
        self.customer = ReeBillCustomer()

    def test_get_first_unissued_bill(self):
        self.assertIsNone(self.customer.get_first_unissued_bill())

        # unfortunately it is necessary to use real ReeBill objects here
        # because mocks won't work with SQLAlchemy
        one = ReeBill(self.customer, 1)
        correction = ReeBill(self.customer, 1, version=1)
        two = ReeBill(self.customer, 2)

        for bill_set in [
            [one],
            [correction, one],
            [two, one],
            [one, two, correction],
        ]:
            self.customer.reebills = bill_set
            self.assertIs(one, self.customer.get_first_unissued_bill())

class ReadingTest(unittest.TestCase):
    """Unit tests for the Reading class.
    """
    def test_create_from_register(self):
        register = Mock(autospec=Register)
        register.register_binding = Register.DEMAND
        register.quantity = 123
        register.unit = 'kW'

        reading = Reading.create_from_register(register)
        self.assertEqual(register.register_binding, reading.register_binding)
        self.assertEqual(123, reading.conventional_quantity)
        self.assertEqual(0, reading.renewable_quantity)
        self.assertEqual(123, reading.hypothetical_quantity)
        self.assertEqual(Reading.ENERGY_SOLD_MEASURE, reading.measure)
        self.assertEqual('SUM', reading.aggregate_function)

        reading = Reading.create_from_register(register, estimate=True)
        self.assertEqual(register.register_binding, reading.register_binding)
        self.assertEqual(123, reading.conventional_quantity)
        self.assertEqual(0, reading.renewable_quantity)
        self.assertEqual(123, reading.hypothetical_quantity)
        self.assertEqual(Reading.ESTIMATED_MEASURE, reading.measure)
        self.assertEqual('SUM', reading.aggregate_function)

class ReeBillUnitTest(unittest.TestCase):
    def setUp(self):
        # unfortunately mocks will not work for any of the SQLAlchemy objects
        # because of relationships. replace with mocks if/when possible.
        utility_account = UtilityAccount('', '', None, None, None, None,
                                         Address(), Address())
        self.customer = ReeBillCustomer(
            utility_account=utility_account,
            bill_email_recipient='test@example.com')

        utilbill = UtilBill(utility_account, None, None,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        utilbill._registers = [Register(Register.TOTAL, 'kWh')]
        self.reebill = ReeBill(self.customer, 1, utilbill=utilbill)
        self.reebill.replace_readings_from_utility_bill_registers(utilbill)

        # currently it doesn't matter if the 2nd bill has the same utilbill
        # as the first, but might need to change
        self.reebill_2 = ReeBill(self.customer, 2, utilbill=utilbill)

    def test_is_estimated(self):
        self.assertFalse(self.reebill.is_estimated())

        self.reebill.readings[0].measure = Reading.ESTIMATED_MEASURE
        self.assertTrue(self.reebill.is_estimated())

        self.reebill.readings.append(
            Reading(Register.DEMAND, 'Demand', 0, 0, 'MAX', 'kW'))
        self.assertFalse(self.reebill.is_estimated())

    def test_make_correction(self):
        # can't make a correction when the bill is not issued
        with self.assertRaises(ValueError):
            self.reebill.make_correction()

        self.reebill.issue(datetime(2000,3,1), Mock())
        correction = self.reebill.make_correction()

        self.assertEqual(False, correction.issued)
        self.assertEqual(None, correction.issue_date)
        self.assertEqual(None, correction.due_date)
        self.assertEqual(1, correction.sequence)
        self.assertEqual(1, correction.version)
        self.assertEqual(self.reebill.discount_rate, correction.discount_rate)
        self.assertEqual(self.reebill.late_charge_rate,
                         correction.late_charge_rate)
        self.assertEqual(self.reebill.utilbill, correction.utilbill)
        self.assertEqual(self.reebill.billing_address,
                         correction.billing_address)
        self.assertEqual(self.reebill.service_address,
                         correction.service_address)

    def test_issue(self):
        self.assertEqual(None, self.reebill.email_recipient)
        self.assertEqual(None, self.reebill.issue_date)
        self.assertEqual(None, self.reebill.due_date)
        self.assertEqual(False, self.reebill.issued)

        reebill_processor = Mock(autospec=ReebillProcessor)
        now = datetime(2000,2,15)

        # can't issue this one yet
        with self.assertRaises(NotIssuable):
            self.reebill_2.issue(now, reebill_processor)

        self.reebill.issue(now, reebill_processor)

        # these calls may change or go away when more code is moved out of
        # ReebillProcessor
        self.assertEqual(1, reebill_processor.compute_reebill.call_count)
        self.assertEqual(1, reebill_processor.get_late_charge.call_count)

        self.assertEqual(self.customer.bill_email_recipient,
                         self.reebill.email_recipient)
        self.assertEqual(now, self.reebill.issue_date)
        self.assertEqual(now.date() + timedelta(30), self.reebill.due_date)
        self.assertEqual(True, self.reebill.issued)

        # after the first bill is issued, the 2nd one can be issued
        self.reebill_2.issue(now, reebill_processor)

    def test_issue_correction(self):
        now = datetime(2000, 2, 15)
        reebill_processor = Mock(autospec=ReebillProcessor)
        self.reebill.issue(now, reebill_processor)
        corrected_bill = self.reebill.make_correction()

        # corrected bills have None as their due_date and issue_date,
        # but even if they have these dates, that should not prevent issuing
        # them (this was reported to have happened in production)
        corrected_bill.issue_date = now
        corrected_bill.due_date = datetime(2000, 3, 15)
        corrected_bill.issue(now, reebill_processor)


class ReebillTestWithDB(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        create_tables()
        init_model()

    def setUp(self):
        washgas = Utility(name='washgas', address=Address())
        supplier = Supplier(name='supplier')
        c_rate_class = RateClass(name='Test Rate Class', utility=washgas,
                                 service='gas')
        utility_account = UtilityAccount('someaccount', '11111',
                            washgas, supplier, c_rate_class,
                            Address(), Address())
        reebill_customer = ReeBillCustomer(name='someone', discount_rate=0.5,
                                late_charge_rate=0.1, service='thermal',
                                bill_email_recipient='example@example.com',
                                utility_account=utility_account)
        u_rate_class = RateClass(name='DC Non Residential Non Heat',
                                 utility=washgas, service='gas')
        self.utilbill = UtilBill(utility_account, washgas,
                                 u_rate_class,
                                 supplier=supplier,
                                 period_start=date(2000, 1, 1),
                                 period_end=date(2000, 2, 1))
        self.register = Register(Register.TOTAL, 'therms', quantity=100)
        self.utilbill._registers = [self.register]
        self.utilbill.charges = [
            Charge('A', formula=Charge.get_simple_formula(Register.TOTAL),
                   rate=2, description='a', unit='therms'),
            Charge('B', formula='1', rate=1, description='b', unit='therms',
                   has_charge=False),
        ]

        self.reebill = ReeBill(reebill_customer, 1, discount_rate=0.5,
                               late_charge_rate=0.1, utilbill=self.utilbill)
        Session().add_all([self.utilbill, self.reebill])
        self.reebill.replace_readings_from_utility_bill_registers(self.utilbill)

    def tearDown(self):
        pass

    def test_compute_charges(self):
        self.assertEqual(1, len(self.reebill.readings))
        reading = self.reebill.readings[0]
        self.assertEqual(100, reading.conventional_quantity)
        self.assertEqual(0, reading.renewable_quantity)

        self.reebill.compute_charges()

        # check that there are the same group names and rsi_bindings in
        # reebill charges as utility bill charges
        self.assertEqual(
            set((c.rsi_binding, c.description) for c in self.utilbill.charges if
                c.has_charge),
            set((c.rsi_binding, c.description) for c in self.reebill.charges)
        )

        # check reebill charges. since there is no renewable energy,
        # hypothetical charges should be identical to actual charges:
        self.assertEqual(1, len(self.reebill.charges))
        c = self.reebill.charges[0]
        self.assertEqual('A', c.rsi_binding)
        self.assertEqual('a', c.description)
        self.assertEqual(100, c.a_quantity)
        self.assertEqual(100, c.h_quantity)
        self.assertEqual(2, c.rate)
        self.assertEqual(200, c.a_total)
        self.assertEqual(200, c.h_total)
        self.assertEqual(200, self.reebill.get_total_hypothetical_charges())

    def test_unit_conversion(self):
        #init_config()
        # 10000 btu = 1 therm
        self.reebill.readings[0].unit = 'btu'
        self.reebill.readings[0].conventional_quantity = 200000
        self.reebill.readings[0].renewable_quantity = 200000
        self.assertAlmostEqual(self.reebill.get_total_conventional_energy(), 2.00, 2)
        self.assertAlmostEqual(self.reebill.get_total_renewable_energy(), 2.00, 2)
        # if the unit is already btu then no conversion is needed
        self.reebill.set_renewable_energy_reading(Register.TOTAL, 200000)
        self.assertEqual(self.reebill.readings[0].renewable_quantity, 200000)
        # 29.307111111 is approximately equal to 1 therm
        self.reebill.readings[0].unit = 'kwh'
        self.reebill.readings[0].conventional_quantity = 29.307111111
        self.reebill.readings[0].renewable_quantity = 29.307111111
        self.assertAlmostEqual(self.reebill.get_total_conventional_energy(), 1.00, 2)
        self.assertAlmostEqual(self.reebill.get_total_renewable_energy(), 1.00, 2)
        # 1btu is equal to 0.00029307107 kwh
        self.reebill.set_renewable_energy_reading(Register.TOTAL, 1)
        self.assertAlmostEquals(self.reebill.readings[0].renewable_quantity, 0.00029307107)
        self.reebill.readings[0].unit = 'therms'
        self.reebill.readings[0].conventional_quantity = 29.307111111
        self.reebill.readings[0].renewable_quantity = 29.307111111
        # no conversion is needed if the unit is already therms
        self.assertAlmostEqual(self.reebill.get_total_conventional_energy(), 29.307, 3)
        self.assertAlmostEqual(self.reebill.get_total_renewable_energy(), 29.307, 3)
        # 1 btu is equal to 1.0000000000000003e-05 therms
        self.reebill.set_renewable_energy_reading(Register.TOTAL, 1)
        self.assertAlmostEqual(self.reebill.readings[0].renewable_quantity, 1.0000000000000003e-05)
        self.reebill.readings[0].unit = 'ccf'
        self.reebill.readings[0].conventional_quantity = 29.307111111
        self.reebill.readings[0].renewable_quantity = 29.307111111
        self.assertAlmostEqual(self.reebill.get_total_conventional_energy(ccf_conversion_factor=2), 58.61, 2)
        self.assertAlmostEqual(self.reebill.get_total_renewable_energy(ccf_conversion_factor=2), 58.61, 2)
        self.reebill.set_renewable_energy_reading(Register.TOTAL, 1)
        self.assertAlmostEqual(self.reebill.readings[0].renewable_quantity, 1.0000000000000003e-05)
        self.reebill.readings[0].unit = 'kwd'
        self.reebill.readings[0].conventional_quantity = 29.307111111
        self.reebill.readings[0].renewable_quantity = 29.307111111
        self.assertEquals(self.reebill.get_total_conventional_energy(), 0)
        self.assertAlmostEqual(self.reebill.get_total_renewable_energy(), 0)
        self.reebill.set_renewable_energy_reading(Register.TOTAL, 1)
        self.assertEquals(self.reebill.readings[0].renewable_quantity, 1)

    def test_replace_readings_from_utility_bill_registers(self):
        # adding a register
        new_register = Register(Register.DEMAND, 'kWh', quantity=200)
        self.utilbill._registers.append(new_register)
        self.reebill.replace_readings_from_utility_bill_registers(self.utilbill)

        reading_0, reading_1 = self.reebill.readings
        self.assertEqual(self.register.register_binding,
                         reading_0.register_binding)
        self.assertEqual(self.register.quantity,
                         reading_0.conventional_quantity)
        self.assertEqual(self.register.unit, reading_0.unit)
        self.assertEqual(new_register.register_binding,
                         reading_1.register_binding)
        self.assertEqual(new_register.quantity, reading_1.conventional_quantity)
        self.assertEqual(new_register.unit, reading_1.unit)
        for r in (reading_0, reading_1):
            self.assertEqual('Energy Sold', r.measure)
            self.assertEqual('SUM', r.aggregate_function)
            self.assertEqual(0, r.renewable_quantity)

        # removing a register
        self.utilbill._registers.remove(self.utilbill._registers[0])
        self.reebill.replace_readings_from_utility_bill_registers(self.utilbill)
        self.assertEqual(1, len(self.reebill.readings))
        self.assertEqual(new_register.register_binding,
                         self.reebill.readings[0].register_binding)
        self.assertEqual(new_register.quantity,
                         self.reebill.readings[0].conventional_quantity)
        self.assertEqual(new_register.unit,
                         self.reebill.readings[0].unit)
        self.assertEqual('Energy Sold', self.reebill.readings[0].measure)
        self.assertEqual('SUM', self.reebill.readings[0].aggregate_function)
        self.assertEqual(0, self.reebill.readings[0].renewable_quantity)

    def test_reading(self):
        '''Test some method calls on the Reading class.
        '''
        reading = self.reebill.readings[0]
        self.assertIs(sum, reading.get_aggregation_function())

        reading.aggregate_function = 'MAX'
        self.assertIs(max, reading.get_aggregation_function())

        reading.aggregate_function = ''
        with self.assertRaises(ValueError):
            reading.get_aggregation_function()
