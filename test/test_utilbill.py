'''Unit tests for the UtilBill class and other code that will eventually be
included in it.
'''
from billing.test.setup_teardown import init_logging, TestCaseWithSetup
init_logging()
from billing import init_config, init_model
from datetime import date
from StringIO import StringIO

import dateutil
from bson import ObjectId

from billing.exc import RSIError
from processing.session_contextmanager import DBSession
from billing.test import utils
#from billing.processing.rate_structure2 import RateStructure, RateStructureItem
from billing.processing import mongo
from billing.test.setup_teardown import TestCaseWithSetup
from billing.exc import NoRSIError
import example_data
from billing.processing.state import UtilBill, Customer, Session, Charge, Address, \
    Register

class UtilBillTest(TestCaseWithSetup):

    def setUp(self):
        init_config('tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables(self.session)


    def test_compute(self):

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
                            Address(), Address(), period_start=date(2000,1,1),
                            period_end=date(2000,2,1))
        session.add(utilbill)
        session.flush()
        register = Register(utilbill, "ABCDEF description", 150, 'therms',
                 "ABCDEF", False, "total", "REG_TOTAL", None, "GHIJKL")
        session.add(register)

        for rdct in rates:
            print rdct, type(rdct)
            session.add(Charge(utilbill, "Insert description here", "",
                               0.0, rdct['quantity_units'], 0.0,
                               rdct['rsi_binding'], 0.0,
                               rate_formula=rdct['rate'],
                               quantity_formula=rdct['quantity']))
        session.flush()
        utilbill.compute_charges()

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

        # 'raise_exception' argument validates that all charges were computed
        # without errors. if this argument is given, all the charges without
        # errors still be correct, and the exception raised only after computing
        # all the charges
        with self.assertRaises(RSIError):
            utilbill.compute_charges(raise_exception=True)
        self.assertDecimalAlmostEqual(31,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(10, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        assert_error(utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        assert_error(utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        assert_error(utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate # structure. self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT')) self.assertDecimalAlmostEqual(45, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(31,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(10, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        assert_error(utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        assert_error(utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        assert_error(utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

        # try a different quantity: 250 therms
        charge = session.query(Charge).filter_by(utilbill=utilbill).\
            filter_by(rsi_binding="CONSTANT").one()
        charge.quantity_formula = '250'
        utilbill.compute_charges()
        self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(75, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(51,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(5, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        assert_error(utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        assert_error(utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        assert_error(utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")

        # and another quantity: 0
        charge.quantity_formula = '0'
        utilbill.compute_charges()
        self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(1,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        assert_error(utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error in quantity formula')
        assert_error(utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error in rate formula: division by zero')
        assert_error(utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error in quantity formula: name 'x' is not defined")


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

