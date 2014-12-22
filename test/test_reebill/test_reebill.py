import unittest
from datetime import date

from core.model import UtilBill, Address, \
    Charge, Register, Session, Utility, Customer, Supplier, RateClass, UtilityAccount
from reebill.state import ReeBill, ReeBillCustomer

class ReebillTest(unittest.TestCase):
    def setUp(self):
        washgas = Utility('washgas', Address('', '', '', '', ''))
        supplier = Supplier('supplier', Address())
        c_rate_class = RateClass('Test Rate Class', washgas)
        utility_account = UtilityAccount('someaccount', '11111',
                            washgas, supplier, c_rate_class,
                            Address(), Address())
        reebill_customer = ReeBillCustomer('someone', '11111', 0.5, 0.1,
                            'example@example.com', utility_account)
        u_rate_class = RateClass('DC Non Residential Non Heat', washgas)
        self.utilbill = UtilBill(utility_account, UtilBill.Complete, 'gas', washgas,
                                 supplier,
                                 u_rate_class,
                                 period_start=date(2000, 1, 1),
                                 period_end=date(2000, 2, 1),
                                 billing_address=Address(),
                                 service_address=Address())
        self.register = Register(self.utilbill, '', '', 'therms', False,
                                 'total', [], '', quantity=100,
                                register_binding='REG_TOTAL')
        self.utilbill.registers = [self.register]
        self.utilbill.charges = [
            Charge(self.utilbill, 'A', 2, 'REG_TOTAL.quantity', 'a',
                   'All Charges', 'therms'),
            Charge(self.utilbill, 'B', 1, '1', 'b', 'All Charges','therms',
                   has_charge=False),
        ]

        self.reebill = ReeBill(reebill_customer, 1, discount_rate=0.5,
                               late_charge_rate=0.1,
                               utilbills=[self.utilbill])
        Session().add_all([self.utilbill, self.reebill])
        self.reebill.replace_readings_from_utility_bill_registers(
                self.utilbill)

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
        self.assertEqual('All Charges', c.group)
        self.assertEqual(200, self.reebill.get_total_hypothetical_charges())

    def test_replace_readings_from_utility_bill_registers(self):
        # adding a register
        new_register = Register(self.utilbill, '', '',
                 'kWh', False, 'total', [], '',quantity=200,
                 register_binding='NEW_REG')
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
        self.utilbill.registers.remove(self.utilbill.registers[0])
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
