'''Unit tests for the UtilBill class and other code that will eventually be
included in it.
'''
from datetime import date
from StringIO import StringIO

import dateutil
from bson import ObjectId

from billing.processing.exceptions import RSIError
from processing.session_contextmanager import DBSession
from billing.test import utils
from billing.processing.rate_structure2 import RateStructure, RateStructureItem
from billing.processing import mongo
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.exceptions import NoRSIError
import example_data
from processing.state import UtilBill, Customer, Session, Charge


class UtilBillTest(TestCaseWithSetup, utils.TestCase):

    def test_compute(self):
        utilbill_doc = {
            'account': '12345', 'service': 'gas', 'utility': 'utility',
            'start': date(2000,1,1), 'end': date(2000,2,1),
            'rate_class': "rate class",
            'charges': [
                {'rsi_binding': 'CONSTANT', 'quantity': 0,
                        'group': 'All Charges'},
                {'rsi_binding': 'LINEAR', 'quantity': 0,
                        'group': 'All Charges'},
                {'rsi_binding': 'LINEAR_PLUS_CONSTANT', 'quantity': 0,
                        'group': 'All Charges'},
                {'rsi_binding': 'BLOCK_1', 'quantity': 0,
                        'group': 'All Charges'},
                {'rsi_binding': 'BLOCK_2', 'quantity': 0,
                        'group': 'All Charges'},
                {'rsi_binding': 'BLOCK_3', 'quantity': 0,
                        'group': 'All Charges'},
                {'rsi_binding': 'REFERENCES_ANOTHER', 'quantity': 0,
                        'group': 'All Charges'},
            ],
            'meters': [{
                'present_read_date': date(2000,2,1),
                'prior_read_date': date(2000,1,1),
                'identifier': 'ABCDEF',
                'registers': [{
                    'identifier': 'GHIJKL',
                    'register_binding': 'REG_TOTAL',
                    'quantity': 150,
                    'quantity_units': 'therms',
                }]
            }],
            'billing_address': {}, # addresses are irrelevant
            'service_address': {},
        }

        # rate structure document containing some common RSI types
        uprs = RateStructure(
            id=ObjectId(),
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
                )
            ]
        )
        session = Session()
        utilbill = UtilBill(Customer('someone', '99999', 0.3, 0.1, None,
                'nobody@example.com'), UtilBill.Complete,
                'gas', 'utility', 'rate class')
        session.add(utilbill)
        utilbill.refresh_charges(uprs.rates)
        utilbill.compute_charges(uprs, utilbill_doc)

        # function to get the "total" value of a charge from its name
        def the_charge_named(rsi_binding):
            return next(c.total for c in utilbill.charges
                    if c.rsi_binding == rsi_binding)

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate # structure. self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT')) self.assertDecimalAlmostEqual(45, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(31,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(10, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))

        # try a different quantity: 250 therms
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 250
        utilbill.compute_charges(uprs, utilbill_doc)
        self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(75, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(51,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(5, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))

        # and another quantity: 0
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 0
        utilbill.compute_charges(uprs, utilbill_doc)
        self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(1,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))

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

