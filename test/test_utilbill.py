'''Unit tests for what will be the class wrapping a utility bill
document, when there finally is one.
'''
from datetime import date
from bson import ObjectId
from unittest import TestCase
from billing.test import example_data
from billing.test import utils
from billing.processing.rate_structure2 import RateStructure
from billing.processing import mongo

class UtilBillTest(TestCase):

    def test_compute(self):
        # make a utility bill document from scratch to ensure full control over
        # its contents
        utilbill_doc = {
            'account': '12345', 'service': 'gas', 'utility': 'washgas',
            'start': date(2000,1,1), 'end': date(2000,1,1),
            'rate_structure_binding': "won't be loaded from the db anyway",
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
        combined_rate_structure = RateStructure({
            '_id': ObjectId(),
            'registers': [{
                'register_binding': 'REG_TOTAL',
                # this dictionary is not actually a "register", so
                # quantity/units here don't matter at all
                'quantity': -1,
                'quantity_units': 'who cares',
            }],
            'rates': [
                {
                    'rsi_binding': 'CONSTANT',
                    'quantity': '50',
                    'quantity_units': 'dollars',
                    'rate_units': 'dollars',
                    'rate': '0.2',
                },
                {
                    'rsi_binding': 'LINEAR',
                    'quantity': 'REG_TOTAL.quantity * 3',
                    'quantity_units': 'therms',
                    'rate': '0.1',
                    'rate_units': 'dollars',
                },
                {
                    'rsi_binding': 'LINEAR_PLUS_CONSTANT',
                    'quantity': 'REG_TOTAL.quantity * 2 + 10',
                    'quantity_units': 'therms',
                    'rate_units': 'dollars',
                    'rate': '0.1',
                },
                {
                    'rsi_binding': 'BLOCK_1',
                    'quantity': 'min(100, REG_TOTAL.quantity)',
                    'quantity_units': 'therms',
                    'rate': '0.3',
                    'rate_units': 'dollars',
                },
                {
                    'rsi_binding': 'BLOCK_2',
                    'quantity': 'min(200, max(0, REG_TOTAL.quantity - 100))',
                    'quantity_units': 'therms',
                    'rate': '0.2',
                    'rate_units': 'dollars',
                },
                {
                    'rsi_binding': 'BLOCK_3',
                    'quantity': 'max(0, REG_TOTAL.quantity - 200)',
                    'quantity_units': 'therms',
                    'rate': '0.1',
                    'rate_units': 'dollars',
                },
                {
                    'rsi_binding': 'NO_CHARGE_FOR_THIS_RSI',
                    'quantity': '1',
                    'quantity_units': 'therms',
                    'rate': '1',
                    'rate_units': 'dollars',
                },
            ]
        })

        mongo.compute_utility_bill(utilbill_doc, combined_rate_structure)

        def the_charge_named(rsi_binding):
            return next(c['total'] for c in
                    utilbill_doc['chargegroups']['All Charges']
                    if c['rsi_binding'] == rsi_binding)

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for
        # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate
        # structure.
        self.assertEquals(10, the_charge_named('CONSTANT'))
        self.assertEquals(45, the_charge_named('LINEAR'))
        self.assertEquals(31, the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertEquals(30, the_charge_named('BLOCK_1'))
        self.assertEquals(10, the_charge_named('BLOCK_2'))
        self.assertEquals(0, the_charge_named('BLOCK_3'))
        self.assertRaises(StopIteration, the_charge_named, 'NO_CHARGE_FOR_THIS_RSI')

        # try a different quantity: 250 therms
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 250
        mongo.compute_utility_bill(utilbill_doc, combined_rate_structure)
        self.assertEquals(10, the_charge_named('CONSTANT'))
        self.assertEquals(75, the_charge_named('LINEAR'))
        self.assertEquals(51, the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertEquals(30, the_charge_named('BLOCK_1'))
        self.assertEquals(30, the_charge_named('BLOCK_2'))
        self.assertEquals(5, the_charge_named('BLOCK_3'))
        self.assertRaises(StopIteration, the_charge_named, 'NO_CHARGE_FOR_THIS_RSI')

        # and another quantity: 0
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 0
        mongo.compute_utility_bill(utilbill_doc, combined_rate_structure)
        self.assertEquals(10, the_charge_named('CONSTANT'))
        self.assertEquals(0, the_charge_named('LINEAR'))
        self.assertEquals(1, the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertEquals(0, the_charge_named('BLOCK_1'))
        self.assertEquals(0, the_charge_named('BLOCK_2'))
        self.assertEquals(0, the_charge_named('BLOCK_3'))
        self.assertRaises(StopIteration, the_charge_named, 'NO_CHARGE_FOR_THIS_RSI')

