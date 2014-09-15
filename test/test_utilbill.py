'''Unit tests for the UtilBill class and other code that will eventually be
included in it.
'''
from unittest import TestCase
from datetime import date
from unittest import TestCase

from billing.exc import RSIError
from billing.processing.state import UtilBill, Customer, Session, Charge,\
    Address, Register

class UtilBillTest(TestCase):

    def assert_error(self, c, error_message):
        '''Assert that the Charge 'c' has None for its quantity/rate/total
        and 'error_message' in its 'error' field.
        '''
        self.assertIsNone(c.quantity)
        self.assertIsNone(c.total)
        self.assertIsNotNone(c.error)
        self.assertEqual(error_message, c.error)

    def assert_charge_values(self, quantity, rate, c):
        '''Assert that the charge 'c' has the given quantity and rate,
        total = quantity * rate, and no error.
        '''
        self.assertEqual(quantity, c.quantity)
        self.assertEqual(rate, c.rate)
        self.assertEqual(quantity * rate, c.total)
        self.assertEqual(None, c.error)

    def test_compute(self):
        utilbill = UtilBill(Customer('someone', '98989', 0.3, 0.1,
                'nobody@example.com', 'FB Test Utility',
                'FB Test Rate Class', Address(), Address()),
                UtilBill.Complete, 'gas', 'utility', 'rate class',
                Address(), Address(), period_start=date(2000, 1, 1),
                period_end=date(2000, 2, 1))
        register = Register(utilbill, "ABCDEF description", 150, 'therms',
                "ABCDEF", False, "total", "REG_TOTAL", None, "GHIJKL")
        utilbill.registers = [register]
        charges = [
            dict(
                rsi_binding='CONSTANT',
                quantity='100',
                quantity_units='dollars',
                rate=0.4,
            ),
            dict(
                rsi_binding='LINEAR',
                quantity='REG_TOTAL.quantity * 3',
                quantity_units='therms',
                rate=0.1,
            ),
            dict(
                rsi_binding='LINEAR_PLUS_CONSTANT',
                quantity='REG_TOTAL.quantity * 2 + 10',
                quantity_units='therms',
                rate=0.1,
            ),
            dict(
                rsi_binding='BLOCK_1',
                quantity='min(100, REG_TOTAL.quantity)',
                quantity_units='therms',
                rate=0.3,
            ),
            dict(
                rsi_binding='BLOCK_2',
                quantity='min(200, max(0, REG_TOTAL.quantity - 100))',
                quantity_units='therms',
                rate=0.2,
            ),
            dict(
                rsi_binding='BLOCK_3',
                quantity='max(0, REG_TOTAL.quantity - 200)',
                quantity_units='therms',
                rate=0.1,
            ),
            dict(
                rsi_binding='REFERENCES_ANOTHER',
                # TODO also try "total" here
                quantity='REFERENCED_BY_ANOTHER.quantity + '
                         'REFERENCED_BY_ANOTHER.rate',
                quantity_units='therms',
                rate=1,
            ),
            dict(
                rsi_binding='NO_CHARGE_FOR_THIS_RSI',
                quantity='1',
                quantity_units='therms',
                rate=1,
            ),
            # this RSI has no charge associated with it, but is used to
            # provide identifiers in the formula of the "REFERENCES_ANOTHER"
            # RSI in 'uprs'
            dict(
                rsi_binding='REFERENCED_BY_ANOTHER',
                quantity='2',
                quantity_units='therms',
                rate=3,
            ),
            dict(
                rsi_binding='SYNTAX_ERROR',
                quantity='5 + ',
                quantity_units='therms',
                rate=1,
            ),
            dict(
                rsi_binding='DIV_BY_ZERO_ERROR',
                quantity='1 / 0',
                quantity_units='therms',
                rate=1,
            ),
            # shows that quantity formula error takes priority over rate
            # formula error
            dict(
                rsi_binding='UNKNOWN_IDENTIFIER',
                quantity='x * 2',
                quantity_units='therms',
                rate=1,
            ),
        ]
        utilbill.charges = [Charge(utilbill, "Insert description here", "",
                0.0, c['quantity_units'], c['rate'], c['rsi_binding'], 0.0,
                quantity_formula=c['quantity']) for c in charges]

        get = utilbill.get_charge_by_rsi_binding

        # 'raise_exception' argument validates that all charges were computed
        # without errors. if this argument is given, all the charges without
        # errors still be correct, and the exception raised only after computing
        # all the charges
        with self.assertRaises(RSIError):
            utilbill.compute_charges(raise_exception=True)
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(450, .1, get('LINEAR'))
        self.assert_charge_values(310, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(50, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_charge_values(2, 3, get('REFERENCED_BY_ANOTHER'))
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error: division by zero')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")

        # TODO enable when bug #76318266 is fixed
        # self.assertEqual(40 + 45 + 31 + 30 + 10 + 0 + 5 + 6,
        #         utilbill.total_charge())

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for
        # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate
        # structure.
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(450, 0.1, get('LINEAR'))
        self.assert_charge_values(310, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(50, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(get('SYNTAX_ERROR'), 'Syntax error')
        self.assert_error(get('DIV_BY_ZERO_ERROR'), 'Error: division by zero')

        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")

        # try a different quantity: 250 therms
        register.quantity = 250
        utilbill.compute_charges()
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(750, 0.1, get('LINEAR'))
        self.assert_charge_values(510, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(150, 0.2, get('BLOCK_2'))
        self.assert_charge_values(50, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(get('SYNTAX_ERROR'), 'Syntax error')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")

        # and another quantity: 0
        register.quantity = 0
        utilbill.compute_charges()
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(0, 0.1, get('LINEAR'))
        self.assert_charge_values(10, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(0, 0.3, get('BLOCK_1'))
        self.assert_charge_values(0, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(get('SYNTAX_ERROR'), 'Syntax error')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")


    def test_compute_charges_empty(self):
        '''Compute utility bill with no charges.
        '''
        customer = Customer('someone', '99999', 0.3, 0.1,
                'nobody@example.com', 'utility', 'rate class',
                Address(), Address())
        utilbill = UtilBill(customer, UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address())
        utilbill.compute_charges()
        self.assertEqual([], utilbill.charges)
        self.assertEqual(0, utilbill.get_total_charges())

    def test_compute_charges_independent(self):
        customer = Customer('someone', '99999', 0.3, 0.1,
                'nobody@example.com', 'utility', 'rate class',
                Address(), Address())
        utilbill = UtilBill(customer, UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address(),
                period_start=date(2000,1,1), period_end=date(2000,2,1))
        utilbill.registers = [Register(utilbill, '', 150,
                'kWh', '', False, "total", "REG_TOTAL", '', '')]
        utilbill.charges = [
            Charge(utilbill, '', '', 0, 'kWh', 1, 'A', 0,
                    quantity_formula='REG_TOTAL.quantity'),
            Charge(utilbill, '', '', 0, 'kWh', 3, 'B', 0,
                    quantity_formula='2'),
            # this has an error
            Charge(utilbill, '', '', 0, 'kWh', 0, 'C', 0,
                    quantity_formula='1/0'),
        ]
        Session().add(utilbill)
        utilbill.compute_charges()

        self.assert_charge_values(150, 1,
                utilbill.get_charge_by_rsi_binding('A'))
        self.assert_charge_values(2, 3,
                utilbill.get_charge_by_rsi_binding('B'))
        self.assert_error(utilbill.get_charge_by_rsi_binding('C'),
                'Error: division by zero')
        self.assertEqual(150 + 6, utilbill.get_total_charges())

    def test_compute_charges_with_cycle(self):
        '''Test computing charges whose dependencies form a cycle.
        All such charges should have errors.
        '''
        customer = Customer('someone', '99999', 0.3, 0.1,
                'nobody@example.com', 'utility', 'rate class',
                Address(), Address())
        utilbill = UtilBill(customer, UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address(),
                period_start=date(2000,1,1), period_end=date(2000,2,1))
        utilbill.charges = [
            # circular dependency between A and B: A depends on B's "quantity"
            # and B depends on A's "rate", which is not allowed even though
            # theoretically both could be computed.
            Charge(utilbill, '', '', 0, 'kWh', 0, 'A', 0,
                    quantity_formula='B.quantity'),
            Charge(utilbill, '', '', 0, 'kWh', 0, 'B', 0,
                    quantity_formula='A.rate'),
            # C depends on itself
            Charge(utilbill, '', '', 0, 'kWh', 0, 'C', 0,
                    quantity_formula='C.total'),
            # D depends on A, which has a circular dependency with B. it should
            # not be computable because A is not computable.
            Charge(utilbill, '', '', 0, 'kWh', 0, 'D', 0,
                    quantity_formula='A.total'),
            Charge(utilbill, '', '', 0, 'kWh', 3, 'E', 0,
                    quantity_formula='2'),
        ]
        Session().add(utilbill)
        utilbill.compute_charges()

        self.assert_error(utilbill.get_charge_by_rsi_binding('A'),
                "Error: name 'B' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('B'),
                "Error: name 'A' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('C'),
                "Error: name 'C' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('D'),
                "Error: name 'A' is not defined")
        self.assert_charge_values(2, 3, utilbill.get_charge_by_rsi_binding('E'))