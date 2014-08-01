'''Unit tests for the UtilBill class and other code that will eventually be
included in it.
'''
from datetime import date

from billing.exc import RSIError
from billing.test import utils
from billing.processing.rate_structure2 import RateStructure, RateStructureItem
from billing.processing import mongo
from billing.test.setup_teardown import TestCaseWithSetup
from processing.state import UtilBill, Customer, Session, Address


class UtilBillTest(TestCaseWithSetup, utils.TestCase):

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

    def test_compute(self):
        '''Test computing a variety of charges (including charges with
        formula errors) with different register quantities as input.
        '''
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

        # rate structure document containing some common RSI types
        uprs = RateStructure(
            rates=[
                RateStructureItem(
                    rsi_binding='CONSTANT',
                    quantity='100',
                    quantity_units='dollars',
                    rate='0.4',
                ),
                RateStructureItem(
                  rsi_binding='LINEAR',
                  quantity='REG_TOTAL.quantity * 3',
                  quantity_units='therms',
                  rate='0.1',
                ),
                RateStructureItem(
                  rsi_binding='LINEAR_PLUS_CONSTANT',
                  quantity='REG_TOTAL.quantity * 2 + 10',
                  quantity_units='therms',
                  rate='0.1',
                ),
                RateStructureItem(
                  rsi_binding='BLOCK_1',
                  quantity='min(100, REG_TOTAL.quantity)',
                  quantity_units='therms',
                  rate='0.3',
                ),
                RateStructureItem(
                  rsi_binding='BLOCK_2',
                  quantity='min(200, max(0, REG_TOTAL.quantity - 100))',
                  quantity_units='therms',
                  rate='0.2',
                ),
                RateStructureItem(
                  rsi_binding='BLOCK_3',
                  quantity='max(0, REG_TOTAL.quantity - 200)',
                  quantity_units='therms',
                  rate='0.1',
                ),
                RateStructureItem(
                    rsi_binding='REFERENCES_ANOTHER',
                    # TODO also try "total" here
                    quantity='REFERENCED_BY_ANOTHER.quantity + '
                             'REFERENCED_BY_ANOTHER.rate',
                    quantity_units='therms',
                    rate='1',
                ),
                RateStructureItem(
                  rsi_binding='NO_CHARGE_FOR_THIS_RSI',
                  quantity='1',
                  quantity_units='therms',
                  rate='1',
                ),
                # this RSI has no charge associated with it, but is used to
                # provide identifiers in the formula of the "REFERENCES_ANOTHER"
                # RSI in 'uprs'
                RateStructureItem(
                    rsi_binding='REFERENCED_BY_ANOTHER',
                    quantity='2',
                    quantity_units='therms',
                    rate='3',
                ),
                RateStructureItem(
                    rsi_binding='SYNTAX_ERROR',
                    quantity='5 + ',
                    quantity_units='therms',
                    rate='1',
                ),
                RateStructureItem(
                    rsi_binding='DIV_BY_ZERO_ERROR',
                    quantity='1',
                    quantity_units='therms',
                    rate='1 / 0',
                ),
                # shows that quantity formula error takes priority over rate
                # formula error
                RateStructureItem(
                    rsi_binding='UNKNOWN_IDENTIFIER',
                    quantity='x * 2',
                    quantity_units='therms',
                    rate='1 / 0',
                ),
            ]
        )
        utilbill = UtilBill(Customer('someone', '99999', 0.3, 0.1, None,
                'nobody@example.com'), UtilBill.Complete,
                'gas', 'utility', 'rate class', Address(), Address())
        Session().add(utilbill)
        utilbill.refresh_charges(uprs.rates)
        utilbill.compute_charges(uprs, utilbill_doc)

        get = utilbill.get_charge_by_rsi_binding

        # 'raise_exception' argument validates that all charges were computed
        # without errors. if this argument is given, all the charges without
        # errors still be correct, and the exception raised only after computing
        # all the charges
        with self.assertRaises(RSIError):
            utilbill.compute_charges(uprs, utilbill_doc, raise_exception=True)
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(310, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(50, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

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
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 250
        utilbill.compute_charges(uprs, utilbill_doc)
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
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 0
        utilbill.compute_charges(uprs, utilbill_doc)
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


    def test_compute_charges_with_cycle(self):
        '''Test computing charges whose dependencies form a cycle.
        All such charges should have errors.
        '''
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

    def test_register_editing(self):
        '''So far, regression test for bug 59517110 in which it was possible to
        create registers with the same identifier. Should be expanded to test
        all aspects of editing meter/register data.
        '''
        # utility bill with empty "meters" list
        utilbill_doc = {
            'account': '12345', 'service': 'gas', 'utility': 'washgas',
            'start': date(2000,1,1), 'end': date(2000,2,1),
            'rate_class': "won't be loaded from the db anyway",
            'charges': [
                {'rsi_binding': 'LINEAR', 'quantity': 0, 'group': 'All '
                                                                  'Charges'},
            ],
            'meters': [],
            'billing_address': {}, # addresses are irrelevant
            'service_address': {},
        }
        
        # add a register; check default values of fields
        mongo.new_register(utilbill_doc)
        self.assertEquals([{
            'prior_read_date': date(2000,1,1),
            'present_read_date': date(2000,2,1),
            'identifier': 'Insert meter ID here',
            'registers': [{
                'identifier': 'Insert register ID here',
                'register_binding': 'Insert register binding here',
                'quantity': 0,
                'quantity_units': 'therms',
                'type': 'total',
                'description': 'Insert description',
            }],
        }], utilbill_doc['meters'])

        # update meter ID
        new_meter_id, new_reg_id = mongo.update_register(
                utilbill_doc, 'Insert meter ID here',
                'Insert register ID here', meter_id='METER')
        self.assertEqual('METER', new_meter_id)
        self.assertEqual('Insert register ID here', new_reg_id)
        self.assertEqual([{
            'prior_read_date': date(2000,1,1),
            'present_read_date': date(2000,2,1),
            'identifier': 'METER',
            'registers': [{
                'identifier': 'Insert register ID here',
                'register_binding': 'Insert register binding here',
                'quantity': 0,
                'quantity_units': 'therms',
                'type': 'total',
                'description': 'Insert description',
            }],
        }], utilbill_doc['meters'])

        # update register ID
        new_meter_id, new_reg_id = mongo.update_register(
                utilbill_doc, 'METER', 'Insert register ID here',
                register_id='REGISTER')
        self.assertEqual('METER', new_meter_id)
        self.assertEqual('REGISTER', new_reg_id)
        self.assertEqual([{
            'prior_read_date': date(2000,1,1),
            'present_read_date': date(2000,2,1),
            'identifier': 'METER',
            'registers': [{
                'identifier': 'REGISTER',
                'register_binding': 'Insert register binding here',
                'quantity': 0,
                'quantity_units': 'therms',
                'type': 'total',
                'description': 'Insert description',
            }],
        }], utilbill_doc['meters'])

        # create new register with default values; since its meter ID is
        # different, there are 2 meters
        mongo.new_register(utilbill_doc)
        self.assertEquals([
            {
                'prior_read_date': date(2000,1,1),
                'present_read_date': date(2000,2,1),
                'identifier': 'METER',
                'registers': [{
                    'identifier': 'REGISTER',
                    'register_binding': 'Insert register binding here',
                    'quantity': 0,
                    'quantity_units': 'therms',
                    'type': 'total',
                    'description': 'Insert description',
                }],
            },
            {
                'prior_read_date': date(2000,1,1),
                'present_read_date': date(2000,2,1),
                'identifier': 'Insert meter ID here',
                'registers': [{
                    'identifier': 'Insert register ID here',
                    'register_binding': 'Insert register binding here',
                    'quantity': 0,
                    'quantity_units': 'therms',
                    'type': 'total',
                    'description': 'Insert description',
                }],
            },
        ], utilbill_doc['meters'])

        # update meter ID of 2nd register so both registers are inside the same
        # meter
        new_meter_id, new_reg_id = mongo.update_register(
                utilbill_doc, 'Insert meter ID here',
                'Insert register ID here', meter_id='METER')
        self.assertEqual('METER', new_meter_id)
        self.assertEqual('Insert register ID here', new_reg_id)
        self.assertEqual([{
            'prior_read_date': date(2000,1,1),
            'present_read_date': date(2000,2,1),
            'identifier': 'METER',
            'registers': [
                {
                    'identifier': 'REGISTER',
                    'register_binding': 'Insert register binding here',
                    'quantity': 0,
                    'quantity_units': 'therms',
                    'type': 'total',
                    'description': 'Insert description',
                },{
                    'identifier': 'Insert register ID here',
                    'register_binding': 'Insert register binding here',
                    'quantity': 0,
                    'quantity_units': 'therms',
                    'type': 'total',
                    'description': 'Insert description',
                },
            ],
        }], utilbill_doc['meters'])

        # can't set both meter ID and register ID the same as another register
        self.assertRaises(ValueError, mongo.update_register, utilbill_doc,
                'METER', 'Insert register ID here', register_id='REGISTER')

        # update "quantity" of register
        mongo.update_register(utilbill_doc, 'METER', 'REGISTER',
                quantity=123.45)
        self.assertEqual([{
            'prior_read_date': date(2000,1,1),
            'present_read_date': date(2000,2,1),
            'identifier': 'METER',
            'registers': [
                {
                    'identifier': 'REGISTER',
                    'register_binding': 'Insert register binding here',
                    'quantity': 123.45,
                    'quantity_units': 'therms',
                    'type': 'total',
                    'description': 'Insert description',
                },{
                    'identifier': 'Insert register ID here',
                    'register_binding': 'Insert register binding here',
                    'quantity': 0,
                    'quantity_units': 'therms',
                    'type': 'total',
                    'description': 'Insert description',
                },
            ],
        }], utilbill_doc['meters'])

