from datetime import datetime
import unittest
from json import loads

from core import init_model
from core.model import Session, UtilityAccount, Address, UtilBill, Utility,\
    Charge, Register, RateClass
from brokerage import wsgi
from brokerage.brokerage_model import BrokerageAccount
from test.setup_teardown import TestCaseWithSetup
from test import init_test_config


# this may change
URL_PREFIX = '/utilitybills/'


class TestPGWeb(unittest.TestCase):
    maxDiff = None

    def assertJson(self, expected, actual):
        '''AssertEqual for JSON where the things being compared can be in
        either string or dict/list form.
        '''
        if isinstance(expected, basestring):
            expected = loads(expected)
        if isinstance(actual, basestring):
            actual = loads(actual)
        self.assertEqual(expected, actual)

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()

        # self.db_fd, wsgi.app.config['DATABASE'] = tempfile.mkstemp()
        wsgi.app.config['TESTING'] = True

    def setUp(self):
        # TODO: this should not have to be done multiple times, but removing it
        # causes a failure when the session is committed below.
        init_model()

        TestCaseWithSetup.truncate_tables()
        s = Session()
        utility = Utility('Example Utility', Address())
        utility1 = Utility('Empty Utility', Address())
        utility2 = Utility('Some Other Utility',  Address())
        ua1 = UtilityAccount('Account 1', '11111', utility, None, None,
                             Address(), Address(), '1')
        ua2 = UtilityAccount('Account 2', '22222', utility, None, None,
                             Address(), Address(), '2')
        ua3 = UtilityAccount('Not PG', '33333', utility, None, None,
                             Address(), Address(), '3')
        rate_class = RateClass('Some Rate Class', utility, 'gas')
        rate_class1 = RateClass('Other Rate Class', utility, 'electric')
        s.add_all([rate_class, rate_class1])
        ua1.id, ua2.id, ua3.id = 1, 2, 3
        utility.id, utility1.id, utility2.id = 1, 2, 10
        s.add_all([utility, utility1, utility2])
        s.add_all([ua1, ua2, ua3])
        s.add_all([BrokerageAccount(ua1), BrokerageAccount(ua2)])
        ub1 = UtilBill(ua1, UtilBill.Complete, utility, None,
                       rate_class, Address(), Address(street='1 Example St.'))
        ub2 = UtilBill(ua1, UtilBill.Complete, utility, None,
                       None, Address(), Address(street='2 Example St.'))
        ub3 = UtilBill(ua3, UtilBill.Complete, utility1, None,
                       None, Address(), Address(street='2 Example St.'))

        ub1.id = 1
        ub2.id = 2
        ub3.id = 3

        register1 = Register(ub1, "ABCDEF description",
                "ABCDEF", 'therms', False, "total", None, "GHIJKL",
                quantity=150,
                register_binding='REG_TOTAL')
        register2 = Register(ub2, "ABCDEF description",
                "ABCDEF", 'therms', False, "total", None, "GHIJKL",
                quantity=150,
                register_binding='REG_TOTAL')
        s.add_all([register1, register2])
        ub1.registers = [register1]
        ub2.registers = [register2]

        c1 = Charge(ub1, 'CONSTANT', 0.4, '100', unit='dollars',
                    type='distribution', target_total=1)
        c2 = Charge(ub1, 'LINEAR', 0.1, 'REG_TOTAL.quantity * 3',
                    unit='therms', type='supply', target_total=2)
        c3 = Charge(ub2, 'LINEAR_PLUS_CONSTANT', 0.1,
                    'REG_TOTAL.quantity * 2 + 10', unit='therms',
                    type='supply')
        c4 = Charge(ub2, 'BLOCK_1', 0.3, 'min(100, REG_TOTAL.quantity)',
                    unit='therms', type='distribution')
        c5 = Charge(ub2, 'BLOCK_2', 0.4,
                    'min(200, max(0, REG_TOTAL.quantity - 100))',
                    unit='dollars', type='supply')
        c1.id, c2.id, c3.id, c4.id, c5.id = 1, 2, 3, 4, 5
        s.add_all([c1, c2, c3, c4, c5])
        s.add_all([ub1, ub2, ub3])

        s.commit()

        self.app = wsgi.app.test_client()


    def tearDown(self):
        TestCaseWithSetup.truncate_tables()

    def test_accounts(self):
        rv = self.app.get(URL_PREFIX + 'accounts')
        self.assertJson(
            [{'account': '11111',
              'id': 1,
              'service_address': '1 Example St., ,  ',
              'utility': 'Example Utility',
              'utility_account_number': '1'},
             {'account': '22222',
              'id': 2,
              'service_address': ', ,  ',
              'utility': 'Example Utility',
              'utility_account_number': '2'}], rv.data)

    def test_utilbills_list(self):
        rv = self.app.get(URL_PREFIX + 'utilitybills?id=3')
        self.assertJson(
            {'results': 1,
             'rows': [
                 {'account': None,
                  'computed_total': 0.0,
                  'id': 3,
                  'next_estimated_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Unknown',
                  'service': 'Unknown',
                  'service_address': '2 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 0.0,
                  'total_charges': 0.0,
                  'total_energy': 0.0,
                  'utility': 'Empty Utility',
                  'utility_account_number': '3',
                  'supply_choice_id': None
                 },
             ], }, rv.data)

    def test_charges_list(self):
        rv = self.app.get(URL_PREFIX + 'charges?utilbill_id=1')
        self.assertJson(
            {'rows': [
                {"target_total": 2.0,
                 "rsi_binding": "LINEAR",
                 "id": 2},
            ],
             'results': 1,
            }, rv.data)
        rv = self.app.get(URL_PREFIX + 'charges?utilbill_id=2')
        self.assertJson(
            {'rows': [
                {
                    "target_total": None,
                    "rsi_binding": "LINEAR_PLUS_CONSTANT",
                    "id": 3
                },
                {
                    "target_total": None,
                    "rsi_binding": "BLOCK_2",
                    "id": 5
                }
            ],
             'results': 2,
            }, rv.data)

    def test_charge(self):
        rv = self.app.put(URL_PREFIX + 'charges/2', data=dict(
            id=2,
            rsi_binding='NON_LINEAR',
            target_total=1
        ))
        self.assertJson(
            {'rows':
                 {
                     "target_total": 1,
                     "rsi_binding": "NON_LINEAR",
                     "id": 2
                 },
             'results': 1
            }, rv.data)

    def test_utilbill(self):
        rv = self.app.put(URL_PREFIX + 'utilitybills/1', data=dict(
            id=2,
            period_start=datetime(2000, 1, 1).isoformat()
        ))
        self.assertJson(
            {'rows':
                 {'account': None,
                  'computed_total': 85.0,
                  'id': 1,
                  'next_estimated_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': '2000-01-01',
                  'processed': False,
                  'rate_class': 'Some Rate Class',
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 2.0,
                  'total_charges': 0.0,
                  'total_energy': 150.0,
                  'utility': 'Example Utility',
                  'utility_account_number': '1',
                  'supply_choice_id': None
                 },
             'results': 1,
            }, rv.data)

    def test_rate_class(self):
        rv = self.app.get(URL_PREFIX + 'utilitybills?id=3')
        self.assertJson(
            {'results': 1,
             'rows': [
                 {'account': None,
                  'computed_total': 0.0,
                  'id': 3,
                  'next_estimated_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Unknown',
                  'service': 'Unknown',
                  'service_address': '2 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 0.0,
                  'total_charges': 0.0,
                  'total_energy': 0.0,
                  'utility': 'Empty Utility',
                  'utility_account_number': '3',
                  'supply_choice_id': None
                 }
             ], }, rv.data)

        rv = self.app.put(URL_PREFIX + 'utilitybills/1', data=dict(
                id = 2,
                utility = "Empty Utility"
        ))

        self.assertJson(
            {
            "results": 1,
            "rows": {
                'account': None,
                  'computed_total': 85.0,
                  'id': 1,
                  'next_estimated_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Some Rate Class',
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 2.0,
                  'total_charges': 0.0,
                  'total_energy': 150.0,
                  'utility': 'Empty Utility',
                  'utility_account_number': '1',
                  'supply_choice_id': None
            },
            }, rv.data
        )

        rv = self.app.put(URL_PREFIX + 'utilitybills/1', data=dict(
                id = 10,
                utility = "Some Other Utility"
        ))

        self.assertJson(
            {
            "results": 1,
            "rows": {
                'account': None,
                  'computed_total': 85.0,
                  'id': 1,
                  'next_estimated_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Some Rate Class',
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 2.0,
                  'total_charges': 0.0,
                  'total_energy': 150.0,
                  'utility': 'Some Other Utility',
                  'utility_account_number': '1',
                  'supply_choice_id': None
            },
            }, rv.data
        )
