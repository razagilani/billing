'''Unit tests for what will be the class wrapping a utility bill
document, when there finally is one.
'''
from datetime import date
import dateutil
from bson import ObjectId
from decimal import Decimal
from unittest import TestCase
from billing.test import example_data
from billing.test import utils
from billing.processing.rate_structure2 import RateStructure, RateStructureItem
from billing.processing import mongo
from billing.processing.exceptions import NoRSIError
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
                {'rsi_binding': 'REFERENCES_ANOTHER', 'quantity': 0},
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

        mongo.compute_all_charges(utilbill_doc, uprs)

        # function to get the "total" value of a charge from its name
        def the_charge_named(rsi_binding):
            return next(c['total'] for c in
                    utilbill_doc['chargegroups']['All Charges']
                    if c['rsi_binding'] == rsi_binding)

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate # structure. self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT')) self.assertDecimalAlmostEqual(45, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(31,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(10, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        self.assertRaises(StopIteration, the_charge_named,
                'NO_CHARGE_FOR_THIS_RSI')
        self.assertDecimalAlmostEqual(161,
                mongo.total_of_all_charges(utilbill_doc))

        # try a different quantity: 250 therms
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 250
        mongo.compute_all_charges(utilbill_doc, uprs)
        self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(75, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(51,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(30, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(5, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        self.assertRaises(StopIteration, the_charge_named,
                'NO_CHARGE_FOR_THIS_RSI')
        self.assertDecimalAlmostEqual(236,
                mongo.total_of_all_charges(utilbill_doc))

        # and another quantity: 0
        utilbill_doc['meters'][0]['registers'][0]['quantity'] = 0
        mongo.compute_all_charges(utilbill_doc, uprs)
        self.assertDecimalAlmostEqual(40, the_charge_named('CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('LINEAR'))
        self.assertDecimalAlmostEqual(1,
                the_charge_named('LINEAR_PLUS_CONSTANT'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_1'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_2'))
        self.assertDecimalAlmostEqual(0, the_charge_named('BLOCK_3'))
        self.assertDecimalAlmostEqual(5, the_charge_named('REFERENCES_ANOTHER'))
        self.assertRaises(StopIteration, the_charge_named,
                'NO_CHARGE_FOR_THIS_RSI')
        self.assertDecimalAlmostEqual(46,
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

    def test_regression_63401058(self):
        '''Regression test for bug 63401058, in which calculating the charges
        of a bill failed because RSI formulas were evaluated in the wrong
        order. This was due to iterating over a dictionary using rsi_bindings,
        where the order was dependendent on the hashes of those strings in
        the dictionary.
        '''
        # simplified version of the actual utility bill
        utilbill_doc = {
            "_id" : ObjectId("52b455467eb49a52d23d105d"),
            "account" : "10056",
            "billing_address" : {
                "city" : "Columbia",
                "state" : "MD",
                "addressee" : "Equity Mgmt",
                "street" : "8975 Guilford Rd Ste 100",
                "postal_code" : "21046"
            },
            "chargegroups" : {
                "Generation/Supply" : [
                    {
                        "rsi_binding" : "SUPPLY_COMMODITY",
                        "uuid" : "a1107f8e-3044-11e3-8b17-1231390e8112",
                        "quantity" : 396.8,
                        "rate_units" : "dollars",
                        "rate" : 0.747,
                        "quantity_units" : "therms",
                        "total" : 296.41,
                        "description" : "Commodity"
                    },
                    {
                        "rsi_binding" : "MD_SUPPLY_SALES_TAX",
                        "uuid" : "a11083ee-3044-11e3-8b17-1231390e8112",
                        "quantity" : 296.41,
                        "rate_units" : "percent",
                        "processingnote" : "",
                        "rate" : 0.06,
                        "quantity_units" : "dollars",
                        "total" : 17.79,
                        "description" : "MD Sales tax commodity"
                    }
                ],
            },
            "end" : dateutil.parser.parse("2013-12-16T00:00:00Z"), "meters" : [
                {
                    "present_read_date" : dateutil.parser.parse("2013-12-16T00:00:00Z"),
                    "registers" : [
                        {
                            "description" : "Therms",
                            "quantity" : 0,
                            "quantity_units" : "therms",
                            "identifier" : "T37110",
                            "type" : "total",
                            "register_binding" : "REG_TOTAL"
                        }
                    ],
                    "prior_read_date" : dateutil.parser.parse("2013-11-14T00:00:00Z"),
                    "identifier" : "T37110"
                }
            ],
            "rate_class" : "GROUP METER APT HEAT/COOL",
            "service" : "gas",
            "service_address" : {
                "city" : "District Heights",
                "state" : "MD",
                "addressee" : "Equity Mgmt",
                "postal_code" : "20747",
                "street" : "3747 Donnell Dr"
            },
            "start" : dateutil.parser.parse("2013-11-14T00:00:00Z"),
            "total" : 510.26,
            "utility" : "washgas"
        }

        # simplified version of document with _id 52b455467eb49a52d23d105c
        # (originally this was a CPRS with an empty UPRS)
        uprs =  RateStructure.from_json('''{
            "_cls" : "RateStructure",
            "type" : "UPRS",
            "rates" : [
                {
                    "rate" : "1",
                    "rsi_binding" : "SYSTEM_CHARGE",
                    "quantity" : "1"
                },
                {
                    "rate" : "1",
                    "rsi_binding" : "ENERGY_FIRST_BLOCK",
                    "quantity" : "1"
                },
                {
                    "rate" : "1",
                    "rsi_binding" : "ENERGY_SECOND_BLOCK",
                    "quantity" : "1"
                },
                {
                    "rsi_binding" : "ENERGY_REMAINDER_BLOCK",
                    "rate_units" : "dollars",
                    "rate" : "1",
                    "quantity_units" : "therms",
                    "quantity" : "1"
                },
                {
                    "rate" : "1",
                    "rsi_binding" : "SALES_TAX",
                    "quantity" : "SYSTEM_CHARGE.total"
                },
                {
                    "rate" : "1",
                    "rsi_binding" : "MD_GROSS_RECEIPTS_SURCHARGE",
                    "quantity" : "1"
                },
                {
                    "rate" : ".061316872",
                    "rsi_binding" : "PG_COUNTY_ENERGY_TAX",
                    "quantity" : "1"
                },
                {
                    "rate" : "1",
                    "rsi_binding" : "SUPPLY_COMMODITY",
                    "quantity" : "REG_TOTAL.quantity"
                },
                {
                    "rate" : "1",
                    "rsi_binding" : "MD_SUPPLY_SALES_TAX",
                    "quantity" : "SUPPLY_COMMODITY.total "
                }
            ]
        }''')

        # this should not raise an exception
        mongo.compute_all_charges(utilbill_doc, uprs)


    def test_compute_charge_without_rsi(self):
        '''Check that compute_charges raises a NoRSIError when attempting to
        compute charges for a bill containing a charge without a
        corresponding RSI.
        '''
        utilbill_doc = {
            'account': '12345', 'service': 'gas', 'utility': 'washgas',
            'start': date(2000,1,1), 'end': date(2000,2,1),
            'rate_class': "won't be loaded from the db anyway",
            'chargegroups': {'All Charges': [
                # a charge with no corrseponding RSI
                {'rsi_binding': 'NO_RSI', 'quantity': 0},
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

        # rate structures are empty
        uprs = RateStructure(
            id=ObjectId(),
            rates=[]
        )
        cprs = RateStructure(
            id=ObjectId(),
            rates=[]
        )

        # compute_all_charges should raise a KeyError if not all charges have
        # an RSI
        self.assertRaises(NoRSIError, mongo.compute_all_charges, utilbill_doc,
                uprs)

    def test_get_service_address(self):
        utilbill_doc = example_data.get_utilbill_dict('10003')
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
                    description='a charge for this will be added too',
                    quantity='5',
                    quantity_units='therms',
                    rate='6',
                    shared=False,
                ),
                RateStructureItem(
                    rsi_binding='NO_CHARGE',
                    description='this RSI should not have a charge',
                    quantity='7',
                    quantity_units='therms',
                    rate='8',
                    shared=True,
                    has_charge=False,
                )
            ]
        )

        mongo.refresh_charges(utilbill_doc, uprs)

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
