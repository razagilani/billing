'''Unit tests for the UtilBill class and other code that will eventually be
included in it.
'''
from test import init_test_config
init_test_config()
from billing import init_model

from datetime import date
from unittest import TestCase

from billing.exc import RSIError, ProcessedBillError
from billing.core.model import UtilBill, Session, Charge,\
    Address, Register, Utility, Supplier, RateClass, UtilityAccount
from billing.reebill.state import Payment, ReeBillCustomer

class UtilBillTest(TestCase):

    def setUp(self):
        init_model()
        session = Session()
        session.query(Register).delete()
        session.query(UtilBill).delete()
        session.query(Payment).delete()
        session.query(ReeBillCustomer).delete()
        session.query(UtilityAccount).delete()

        self.utility = Utility('utility', Address())
        self.supplier = Supplier('supplier', Address())
        self.utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass('FB Test Rate Class', self.utility), Address(), Address())
        self.rate_class = RateClass('rate class', self.utility)

    def tearDown(self):
        Session.remove()

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

    def test_validate_utilbill_period(self):
        # valid periods
        UtilBill.validate_utilbill_period(None, None)
        UtilBill.validate_utilbill_period(date(1000,1,1), None)
        UtilBill.validate_utilbill_period(None, date(1000,1,1))
        UtilBill.validate_utilbill_period(date(2000,1,1), date(2000,1,2))
        UtilBill.validate_utilbill_period(date(2000,1,1), date(2000,12,31))

        # length < 1 day
        with self.assertRaises(ValueError):
            UtilBill.validate_utilbill_period(date(2000,1,1), date(2000,1,1))
        with self.assertRaises(ValueError):
            UtilBill.validate_utilbill_period(date(2000,1,2), date(2000,1,1))

        # length > 365 days
        with self.assertRaises(ValueError):
            UtilBill.validate_utilbill_period(date(2000,1,1), date(2001,1,2))

    def test_processed_editable(self):
        utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass('FB Test Rate Class', self.utility), Address(), Address())
        utilbill = UtilBill(utility_account, UtilBill.Complete, 'gas',
                            self.utility, self.supplier,
                            RateClass('rate class', self.utility), Address(),
                            Address(), period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))

        self.assertFalse(utilbill.processed)
        utilbill.check_editable()

        utilbill.processed = True
        self.assertTrue(utilbill.processed)
        self.assertRaises(ProcessedBillError, utilbill.check_editable)

    def test_add_charge(self):
        utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass('FB Test Rate Class', self.utility), Address(), Address())
        utilbill = UtilBill(utility_account, UtilBill.Complete, 'gas',
                            self.utility, self.supplier,
                            RateClass('rate class', self.utility), Address(),
                            Address(), period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))

        session = Session()
        session.add(utilbill)
        session.flush()

        self.assertEqual(utilbill.registers, [])

        charge = utilbill.add_charge()
        self.assertEqual(charge.quantity_formula, '', "The quantity formula"
                " should be an empty string when no registers are present")

        session.delete(charge)

        utilbill.registers = [Register(utilbill, "ABCDEF description",
            "ABCDEF", 'therms', False, 'total', None, "ABCDEF", quantity=150,
            register_binding='REG_TOTAL'),
                              Register(utilbill, "ABCDEF description",
            "ABCDEF", 'therms', False, "total", None, "GHIJKL",
            quantity=150, register_binding='SOME_OTHER_BINDING')]

        charge = utilbill.add_charge()
        self.assertEqual(charge.quantity_formula, "REG_TOTAL.quantity", "The "
         " quantity formula should be 'REG_TOTAL.quantity' when at least one "
         " register has a register_binding named 'REG_TOTAL'.")
        session.delete(charge)

        for register in utilbill.registers:
            session.delete(register)

        utilbill.registers = [Register(utilbill, "ABCDEF description",
            "ABCDEF", 'therms', False, "total", None, "GHIJKL", quantity=150,
            register_binding='SOME_OTHER_BINDING')]
        charge = utilbill.add_charge()
        self.assertEqual(charge.quantity_formula, "SOME_OTHER_BINDING", "The "
            " quantity formula should be 'SOME_OTHER_BINDING' when no registers"
            " have a register binding named 'REG_TOTAL'")

    def test_compute(self):
        fb_utility = Utility('FB Test Utility', Address())
        utility = Utility('utility', Address())
        utilbill = UtilBill(UtilityAccount('someone', '98989',
                fb_utility, 'FB Test Supplier',
                RateClass('FB Test Rate Class', fb_utility),
                Address(), Address()), UtilBill.Complete, 'gas',
                utility, Supplier('supplier', Address()),
                RateClass('rate class', utility),
                Address(), Address(), period_start=date(2000, 1, 1),
                period_end=date(2000, 2, 1))
        register = Register(utilbill, "ABCDEF description",
                "ABCDEF", 'therms', False, "total", None, "GHIJKL",
                quantity=150,
                register_binding='REG_TOTAL')
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
        utilbill.charges = [Charge(utilbill, c['rsi_binding'], c['rate'],
                c['quantity'], "Insert description here", "",
                unit=c['quantity_units']) for c in charges]

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
        utility_account = UtilityAccount('someone', '99999',
                'utility', 'supplier',
                'rate class', Address(), Address())
        utilbill = UtilBill(utility_account, UtilBill.Complete,
                'gas', 'utility', 'supplier', 'rate class',
                Address(), Address())
        utilbill.compute_charges()
        self.assertEqual([], utilbill.charges)
        self.assertEqual(0, utilbill.get_total_charges())

    def test_compute_charges_independent(self):
        utility = Utility('utility', Address())
        supplier = Supplier('supplier', Address())
        utility_account = UtilityAccount('someone', '99999',
                utility, supplier,
                RateClass('rate class', utility), Address(),
                Address())
        utilbill = UtilBill(utility_account, UtilBill.Complete,
                'gas', utility, supplier, RateClass('rate class', utility),
                Address(), Address(), period_start=date(2000,1,1),
                period_end=date(2000,2,1))
        utilbill.registers = [Register(utilbill, '',
                '', 'kWh', False, "total", '', '',
                quantity=150,
                register_binding='REG_TOTAL')]
        utilbill.charges = [
            Charge(utilbill, 'A', 1, 'REG_TOTAL.quantity',
                   '', '', 'kWh'),
            Charge(utilbill, 'B', 3, '2', '', '', 'kWh'),
            # this has an error
            Charge(utilbill, 'C', 0, '1/0', '', '', 'kWh'),
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
        utility = Utility('utility', Address())
        supplier = Supplier('supplier', Address())
        utility_account = UtilityAccount('someone', '99999',
                utility, supplier,
                RateClass('rate class', utility), Address(),
                Address())
        utilbill = UtilBill(utility_account, UtilBill.Complete,
                'gas', utility, supplier, RateClass('rate class', utility)
                , Address(), Address(), period_start=date(2000,1,1),
                period_end=date(2000,2,1))
        utilbill.charges = [
            # circular dependency between A and B: A depends on B's "quantity"
            # and B depends on A's "rate", which is not allowed even though
            # theoretically both could be computed.
            Charge(utilbill, 'A', 0, 'B.quantity', '', '', 'kWh'),
            Charge(utilbill, 'B', 0, 'A.rate', '', '', 'kWh'),
            # C depends on itself
            Charge(utilbill, 'C', 0, 'C.total', '', '', 'kWh'),
            # D depends on A, which has a circular dependency with B. it should
            # not be computable because A is not computable.
            Charge(utilbill, 'D', 0, 'A.total', '', '', 'kWh'),
            Charge(utilbill, 'E', 3, '2', '', '', 'kWh'),
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

    def test_processed_utility_bills(self):
        '''
        test for making sure processed bills cannot be edited
        '''
        utility = Utility('utility', Address())
        supplier = Supplier('supplier', Address())
        utility_account = UtilityAccount('someone', '99999',
                utility, supplier,
                RateClass('rate class', utility), Address(),
                Address())
        utilbill = UtilBill(utility_account, UtilBill.Complete,
                'gas', utility, supplier, RateClass('rate class', utility),
                Address(), Address(), period_start=date(2000,1,1),
                period_end=date(2000,2,1))
        utilbill.registers = [Register(utilbill, '',
                '', 'kWh', False, "total", '', '',
                quantity=150,
                register_binding='REG_TOTAL')]
        utilbill.charges = [
            Charge(utilbill, 'A', 1, 'REG_TOTAL.quantity', '', '', 'kWh'),
            Charge(utilbill, 'B', 3, '2', '', '', 'kWh'),
            # this has an error
            Charge(utilbill, 'C', 0, '1/0', '', '', 'kWh'),
        ]
        self.assertTrue(utilbill.editable())
        Session().add(utilbill)
        utilbill.processed = True
        self.assertRaises(ProcessedBillError, utilbill.compute_charges())
        self.assertFalse(utilbill.editable())

    def test_date_modified(self):
        # TODO BILL-5878
        raise NotImplementedError

    def test_get_total_energy_consumption(self):
        utilbill = UtilBill(self.utility_account, UtilBill.Complete,
                            'gas', self.utility, self.supplier, self.rate_class,
                            Address(), Address(), period_start=date(2000,1,1),
                            period_end=date(2000,2,1))
        utilbill.registers = [
            Register(utilbill, '', '', 'therms', False, '', '', '',
                     register_binding='X', quantity=1),
            Register(utilbill, '', '', 'kWh', False, '', '', '',
                     register_binding='REG_TOTAL', quantity=2),
        ]
        self.assertEqual(2, utilbill.get_total_energy_consumption())

    def test_charge_types(self):
        utilbill = UtilBill(self.utility_account, UtilBill.Complete,
                            'gas', self.utility, self.supplier, self.rate_class,
                            Address(), Address(), period_start=date(2000,1,1),
                            period_end=date(2000,2,1))
        the_charges = [
            Charge(utilbill, 'A', 1, '1', type='distribution'),
            # a Charge does not count as a real charge if has_charge=False.
            Charge(utilbill, 'B', 1, '3', type='supply', has_charge=False),
            Charge(utilbill, 'C', 1, '5', type='supply'),
            Charge(utilbill, 'D', 1, 'syntax error', type='supply'),
            Charge(utilbill, 'E', 1, '7', type='other'),
        ]
        utilbill.charges = the_charges
        self.assertEqual(the_charges, utilbill.charges)

        # supply charge with a syntax error counts as one of the "supply
        # charges"
        self.assertEqual(the_charges[2:4], utilbill.get_supply_charges())

        # but it does not count toward the "supply total"
        utilbill.compute_charges()
        self.assertEqual(5, utilbill.get_supply_total())

        # TODO: test methods that use other charge types (distribution,
        # other) here when they are added.


