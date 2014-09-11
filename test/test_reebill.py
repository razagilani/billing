import unittest
from datetime import date

from mock import Mock

from billing.processing.state import ReeBill, Customer, UtilBill, Address, \
    Charge, Register, Session, Utility


class ReebillTest(unittest.TestCase):

    def test_compute_charges(self):

        test_utility = Utility('Test Utility', Address('', '', '', '', ''))

        customer = Customer('someone', '11111', 0.5, 0.1,
                'example@example.com', test_utility, 'Test Rate Class',
                Address(), Address())

        washgas = Utility('washgas', Address('', '', '', '', ''))

        utilbill = UtilBill(customer, UtilBill.Complete, 'gas', washgas,
                'DC Non Residential Non Heat', period_start=date(2000,1,1),
                period_end=date(2000,2,1),
                billing_address=Address(), service_address=Address())
        utilbill.registers = [Register(utilbill, '', 100, 'therms', '', False,
                'total', 'REG_TOTAL', [], '')]
        utilbill.charges = [
            Charge(utilbill, 'a', 'All Charges', 0, 'therms',
                    2,'A', 0, quantity_formula='REG_TOTAL.quantity'),
            Charge(utilbill, 'b', 'All Charges', 0, 'therms', 1, 'B', 0,
                    quantity_formula='1', has_charge=False),
        ]

        reebill = ReeBill(customer, 1, discount_rate=0.5, late_charge_rate=0.1,
                utilbills=[utilbill])
        reebill.replace_readings_from_utility_bill_registers(utilbill)

        Session().add_all([utilbill, reebill])
        self.assertEqual(1, len(reebill.readings))
        reading = reebill.readings[0]
        self.assertEqual(100, reading.conventional_quantity)
        self.assertEqual(0, reading.renewable_quantity)

        reebill.compute_charges()

        # check that there are the same group names and rsi_bindings in
        # reebill charges as utility bill charges
        self.assertEqual(
            set((c.rsi_binding, c.description) for c in utilbill.charges if
                c.has_charge),
            set((c.rsi_binding, c.description) for c in reebill.charges)
        )

        # check reebill charges. since there is no renewable energy,
        # hypothetical charges should be identical to actual charges:
        self.assertEqual(1, len(reebill.charges))
        c = reebill.charges[0]
        self.assertEqual('A', c.rsi_binding)
        self.assertEqual('a', c.description)
        self.assertEqual(100, c.a_quantity)
        self.assertEqual(100, c.h_quantity)
        self.assertEqual(2, c.a_rate)
        self.assertEqual(2, c.h_rate)
        self.assertEqual(200, c.a_total)
        self.assertEqual(200, c.h_total)
        self.assertEqual('All Charges', c.group)
        self.assertEqual(200, reebill.get_total_hypothetical_charges())

