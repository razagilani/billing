'''Unit tests for the UtilBill class and other code that will eventually be
included in it.
'''
from billing.test.setup_teardown import init_logging, TestCaseWithSetup
init_logging()
from billing import init_config, init_model
from datetime import date
from billing.exc import RSIError
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.state import UtilBill, Customer, Session, Charge, Address, \
    Register

class UtilBillTest(TestCaseWithSetup):

    def setUp(self):
        init_config('tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables(self.session)

    
    # function to check error state of a charge
    def assert_error(self, c, error_message):
        '''Assert that the Charge 'c' has None for its quantity/rate/total
        and 'error_message' in its 'error' field.
        '''
        self.assertIsNone(c.quantity)
        self.assertIsNone(c.rate)
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


    def insert_test_data(self):
        rates = [
            dict(
                rsi_binding='CONSTANT',
                quantity='100',
                quantity_units='dollars',
                rate='0.4',
            ),
            dict(
              rsi_binding='LINEAR',
              quantity='REG_TOTAL.quantity * 3',
              quantity_units='therms',
              rate='0.1',
            ),
            dict(
              rsi_binding='LINEAR_PLUS_CONSTANT',
              quantity='REG_TOTAL.quantity * 2 + 10',
              quantity_units='therms',
              rate='0.1',
            ),
            dict(
              rsi_binding='BLOCK_1',
              quantity='min(100, REG_TOTAL.quantity)',
              quantity_units='therms',
              rate='0.3',
            ),
            dict(
              rsi_binding='BLOCK_2',
              quantity='min(200, max(0, REG_TOTAL.quantity - 100))',
              quantity_units='therms',
              rate='0.2',
            ),
            dict(
              rsi_binding='BLOCK_3',
              quantity='max(0, REG_TOTAL.quantity - 200)',
              quantity_units='therms',
              rate='0.1',
            ),
            dict(
                rsi_binding='REFERENCES_ANOTHER',
                # TODO also try "total" here
                quantity='REFERENCED_BY_ANOTHER.quantity + '
                         'REFERENCED_BY_ANOTHER.rate',
                quantity_units='therms',
                rate='1',
            ),
            dict(
              rsi_binding='NO_CHARGE_FOR_THIS_RSI',
              quantity='1',
              quantity_units='therms',
              rate='1',
            ),
            # this RSI has no charge associated with it, but is used to
            # provide identifiers in the formula of the "REFERENCES_ANOTHER"
            # RSI in 'uprs'
            dict(
                rsi_binding='REFERENCED_BY_ANOTHER',
                quantity='2',
                quantity_units='therms',
                rate='3',
            ),
            dict(
                rsi_binding='SYNTAX_ERROR',
                quantity='5 + ',
                quantity_units='therms',
                rate='1',
            ),
            dict(
                rsi_binding='DIV_BY_ZERO_ERROR',
                quantity='1',
                quantity_units='therms',
                rate='1 / 0',
            ),
            # shows that quantity formula error takes priority over rate
            # formula error
            dict(
                rsi_binding='UNKNOWN_IDENTIFIER',
                quantity='x * 2',
                quantity_units='therms',
                rate='1 / 0',
            ),
        ]
        session = Session()
        utilbill = UtilBill(Customer('someone', '98989', 0.3, 0.1,
                                     'nobody@example.com', 'FB Test Utility',
                                     'FB Test Rate Class', Address(), Address()),
                            UtilBill.Complete, 'gas', 'utility', 'rate class',
                            Address(), Address(), period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        session.add(utilbill)
        session.flush()
        register = Register(utilbill, "ABCDEF description", 150, 'therms',
                 "ABCDEF", False, "total", "REG_TOTAL", None, "GHIJKL")
        session.add(register)

        for rdct in rates:
            session.add(Charge(utilbill, "Insert description here", "",
                               0.0, rdct['quantity_units'], 0.0,
                               rdct['rsi_binding'], 0.0,
                               rate_formula=rdct['rate'],
                               quantity_formula=rdct['quantity']))
        session.flush()
        utilbill.compute_charges()
        return utilbill, register

    def test_compute(self):
        utilbill, register = self.insert_test_data()
        # function to get the "total" value of a charge from its name
        def the_charge_named(rsi_binding):
            return next(c.total for c in utilbill.charges
                    if c.rsi_binding == rsi_binding)

        # function to check error state of a charge
        def assert_error(c, error_message):
            self.assertIsNone(c.quantity)
            self.assertIsNone(c.rate)
            self.assertIsNone(c.total)
            self.assertIsNotNone(c.error)
            self.assertEqual(error_message, c.error)

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
                'Syntax error in quantity formula')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

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
        self.assert_error(get('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

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
        self.assert_error(get('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

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
        self.assert_error(get('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")


    def test_compute_charges_empty(self):
        '''Compute utility bill with no charges.
        '''
        # irrelevant fields are omitted from this document
        utilbill_doc = {
            'charges': [],
            'meters': [],
        }
        utilbill = UtilBill(Customer('someone', '99999', 0.3, 0.1, None,
                'nobody@example.com'), UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address())
        utilbill.compute_charges(RateStructure(rates=[]), utilbill_doc)
        self.assertEqual([], utilbill.charges)
        self.assertEqual(0, utilbill.total_charge())

    def test_compute_charges_independent(self):
        # irrelevant fields are omitted from this document
        utilbill_doc = {
            'charges': [],
            'meters': [{
                'registers': [{
                    'register_binding': 'REG_TOTAL',
                    'quantity': 150,
                }]
            }],
        }

        rs = RateStructure(rates=[
            # circular dependency between A and B: A depends on B's "quantity"
            # and B depends on A's "rate", which is not allowed even though
            # theoretically both could be computed.
            RateStructureItem(
                rsi_binding='A',
                quantity='REG_TOTAL.quantity',
                quantity_units='kWh',
                rate='1',
            ),
            RateStructureItem(
                rsi_binding='B',
                quantity='2',
                quantity_units='kWh',
                rate='3',
            ),
            # this has an error
            RateStructureItem(
                rsi_binding='C',
                quantity='1/0',
                quantity_units='kWh',
                rate='x + y',
            ),
        ])
        utilbill = UtilBill(Customer('someone', '99999', 0.3, 0.1, None,
                'nobody@example.com'), UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address())
        Session().add(utilbill)
        utilbill.refresh_charges(rs.rates)
        utilbill.compute_charges(rs, utilbill_doc)

        self.assert_charge_values(150, 1,
                utilbill.get_charge_by_rsi_binding('A'))
        self.assert_charge_values(2, 3,
                utilbill.get_charge_by_rsi_binding('B'))
        self.assert_error(utilbill.get_charge_by_rsi_binding('C'),
                'Error in quantity formula: division by zero')
        self.assertEqual(150 + 6, utilbill.total_charge())

    def test_compute_charges_with_cycle(self):
        '''Test computing charges whose dependencies form a cycle.
        All such charges should have errors.
        '''
        # irrelevant fields are omitted from this document
        utilbill_doc = {
            'charges': [],
            'meters': [],
        }

        rs = RateStructure(rates=[
            # circular dependency between A and B: A depends on B's "quantity"
            # and B depends on A's "rate", which is not allowed even though
            # theoretically both could be computed.
            RateStructureItem(
                rsi_binding='A',
                quantity='B.quantity',
                quantity_units='kWh',
                rate='0',
            ),
            RateStructureItem(
                rsi_binding='B',
                quantity='0',
                quantity_units='kWh',
                rate='A.rate',
            ),
            # C depends on itself
            RateStructureItem(
                rsi_binding='C',
                quantity='C.total',
                quantity_units='kWh',
                rate='0',
            ),
            # D depends on A, which has a circular dependency with B. it should
            # not be computable because A is not computable.
            RateStructureItem(
                rsi_binding='D',
                quantity='A.total',
                quantity_units='kWh',
                rate='0',
            ),
        ])
        utilbill = UtilBill(Customer('someone', '99999', 0.3, 0.1, None,
                'nobody@example.com'), UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address())
        Session().add(utilbill)
        utilbill.refresh_charges(rs.rates)
        utilbill.compute_charges(rs, utilbill_doc)

        self.assert_error(utilbill.get_charge_by_rsi_binding('A'),
                "Error in quantity formula: name 'B' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('B'),
                "Error in rate formula: name 'A' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('C'),
                "Error in quantity formula: name 'C' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('D'),
            "Error in quantity formula: name 'A' is not defined")