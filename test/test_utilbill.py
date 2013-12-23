'''Unit tests for what will be the class wrapping a utility bill
document, when there finally is one.
'''
from datetime import date
from bson import ObjectId
from decimal import Decimal
from unittest import TestCase
from billing.test import example_data
from billing.test import utils
from billing.processing.rate_structure2 import RateStructure, Register, RateStructureItem
from billing.processing import mongo
import example_data

class UtilBillTest(utils.TestCase):

    def test_compute(self):
        # make a utility bill document from scratch to ensure full control over
        # its contents
        utilbill_doc = {
            'account': '12345', 'service': 'gas', 'utility': 'washgas',
            'start': date(2000,1,1), 'end': date(2000,2,1),
            'rate_class': "won't be loaded from the db anyway",
            'chargegroups': {'All Charges': [
                {'rsi_binding': 'CONSTANT', 'quantity': 0},
                {'rsi_binding': 'LINEAR', 'quantity': 0},
                {'rsi_binding': 'LINEAR_PLUS_CONSTANT', 'quantity': 0},
                {'rsi_binding': 'BLOCK_1', 'quantity': 0},
                {'rsi_binding': 'BLOCK_2', 'quantity': 0},
                {'rsi_binding': 'BLOCK_3', 'quantity': 0},
            ]},
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
            type='UPRS',
            registers=[Register(
                register_binding='REG_TOTAL',
                # this object is not actually a "register", so
                # quantity/units here don't matter at all
                quantity='-1',
                quantity_units='who cares',
            )],
            rates=[
                RateStructureItem(
                  rsi_binding='CONSTANT',
                  quantity='50',
                  quantity_units='dollars',
                  #rate_units='dollars',
                  rate='0.2',
                ),
                RateStructureItem(
                  rsi_binding='LINEAR',
                  quantity='REG_TOTAL.quantity * 3',
                  quantity_units='therms',
                  rate='0.1',
                  #rate_units='dollars',
                ),
                RateStructureItem(
                  rsi_binding='LINEAR_PLUS_CONSTANT',
                  quantity='REG_TOTAL.quantity * 2 + 10',
                  quantity_units='therms',
                  #rate_units='dollars',
                  rate='0.1',
                ),
                RateStructureItem(
                  rsi_binding='BLOCK_1',
                  quantity='min(100, REG_TOTAL.quantity)',
                  quantity_units='therms',
                  rate='0.3',
                  #rate_units='dollars',
                ),
                RateStructureItem(
                  rsi_binding='BLOCK_2',
                  quantity='min(200, max(0, REG_TOTAL.quantity - 100))',
                  quantity_units='therms',
                  rate='0.2',
                  #rate_units='dollars',
                ),
                RateStructureItem(
                  rsi_binding='BLOCK_3',
                  quantity='max(0, REG_TOTAL.quantity - 200)',
                  quantity_units='therms',
                  rate='0.1',
                  #rate_units='dollars',
                ),
                RateStructureItem(
                  rsi_binding='NO_CHARGE_FOR_THIS_RSI',
                  quantity='1',
                  quantity_units='therms',
                  rate='1',
                  #rate_units='dollars',
                ),
            ]
        )

        # TODO test overriding CPRS in UPRS
        cprs = RateStructure(
            id=ObjectId(),
            type='CPRS',
            registers=[],
            rates=[],
        )

        mongo.compute_all_charges(utilbill_doc, uprs, cprs)

        # function to get the "total" value of a charge from its name
        def the_charge_named(rsi_binding):
            return next(c['total'] for c in
                    utilbill_doc['chargegroups']['All Charges']
                    if c['rsi_binding'] == rsi_binding)

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for
        # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate
        # structure.
        self.assertDecimalAlmostEqual(10, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(45, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(31,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(10, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertRaises(StopIteration, the_charge_named,
                'NO_CHARGE_FOR_THIS_RSI')
        self.assertDecimalAlmostEqual(126,
                mongo.total_of_all_charges(utilbill_doc))

        # try a different quantity: 250 therms
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 250
        mongo.compute_all_charges(utilbill_doc, uprs, cprs)
        self.assertDecimalAlmostEqual(10, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(75, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(51,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(5, the_charge_named('BLOCK_3'))
        self.assertRaises(StopIteration, the_charge_named,
                'NO_CHARGE_FOR_THIS_RSI')
        self.assertDecimalAlmostEqual(201,
                mongo.total_of_all_charges(utilbill_doc))

        # and another quantity: 0
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 0
        mongo.compute_all_charges(utilbill_doc, uprs, cprs)
        self.assertDecimalAlmostEqual(10, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(1,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertRaises(StopIteration, the_charge_named,
                'NO_CHARGE_FOR_THIS_RSI')
        self.assertDecimalAlmostEqual(11,
                mongo.total_of_all_charges(utilbill_doc))

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
            'chargegroups': {'All Charges': [
                {'rsi_binding': 'LINEAR', 'quantity': 0},
            ]},
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

    def test_get_service_address(self):
        utilbill_doc = example_data.example_utilbill
        address = mongo.get_service_address(utilbill_doc)
        self.assertEqual(address['postal_code'],'20010')
        self.assertEqual(address['city'],'Washington')
        self.assertEqual(address['state'],'DC')
        self.assertEqual(address['addressee'],'Monroe Towers')
        self.assertEqual(address['street'],'3501 13TH ST NW #WH')

    def test_refresh_charges(self):
        utilbill_doc = example_data.get_utilbill_dict('99999', start=date(
                2000,1,1), end=date(2000,2,1))
        utilbill_doc['chargegroups'] = {
            'All Charges': [
                {
                    'rsi_binding': 'OLD',
                    'description': 'this will get removed',
                    'quantity': 2,
                    'quantity_units': 'therms',
                    'rate': 3,
                    'total': 6,
                },
            ],
        }

        uprs = RateStructure(
            id=ObjectId(),
            type='UPRS',
            rates=[
                RateStructureItem(
                    rsi_binding='NEW_1',
                    description='a charge for this will be added',
                    quantity='1',
                    quantity_units='dollars',
                    rate='2',
                ),
                RateStructureItem(
                    rsi_binding='NEW_2',
                    description='ignored because overridden by CPRS',
                    quantity='3',
                    quantity_units='kWh',
                    rate='4',
                )
            ]
        )
        cprs = RateStructure(
            id=ObjectId(),
            type='CPRS',
            rates=[
                RateStructureItem(
                    rsi_binding='NEW_2',
                    description='a charge for this will be added too',
                    quantity='5',
                    quantity_units='therms',
                    rate='6',
                )
            ]
        )

        mongo.refresh_charges(utilbill_doc, uprs, cprs)

        self.maxDiff = None
        self.assertEqual({
            'All Charges': [
                {
                    'rsi_binding': 'NEW_1',
                    'description': 'a charge for this will be added',
                    'quantity': 0,
                    'quantity_units': 'dollars',
                    'rate': 0,
                    'total': 0,
                },
                {
                    'rsi_binding': 'NEW_2',
                    'description': 'a charge for this will be added too',
                    'quantity': 0,
                    'quantity_units': 'therms',
                    'rate': 0,
                    'total': 0,
                },
            ]},
            utilbill_doc['chargegroups']
        )
