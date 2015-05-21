"""All tests for the Bill Entry application.
"""
from datetime import datetime, date
from time import sleep
import unittest
from json import loads
import json
from mock import Mock
from sqlalchemy.orm.exc import NoResultFound

# if init_test_config() is not called before "billentry" is imported,
# "billentry" will call init_config to initialize the config object with the
# non-test config file. so init_test_config must be called before
# "billentry" is imported.
from exc import UnEditableBillError
from test import init_test_config
from util import FixMQ
from util.dictutils import deep_map

init_test_config()

from core.altitude import AltitudeBill, get_utilbill_from_guid

import billentry
from billentry import common
from billentry.billentry_exchange import create_amqp_conn_params, \
    ConsumeUtilbillGuidsHandler
from billentry.billentry_model import BillEntryUser, BEUtilBill, Role, BEUserSession
from billentry.common import replace_utilbill_with_beutilbill, \
    account_has_bills_for_data_entry

from core import init_model, altitude
from core.model import Session, UtilityAccount, Address, UtilBill, Utility,\
    Charge, Register, RateClass
from brokerage.brokerage_model import BrokerageAccount
with FixMQ():
    from mq import IncomingMessage
    from mq.tests import create_mock_channel_method_props, \
    create_channel_message_body
from test.setup_teardown import clear_db


def unicodify(x):
    return unicode(x) if isinstance(x, basestring) else x


class TestBEUtilBill(unittest.TestCase):
    """Unit test for BEUtilBill.
    """
    def setUp(self):
        self.utility = Mock(autospec=Utility)
        self.rate_class = Mock(autospec=RateClass)
        self.rate_class.get_register_list.return_value = []
        self.ua = UtilityAccount('Account 1', '11111', self.utility, None, None,
                            Address(), Address(), '1')
        self.user = Mock(autospec=BillEntryUser)
        self.user.is_anonymous.return_value = False
        self.ub = BEUtilBill(self.ua, self.utility, self.rate_class, None)

    def test_create_from_utilbill(self):
        utilbill = UtilBill(self.ua, self.utility, self.rate_class, None,
                            self.rate_class)
        beutilbill = BEUtilBill.create_from_utilbill(utilbill)
        self.assertIs(BEUtilBill, type(beutilbill))
        for attr_name in UtilBill.column_names():
            if attr_name in ('discriminator'):
                continue
            utilbill_value = getattr(utilbill, attr_name)
            beutilbill_value = getattr(beutilbill, attr_name)
            self.assertEqual(utilbill_value, beutilbill_value)

    def test_entry(self):
        self.assertFalse(self.ub.is_entered())

        the_date = datetime(2000,1,1,0)
        self.ub.enter(self.user, the_date)
        self.assertEqual(the_date, self.ub.get_date())
        self.assertEqual(self.user, self.ub.get_user())
        self.assertTrue(self.ub.is_entered())
        self.assertEqual(self.ub.editable(), False)

        self.ub.un_enter()
        self.assertEqual(None, self.ub.get_date())
        self.assertEqual(None, self.ub.get_user())
        self.assertFalse(self.ub.is_entered())
        self.assertEqual(self.ub.editable(), True)

        self.ub.processed = True
        self.assertEqual(None, self.ub.get_date())
        self.assertEqual(None, self.ub.get_user())
        self.assertTrue(self.ub.is_entered())

class BillEntryIntegrationTest(object):
    """Shared code for TestCases that test Bill Entry. Some of this (like
    assertJson) is not specific to Bill Entry and can be shared with other
    test cases.

    This is not a subclass of TestCase because inheritance from TestCase
    subclasses never seems to work. Subclasses should have this as their first
    superclass and TestCase as the second.
    """
    maxDiff = None

    # this may change
    URL_PREFIX = '/utilitybills/'

    def assertJson(self, expected, actual):
        '''AssertEqual for JSON where the things being compared can be in
        either string or dict/list form.
        '''
        if isinstance(expected, basestring):
            expected = deep_map(unicodify, loads(expected))
        if isinstance(actual, basestring):
            actual = deep_map(unicodify, loads(actual))
        self.assertEqual(expected, actual)

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()
        billentry.app.config['TESTING'] = True
        # TESTING is supposed to imply LOGIN_DISABLED if the Flask-Login
        # "login_required" decorator is used, but we
        # are using the before_request callback instead
        billentry.app.config['LOGIN_DISABLED'] = True
        # TODO: this should prevent the method decorated with
        # "app.errorhandler" from running, but doesn't
        billentry.app.config['TRAP_HTTP_EXCEPTIONS'] = True
        billentry.app.config['PROPAGATE_EXCEPTIONS'] = True
        cls.app = billentry.app.test_client()

    def setUp(self):
        clear_db()

        # TODO: this should not have to be done multiple times, but removing it
        # causes a failure when the session is committed below.
        init_model()

        self.project_mgr_role = Role(
            'Project Manager',
            'Role for accessing reports view of billentry app')
        self.admin_role = Role('admin', 'admin role for bill entry app')
        self.utility = Utility(name='Example Utility')
        self.utility.id = 1
        self.ua1 = UtilityAccount('Account 1', '11111', self.utility, None,
                                  None, Address(), Address(), account_number='1')
        self.ua1.id = 1
        self.some_rate_class = RateClass('Some Rate Class', self.utility, 'gas')
        self.some_rate_class.id= 1
        self.ub1 = BEUtilBill(self.ua1, self.utility, self.some_rate_class,
                              service_address=Address(street='1 Example St.'))
        self.ub1.registers[0].quantity = 150
        self.ub1.registers[0].meter_identifier = "GHIJKL"
        self.ub2 = BEUtilBill(self.ua1, self.utility, None,
                              service_address=Address(street='2 Example St.'))
        self.ua2 = UtilityAccount('Account 2', '22222', self.utility, None,
                                  None, Address(), Address(), account_number='2')
        self.some_electric_rate_class = RateClass('Some Electric Rate Class', self.utility,
                                     'electric')
        self.some_electric_rate_class.id = 2
        self.ub2.set_rate_class(self.some_electric_rate_class)
        self.ub2.registers[0].unit = 'therms'
        self.ub2.registers[0].quantity = 250.0
        self.ub2.registers[0].meter_identifier = 'MNOPQR'
        self.ub3 = BEUtilBill(self.ua2, self.utility, self.some_electric_rate_class,
                              service_address=Address(street='1 Electric St.'))
        self.ub1.id = 1
        self.ub2.id = 2
        self.ub3.id = 3
        s = Session()
        s.add_all([
            self.utility, self.ua1, self.some_rate_class, self.ub1,
            self.ub2, self.project_mgr_role, self.admin_role,
        ])
        s.commit()
        # TODO: add more database objects used in multiple subclass setUps

    def tearDown(self):
        clear_db()

class TestBillEntryMain(BillEntryIntegrationTest, unittest.TestCase):
    """Integration tests using REST request handlers related to Bill Entry main
    page.
    BillEntryIntegrationTest must be the first superclass for super() to work.
    """
    def setUp(self):
        super(TestBillEntryMain, self).setUp()

        s = Session()
        utility1 = Utility(name='Empty Utility')
        utility2 = Utility(name='Some Other Utility')
        ua2 = UtilityAccount('Account 2', '22222', self.utility, None, None,
                             Address(), Address(), account_number='2')
        ua3 = UtilityAccount('Not PG', '33333', self.utility, None, None,
                             Address(), Address(), account_number='3')
        self.other_rate_class = RateClass('Other Rate Class', self.utility, 'electric')
        self.other_rate_class.id = 3
        s.add_all([self.some_rate_class, self.other_rate_class])
        ua2.id, ua3.id = 2, 3
        utility1.id, utility2.id = 2, 10
        s.add_all([self.utility, utility1, utility2, ua2, ua3,
                   BrokerageAccount(self.ua1), BrokerageAccount(ua2)])
        ub3 = UtilBill(ua3, utility1, None,
                       service_address=Address(street='2 Example St.'))
        ub3.id = 3

        self.ub1.registers[0].quantity = 150
        self.ub2.registers[0].quantity = 150
        self.ub2.registers[0].meter_identifier = "GHIJKL"

        c1 = Charge('CONSTANT', rate=0.4, formula='100', unit='dollars',
                    type='distribution', target_total=1)
        c2 = Charge('LINEAR', rate=0.1, formula='REG_TOTAL.quantity * 3',
                    unit='therms', type='supply', target_total=2)
        self.ub1.charges = [c1, c2]
        c3 = Charge('LINEAR_PLUS_CONSTANT', rate=0.1,
                    formula='REG_TOTAL.quantity * 2 + 10', unit='therms',
                    type='supply')
        c4 = Charge('BLOCK_1', rate=0.3, formula='min(100, REG_TOTAL.quantity)',
                    unit='therms', type='distribution')
        c5 = Charge('BLOCK_2',rate= 0.4,
                    formula='min(200, max(0, REG_TOTAL.quantity - 100))',
                    unit='dollars', type='supply')
        self.ub2.charges = [c3, c4, c5]
        c1.id, c2.id, c3.id, c4.id, c5.id = 1, 2, 3, 4, 5
        s.add_all([c1, c2, c3, c4, c5, ub3])
        user = BillEntryUser(email='user1@test.com', password='password')
        s.add(user)
        s.commit()

    def test_accounts_get(self):
        rv = self.app.get(self.URL_PREFIX + 'accounts')
        self.assertJson(
            [{'account': '11111',
              'bills_to_be_entered': True,
              'id': 1,
              'service_address': '1 Example St., ,  ',
              'utility': 'Example Utility',
              'utility_account_number': '1'},
             {'account': '22222',
              'bills_to_be_entered': False,
              'id': 2,
              'service_address': ', ,  ',
              'utility': 'Example Utility',
              'utility_account_number': '2'}], rv.data)

    def test_account_put(self):
        rv = self.app.put(self.URL_PREFIX + 'accounts/1')
        self.assertJson(
            {'account': '11111',
              'bills_to_be_entered': True,
              'id': 1,
              'service_address': '1 Example St., ,  ',
              'utility': 'Example Utility',
              'utility_account_number': '1'}, rv.data)

        rv = self.app.get(self.URL_PREFIX + 'utilitybills?id=3')
        self.assertJson(
            {'results': 0,
             'rows': [], }, rv.data)

    def test_utilbills_list(self):
        rv = self.app.get(self.URL_PREFIX + 'utilitybills?id=1')
        expected = {'results': 2,
         'rows': [
             {'computed_total': 0.0,
              'due_date': None,
              'id': 2,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': None,
              'processed': False,
              'rate_class': self.some_electric_rate_class.name,
              'rate_class_id': self.some_electric_rate_class.id,
              'service': 'Electric',
              'service_address': '2 Example St., ,  ',
              'supplier': 'Unknown',
              'supplier_id': None,
              'supply_group': 'Unknown',
              'supply_group_id': None,
              'supply_total': 0.0,
              'target_total': 0.0,
              'total_energy': 150.0,
              'utility': 'Example Utility',
              'utility_id': 1,
              'utility_account_number': '1',
              'utility_account_id': 1,
              'supply_choice_id': None,
              'wiki_url': 'http://example.com/utility:Example Utility',
              'entered': False,
              'flagged': False,
              'meter_identifier': 'GHIJKL',
              'tou': False
             },
             {'computed_total': 0.0,
              'due_date': None,
              'entered': False,
              'id': 1,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': None,
              'processed': False,
              'rate_class': self.some_rate_class.name,
              'rate_class_id': self.some_rate_class.id,
              'service': 'Gas',
              'service_address': '1 Example St., ,  ',
              'supplier': 'Unknown',
              'supplier_id': None,
              'supply_group': 'Unknown',
              'supply_group_id': None,
              'supply_choice_id': None,
              'supply_total': 2.0,
              'target_total': 0.0,
              'total_energy': 150.0,
              'utility': 'Example Utility',
              'utility_id': 1,
              'utility_account_number': '1',
              'utility_account_id': 1,
              'wiki_url': 'http://example.com/utility:Example Utility',
              'flagged': False,
              'meter_identifier': 'GHIJKL',
              'tou': False}
         ], }
        self.assertJson(expected, rv.data)

    def test_charges_list(self):
        rv = self.app.get(self.URL_PREFIX + 'charges?utilbill_id=1')
        self.assertJson(
            {'rows': [
                {"target_total": 2.0,
                 "rsi_binding": "LINEAR",
                 "id": 2},
            ],
             'results': 1,
            }, rv.data)
        rv = self.app.get(self.URL_PREFIX + 'charges?utilbill_id=2')
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
        rv = self.app.put(self.URL_PREFIX + 'charges/2', data=dict(
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
        expected = {'rows':
             {'computed_total': 85.0,
              'due_date': None,
              'id': 1,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': '2000-01-01',
              'processed': False,
              'rate_class': self.some_rate_class.name,
              'rate_class_id': self.some_rate_class.id,
              'service': 'Gas',
              'service_address': '1 Example St., ,  ',
              'supplier': 'Unknown',
              'supplier_id': None,
              'supply_group': 'Unknown',
              'supply_group_id': None,
              'supply_choice_id': None,
              'supply_total': 2.0,
              'target_total': 0.0,
              'total_energy': 150.0,
              'utility': 'Example Utility',
              'utility_id': 1,
              'utility_account_id': 1,
              'utility_account_number': '1',
              'wiki_url': 'http://example.com/utility:Example Utility',
              'entered': True,
              'meter_identifier': 'GHIJKL',
              'flagged': False,
              'tou': False
              },
         'results': 1}

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
            id=2,
            period_start=datetime(2000, 1, 1).isoformat(),
            entered=True
        ))
        expected['rows']['period_start'] = '2000-01-01'
        self.assertJson(expected, rv.data)

        # catch ProcessedBillError because a 500 response is returned
        # when the user tries to edit a bill that is not editable=
        with self.assertRaises(UnEditableBillError):
            rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
                id=2,
                next_meter_read_date=date(2000, 2, 5).isoformat()
                ))

        # this request is being made using a different content-type because
        # with the default content-type of form-urlencoded bool False
        # was interpreted as a string and it was evaluating to True on the
        # server. Also in out app, the content-type is application/json so
        # we should probably update all our test code to use application/json
        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1',
                          content_type='application/json',
            data=json.dumps(dict(
                id=2,
                entered=False
        )))
        self.assertEqual(rv.status_code, 200)

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
            id=2,
            next_meter_read_date=date(2000, 2, 5).isoformat()
        ))

        expected['rows']['next_meter_read_date'] = date(2000, 2, 5).isoformat()
        expected['rows']['entered'] = False
        self.assertJson(expected, rv.data)

        rv = self.app.put(
            self.URL_PREFIX + 'utilitybills/1',
            content_type='application/json',
            data=json.dumps(dict(
                id=2,
                flagged=True
            ))
        )
        self.assertEqual(rv.status_code, 200)
        expected['rows']['flagged'] = True
        self.assertJson(expected, rv.data)

        rv = self.app.put(
            self.URL_PREFIX + 'utilitybills/1',
            content_type='application/json',
            data=json.dumps(dict(
                id=2,
                flagged=False
            ))
        )
        self.assertEqual(rv.status_code, 200)
        expected['rows']['flagged'] = False
        self.assertJson(expected, rv.data)

        # TODO: why aren't there tests for editing all the other fields?

    def test_update_utilbill_rate_class(self):
        expected = {'results': 2,
         'rows': [
             {'computed_total': 0.0,
              'due_date': None,
              'id': 2,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': None,
              'processed': False,
              'rate_class': self.some_electric_rate_class.name,
              'rate_class_id': self.some_electric_rate_class.id,
              'service': 'Electric',
              'service_address': '2 Example St., ,  ',
              'supplier': 'Unknown',
              'supplier_id': None,
              'supply_group': 'Unknown',
              'supply_group_id': None,
              'supply_total': 0.0,
              'target_total': 0.0,
              'total_energy': 150.0,
              'utility': 'Example Utility',
              'utility_account_id': 1,
              'utility_id': 1,
              'utility_account_number': '1',
              'supply_choice_id': None,
              'wiki_url': 'http://example.com/utility:Example Utility',
              'entered': False,
              'flagged': False,
              'meter_identifier': 'GHIJKL',
              'tou': False
             },
             {'computed_total': 0.0,
              'due_date': None,
              'entered': False,
              'id': 1,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': None,
              'processed': False,
              'rate_class': self.some_rate_class.name,
              'rate_class_id': self.some_rate_class.id,
              'service': 'Gas',
              'service_address': '1 Example St., ,  ',
              'supplier': 'Unknown',
              'supplier_id': None,
              'supply_group': 'Unknown',
              'supply_group_id': None,
              'supply_choice_id': None,
              'supply_total': 2.0,
              'target_total': 0.0,
              'total_energy': 150.0,
              'utility': 'Example Utility',
              'utility_id': 1,
              'utility_account_number': '1',
              'utility_account_id': 1,
              'wiki_url': 'http://example.com/utility:Example Utility',
              'flagged': False,
              'meter_identifier': 'GHIJKL',
              'tou': False}
         ], }
        rv = self.app.get(self.URL_PREFIX + 'utilitybills?id=1')
        self.assertJson(expected, rv.data)

        # TODO reuse 'expected' in later assertions instead of repeating the
        # giant dictionary over and over
        utility = Utility(name="Empty Utility")
        Session().add(utility)
        Session().commit()

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
                id = 2,
                utility = utility.id
        ))
        self.assertJson({
            "results": 1,
            "rows": {
         	    'computed_total': 85.0,
                'due_date': None,
                'entered': False,
                'id': 1,
                'next_meter_read_date': None,
                'pdf_url': '',
                'period_end': None,
                'period_start': None,
                'processed': False,
                'rate_class': self.some_rate_class.name,
                'rate_class_id': self.some_rate_class.id,
                'service': 'Gas',
                'service_address': '1 Example St., ,  ',
                'supplier': 'Unknown',
                'supplier_id': None,
                'supply_group': 'Unknown',
                'supply_group_id': None,
                'supply_choice_id': None,
                'supply_total': 2.0,
                'target_total': 0.0,
                'total_energy': 150.0,
                'utility': 'Example Utility',
                'utility_id': 1,
                'utility_account_number': '1',
                'utility_account_id': 1,
                'wiki_url': 'http://example.com/utility:Example Utility',
                'flagged': False,
                'meter_identifier': 'GHIJKL',
                'tou': False
            }}, rv.data
        )
        utility = Utility(name="Some Other Utility")
        Session().add(utility)
        Session().commit()
        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
                id = 10,
                utility = utility.id
        ))

        self.assertJson(
            {
            "results": 1,
            "rows": {
                  'computed_total': 85.0,
                  'id': 1,
                  'due_date': None,
                  'next_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': self.some_rate_class.name,
                  'rate_class_id': self.some_rate_class.id,
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supplier_id': None,
                  'supply_group': 'Unknown',
                  'supply_group_id': None,
                  'supply_total': 2.0,
                  'target_total': 0.0,
                  'total_energy': 150.0,
                  'utility': 'Example Utility',
                  'utility_id': 1,
                  'utility_account_number': '1',
                  'utility_account_id': 1,
                  'supply_choice_id': None,
                  'wiki_url': 'http://example.com/utility:Example Utility',
                  'entered': False,
                  'flagged': False,
                  'meter_identifier': 'GHIJKL',
                  'tou': False
            },
            }, rv.data
        )

class TestBillEntryReport(BillEntryIntegrationTest, unittest.TestCase):
    """Integration tests using REST request handlers related to Bill Entry
    report page.
    """
    def setUp(self):
        super(TestBillEntryReport, self).setUp()
        s = Session()
        self.user1 = BillEntryUser(email='1@example.com', password='password')
        self.user1.id = 1
        self.user2 = BillEntryUser(email='2@example.com', password='password')
        self.user2.id = 2
        self.user3 = BillEntryUser(email='3@example.com', password='password')
        self.user3.id = 3
        s.add_all([self.ub1, self.ub2, self.ub3, self.user1, self.user2])
        self.user1.roles = [self.project_mgr_role]
        self.user3.roles = [self.admin_role]
        s.commit()

        self.response_all_counts_0 = {"results": 2, "rows": [
            {"id": 1, "email": '1@example.com', "total_count": 0,
             "gas_count": 0, "electric_count": 0, "elapsed_time": 0},
            {"id": 2, 'email': '2@example.com', "total_count": 0,
             "gas_count": 0, "electric_count": 0, "elapsed_time": 0}]}
        self.response_no_flagged_bills = {"results": 0, "rows": []}

    def test_report_count_for_user(self):

        data = {'email': '1@example.com', 'password': 'password'}
        # post request for user login with valid credentials
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)

        # on successful login user is routed to the next url
        self.assertTrue(response.status_code == 302)
        self.assertEqual('http://localhost/', response.location)

        url_format = self.URL_PREFIX + 'users_counts?start=%s&end=%s'

        # no "entered" bills yet
        rv = self.app.get(url_format % (datetime(2000,1,1).isoformat(),
                                        datetime(2000,2,1).isoformat()))

        self.assertJson(self.response_all_counts_0, rv.data)

        self.ub1.enter(self.user1, datetime(2000,1,10))
        self.ub2.enter(self.user1, datetime(2000,1,20))

        # no bills in range
        rv = self.app.get(url_format % (datetime(2000,1,11).isoformat(),
                                        datetime(2000,1,20).isoformat()))
        self.assertJson(self.response_all_counts_0, rv.data)

        # 1 gas bill and 1 bill without rate class in range for user 1
        # No bill in range for user 2
        rv = self.app.get(url_format % (datetime(2000,1,10).isoformat(),
                                        datetime(2000,1,21).isoformat()))
        self.assertJson({"results": 2, "rows": [
            {"id": self.user1.id, "email": '1@example.com', "total_count": 2,
             "gas_count": 1, "electric_count": 1, "elapsed_time": 0},
            {"id": self.user2.id, 'email': '2@example.com', "total_count": 0,
             "gas_count": 0, "electric_count": 0, "elapsed_time": 0}]},
                        rv.data)

        self.ub3.enter(self.user2, datetime(2000,1,10))

        # 1 gas bill and 1 bill without rate class in range for user 1
        # 1 electrtic bill for user 1
        rv = self.app.get(url_format % (datetime(2000,1,10).isoformat(),
                                        datetime(2000,1,21).isoformat()))
        self.assertJson({"results": 2, "rows": [
            {"id": self.user1.id, "email": '1@example.com', "total_count": 2,
             "gas_count": 1, "electric_count": 1, "elapsed_time": 0},
            {"id": self.user2.id, 'email': '2@example.com', "total_count": 1,
             "gas_count": 0, "electric_count": 1, "elapsed_time": 0}]},
                        rv.data)


    def test_user_permission_for_utilbill_counts(self):
        data = {'email':'2@example.com', 'password': 'password'}
        # post request for user login with for user2, member of no role
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)

        url_format = self.URL_PREFIX + 'users_counts?start=%s&end=%s'

        rv = self.app.get(url_format % (datetime(2000,1,1).isoformat(),
                                        datetime(2000,2,1).isoformat()))
        # this should result in a status_code of '403 permission denied'
        # as only members of 'Project Manager' or 'admin' role are allowed
        # access to report page and user2 is member of niether one
        self.assertEqual(403, rv.status_code)


        data = {'email':'1@example.com', 'password': 'password'}
        # post request for user login with for user1, member of
        # Project Manager role
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)
        rv = self.app.get(url_format % (datetime(2000,1,1).isoformat(),
                                        datetime(2000,2,1).isoformat()))

        # this should succeed with 200 as user1 is member of Project Manager
        # Role
        self.assertEqual(200, rv.status_code)
        self.assertJson(self.response_all_counts_0, rv.data)

        data = {'email':'3@example.com', 'password': 'password'}
        # post request for user login with for user3, member of
        # admin role
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)
        rv = self.app.get(url_format % (datetime(2000,1,1).isoformat(),
                                        datetime(2000,2,1).isoformat()))

        # this should succeed with 200 as user3 is member of admin role
        self.assertEqual(200, rv.status_code)
        self.assertJson(self.response_all_counts_0, rv.data)

    def test_user_permissions_for_utilbill_flagging(self):
        data = {'email':'2@example.com', 'password': 'password'}
        # post request for user login with for user2, member of no role
        self.app.post('/userlogin',
                      content_type='multipart/form-data', data=data)

        url_format = self.URL_PREFIX + 'flagged_utilitybills'
        rv = self.app.get(url_format)
        # this should result in a status_code of '403 permission denied'
        # as only members of 'Project Manager' or 'admin' role are allowed
        # access to report page and user2 is member of niether one
        self.assertEqual(403, rv.status_code)

        data = {'email':'1@example.com', 'password': 'password'}
        # post request for user login with for user1, member of
        # Project Manager role
        self.app.post('/userlogin',
                      content_type='multipart/form-data', data=data)

        rv = self.app.get(url_format)
        # this should succeed with 200 as user1 is member of Project Manager
        # Role
        self.assertEqual(200, rv.status_code)
        self.assertJson(self.response_no_flagged_bills, rv.data)

        data = {'email':'3@example.com', 'password': 'password'}
        # post request for user login with for user3, member of
        # admin role
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)
        rv = self.app.get(url_format)

        # this should succeed with 200 as user3 is member of admin role
        self.assertEqual(200, rv.status_code)
        self.assertJson(self.response_no_flagged_bills, rv.data)

    def test_report_flagged_utilbills(self):
        # log in as project manager
        data = {'email':'1@example.com', 'password': 'password'}
        self.app.post('/userlogin',
                      content_type='multipart/form-data', data=data)
        url_format = self.URL_PREFIX + 'flagged_utilitybills'

        # no bills flagged yet
        rv = self.app.get(url_format)
        self.assertJson(self.response_no_flagged_bills, rv.data)

        # flag two bills
        self.ub1.flag()
        self.ub2.flag()
        rv = self.app.get(url_format)
        self.assertJson({
            "results": 2,
            'rows': [{
                'computed_total': 0,
                'due_date': None,
                'id': 2,
                'meter_identifier': 'MNOPQR',
                'next_meter_read_date': None,
                'pdf_url': '',
                'period_end': None,
                'period_start': None,
                'processed': False,
                'rate_class': self.some_electric_rate_class.name,
                'rate_class_id': self.some_electric_rate_class.id,
                'service': 'Electric',
                'service_address': '2 Example St., ,  ',
                'supplier': 'Unknown',
                'supplier_id': None,
                'supply_group': 'Unknown',
                'supply_group_id': None,
                'supply_total': 0,
                'target_total': 0,
                'total_energy': 250.0,
                'utility': 'Example Utility',
                'utility_id': 1,
                'utility_account_id': 1,
                'utility_account_number': '1',
                'supply_choice_id': None,
                'wiki_url': 'http://example.com/utility:Example Utility',
                'entered': False,
                'flagged': True,
                'tou': False
            }, {
                'computed_total': 0,
                'due_date': None,
                'id': 1,
                'meter_identifier': 'GHIJKL',
                'next_meter_read_date': None,
                'pdf_url': '',
                'period_end': None,
                'period_start': None,
                'processed': False,
                'rate_class': self.some_rate_class.name,
                'rate_class_id': self.some_rate_class.id,
                'service': 'Gas',
                'service_address': '1 Example St., ,  ',
                'supplier': 'Unknown',
                'supplier_id': None,
                'supply_group': 'Unknown',
                'supply_group_id': None,
                'supply_total': 0,
                'target_total': 0,
                'total_energy': 150.0,
                'utility': 'Example Utility',
                'utility_id': 1,
                'utility_account_id': 1,
                'utility_account_number': '1',
                'supply_choice_id': None,
                'wiki_url': 'http://example.com/utility:Example Utility',
                'entered': False,
                'flagged': True,
                'tou': False
            }]}, rv.data)

        # Unflag one bill
        self.ub2.un_flag()
        rv = self.app.get(url_format)
        self.assertJson({
            "results": 1,
            'rows': [{
                'computed_total': 0,
                'due_date': None,
                'id': 1,
                'meter_identifier': 'GHIJKL',
                'next_meter_read_date': None,
                'pdf_url': '',
                'period_end': None,
                'period_start': None,
                'processed': False,
                'rate_class': self.some_rate_class.name,
                'rate_class_id': self.some_rate_class.id,
                'service': 'Gas',
                'service_address': '1 Example St., ,  ',
                'supplier': 'Unknown',
                'supplier_id': None,
                'supply_group': 'Unknown',
                'supply_group_id': None,
                'supply_total': 0,
                'target_total': 0,
                'total_energy': 150,
                'utility': 'Example Utility',
                'utility_id': 1,
                'utility_account_id': 1,
                'utility_account_number': '1',
                'supply_choice_id': None,
                'wiki_url': 'http://example.com/utility:Example Utility',
                'entered': False,
                'flagged': True,
                'tou': False
            }]}, rv.data)

    def test_report_utilbills_for_user(self):
        url_format = self.URL_PREFIX + 'user_utilitybills?start=%s&end=%s&id=%s'

        # no "entered" bills yet
        start = datetime(2000, 1, 5)
        end = datetime(2000, 1, 11)
        rv = self.app.get(url_format % (start.isoformat(),
                                        end.isoformat(),
                                        self.user1.id))
        self.assertJson({"results": 0, "rows": []}, rv.data)

        # one "entered bill for user1
        self.ub1.enter(self.user1, datetime(2000,1,10))
        rv = self.app.get(url_format % (start.isoformat(),
                                        end.isoformat(),
                                        self.user1.id))
        self.assertJson(
            {"results": 1,
             'rows':
                 [{'computed_total': 0,
                  'due_date': None,
                  'id': 1,
                  'next_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': self.some_rate_class.name,
                  'rate_class_id': self.some_rate_class.id,
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supplier_id': None,
                  'supply_group': 'Unknown',
                  'supply_group_id': None,
                  'supply_total': 0,
                  'target_total': 0,
                  'total_energy': 150.0,
                  'utility': 'Example Utility',
                  'utility_id': 1,
                  'utility_account_id': 1,
                  'utility_account_number': '1',
                  'supply_choice_id': None,
                  'wiki_url': 'http://example.com/utility:Example Utility',
                  'entered': True,
                  'flagged': False,
                  'meter_identifier': 'GHIJKL',
                  'tou': False
                 }],
             }, rv.data)

        # still none for user2
        rv = self.app.get(url_format % (start.isoformat(),
                                        end.isoformat(),
                                        self.user2.id))
        self.assertJson({"results": 0, "rows": []}, rv.data)


class TestReplaceUtilBillWithBEUtilBill(BillEntryIntegrationTest,
                                        unittest.TestCase):

    def test_replace_utilbill_with_beutilbill(self):
        s = Session()
        u = UtilBill(self.ua1, self.utility, self.some_rate_class)
        s.add(u)
        s.flush() # set u.id

        self.assertEqual(1, s.query(UtilBill).filter_by(id=u.id).count())
        self.assertEqual(0, s.query(BEUtilBill).filter_by(id=u.id).count())

        # replace_utilbill_with_beutilbill does not have to destroy
        # utilbill.id, but it may
        original_id = u.id

        # load charges and registers while 'utilbill' is still valid, so they
        # can be compared below
        u.charges, u.registers

        new_beutilbill = replace_utilbill_with_beutilbill(u)
        self.assertEqual(original_id, new_beutilbill.id)

        # new_beutilbill has the same id, because it corresponds to the same
        # database row
        query_result = s.query(UtilBill).filter_by(id=original_id).one()
        self.assertIs(new_beutilbill, query_result)
        self.assertIsInstance(new_beutilbill, BEUtilBill)
        self.assertEqual(BEUtilBill.POLYMORPHIC_IDENTITY,
                         new_beutilbill.discriminator)

        # foreign keys and child objects are the same
        self.assertEqual(u.billing_address_id,
                         new_beutilbill.billing_address_id)
        self.assertEqual(u.service_address_id,
                         new_beutilbill.service_address_id)
        self.assertEqual(u.billing_address.id,
                         new_beutilbill.billing_address.id)
        self.assertEqual(u.service_address.id,
                         new_beutilbill.service_address.id)
        self.assertEqual(u.billing_address, new_beutilbill.billing_address)
        self.assertEqual(u.service_address, new_beutilbill.service_address)
        self.assertEqual(u.charges, new_beutilbill.charges)
        self.assertEqual([c.id for c in u.charges],
                         [c.id for c in new_beutilbill.charges])
        self.assertEqual([r.id for r in u.registers],
                         [r.id for r in new_beutilbill.registers])

        # also the child objects should really exist in the database
        self.assertEqual(1, s.query(Address).filter_by(
            id=new_beutilbill.billing_address_id).count())
        self.assertEqual(1, s.query(Address).filter_by(
            id=new_beutilbill.service_address_id).count())

class TestAccountHasBillsForDataEntry(unittest.TestCase):

    def test_account_has_bills_for_data_entry(self):
        utility = Utility(name='Empty Utility')
        utility_account = UtilityAccount('Account 2', '22222', utility, None,
                                         None, Address(), Address(), '2')

        regular_utilbill = UtilBill(utility_account, utility, None,
                       service_address=Address(street='2 Example St.'))
        beutilbill = BEUtilBill(utility_account, utility, None,
                                service_address=Address(street='2 Example St.'))

        utility_account.utilbills = []
        self.assertFalse(account_has_bills_for_data_entry(utility_account))

        utility_account.utilbills = [regular_utilbill]
        self.assertFalse(account_has_bills_for_data_entry(utility_account))

        utility_account.utilbills = [regular_utilbill, beutilbill]
        self.assertTrue(account_has_bills_for_data_entry(utility_account))

        utility_account.utilbills = [beutilbill]
        self.assertTrue(account_has_bills_for_data_entry(utility_account))

        beutilbill.enter(BillEntryUser(Mock(autospecs=BillEntryUser)),
                         datetime.utcnow())
        self.assertFalse(account_has_bills_for_data_entry(utility_account))


class TestUtilBillGUIDAMQP(unittest.TestCase):

    def setUp(self):
        super(TestUtilBillGUIDAMQP, self).setUp()

        # parameters for real RabbitMQ connection are stored but never used so
        # there is no actual connection
        exchange_name, routing_key, amqp_connection_parameters, \
                = create_amqp_conn_params()

        self.utilbill = Mock(autospec=UtilBill)
        self.utilbill.discriminator = UtilBill.POLYMORPHIC_IDENTITY
        self.core_altitude_module = Mock(autospec=altitude)
        self.billentry_common_module = Mock(autospec=common)
        self.guid = '5efc8f5a-7cca-48eb-af58-7787348388c5'

        self.handler = ConsumeUtilbillGuidsHandler(
            exchange_name, routing_key, amqp_connection_parameters,
            self.core_altitude_module, self.billentry_common_module)

        # We don't have to wait for the rabbitmq connection to close,
        # since we're never instatiating a connection
        self.handler._wait_on_close = 0

        # these are for creating IncomingMessage objects for 'handler' to
        # handle
        _, method, props = create_mock_channel_method_props()
        self.mock_method = method
        self.mock_props = props

    def test_process_utilbill_guid_with_no_matching_guid(self):
        message = create_channel_message_body(dict(
            message_version=[1, 0],
            guid='3e7f9bf5-f729-423c-acde-58f6174df551'))
        message_obj = IncomingMessage(self.mock_method, self.mock_props,
                                      message)
        self.core_altitude_module.get_utilbill_from_guid.side_effect = \
            NoResultFound
        self.assertRaises(NoResultFound, self.handler.handle, message_obj)
        self.billentry_common_module.replace_utilbill_with_beutilbill.has_calls(
            [])

    def test_process_utilbill_guid_with_matching_guid(self):
        message = create_channel_message_body(dict(
            message_version=[1, 0],
            guid=self.guid))
        message_obj = IncomingMessage(self.mock_method, self.mock_props,
                                      message)
        self.core_altitude_module.get_utilbill_from_guid.return_value = \
            self.utilbill
        self.handler.handle(message_obj)
        self.billentry_common_module.replace_utilbill_with_beutilbill\
                .assert_called_once_with(self.utilbill)


class TestBillEntryUserSessions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()
        billentry.app.config['LOGIN_DISABLED'] = False
        billentry.app.config['TRAP_HTTP_EXCEPTIONS'] = True
        billentry.app.config['TESTING'] = True
        cls.app = billentry.app.test_client()

        from core import config
        cls.authorize_url = config.get('billentry', 'authorize_url')

    def setUp(self):
        init_test_config()
        clear_db()
        s = Session()
        user = BillEntryUser(email='user1@test.com', password='password')
        s.add(user)
        s.commit()

    def tearDown(self):
        clear_db()

    def test_session_duration(self):
        current_timestamp = datetime.utcnow()
        # valid data for user login
        data = {'email':'user1@test.com', 'password': 'password'}\
        # post request for user login with valid credentials
        self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)
        # a BEUserSession object must exist for this user after a
        # successfull login
        user = Session().query(BillEntryUser).filter_by(email='user1@test.com').first()
        be_user_session = Session().query(BEUserSession).filter_by(beuser=user).all()
        self.assertEqual(len(be_user_session), 1)

        # both session_start and last_request are updated at user login so
        # the difference between their timestamps and current_timestamp
        # must be greater than 0
        self.assertNotEquals(0, be_user_session[0].session_start - current_timestamp)
        self.assertNotEquals(0, be_user_session[0].last_request - current_timestamp)

        last_request_timestamp = be_user_session[0].last_request
        # make another request to update the last_request field as the
        # timestamp for last_request is updated on every request
        self.app.get('/')
        self.assertNotEquals(0, be_user_session[0].last_request - last_request_timestamp)

        last_request_timestamp =  be_user_session[0].last_request
        # logout closes the current session
        self.app.get('/logout')
        self.assertNotEquals(0, be_user_session[0].last_request - last_request_timestamp)
        self.assertEqual((be_user_session[0].last_request -
                          be_user_session[0].session_start).
                         total_seconds(), user.get_beuser_billentry_duration
                        (current_timestamp, datetime.utcnow()))

        #start a new session by logging in
        self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)
        current_timestamp = datetime.utcnow()
        user_sessions = Session().query(BEUserSession).filter_by(beuser=user).all()
        # count of sessione should be two now that another login request has been made
        self.assertEqual(2, len(user_sessions))
        # the session duration for current session should be 0 as both
        # session_start and last_request have the same values
        self.assertEqual(0, user.get_beuser_billentry_duration(current_timestamp, datetime.utcnow()))


class TestBillEnrtyAuthentication(unittest.TestCase):
    URL_PREFIX = 'http://localhost'

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()
        billentry.app.config['LOGIN_DISABLED'] = False
        billentry.app.config['TRAP_HTTP_EXCEPTIONS'] = True
        billentry.app.config['TESTING'] = True
        cls.app = billentry.app.test_client()

        from core import config
        cls.authorize_url = config.get('billentry', 'authorize_url')

    def setUp(self):
        init_test_config()
        clear_db()
        s = Session()
        user = BillEntryUser(email='user1@test.com', password='password')
        s.add(user)
        s.commit()

    def tearDown(self):
        clear_db()

    def test_oauth_login(self):
        # just an example of a URL the user was trying to go to
        original_url = '/admin'

        # first the user tries to go to 'original_url' and 401 is returned
        rv = self.app.get(original_url)
        self.assertEqual(302, rv.status_code)
        self.assertEqual(self.URL_PREFIX + '/login-page', rv.location)

        # then the user clicks on the "Log in with Google" link, whose URL is
        #  /login, and gets redirected to Google's OAuth URL
        rv = self.app.get('/login')
        self.assertEqual(302, rv.status_code)
        # not checking arguments in the URL
        self.assertTrue(rv.location.startswith(self.authorize_url))

        # /oauth2callback is the URL that Google redirects to after the user
        # authenticates. we aren't simulating the valid OAuth data that
        # Google would provide, so the response is invalid
        rv = self.app.get('/oauth2callback')
        self.assertEqual(302, rv.status_code)
        self.assertEqual(self.URL_PREFIX + '/login-page', rv.location)

        # after unsuccessful login, the user still can't get to a normal page
        rv = self.app.get('/')
        self.assertEqual(302, rv.status_code)
        self.assertEqual(self.URL_PREFIX + '/login-page', rv.location)

    def test_local_login(self):
        response = self.app.get('/')
        # because user is not logged in so a redirect to login-page should
        # happen
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.URL_PREFIX + '/login-page', response.location)

        # valid data for user login
        data = {'email':'user1@test.com', 'password': 'password'}\
        # post request for user login with valid credentials
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)

        self.assertTrue(response.status_code == 302)
        self.assertEqual('http://localhost/', response.location)

        # user successfully gets index.html
        response = self.app.get(self.URL_PREFIX + '/')
        self.assertEqual(200, response.status_code)

        # logout user
        self.app.get('/logout')

        # TODO: when a user gets redirected to the login page,
        # test redirection to the page the user originally wanted to go to.

        response = self.app.get('/')
        # because user is not logged in so a 401 is returned
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.URL_PREFIX + '/login-page', response.location)

        # invalid email for user login
        data = {'email':'user2@test.com', 'password': 'password'}

        # post request for user login with invalid credentials
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)

        # the login should fail and user should be redirected to login page
        self.assertEqual(response.status_code, 302)
        self.assertEqual('http://localhost/login-page', response.location)

        # invalid password for user login
        data = {'email':'user1@test.com', 'password': 'password1'}

        # post request for user login with invalid credentials
        response = self.app.post('/userlogin',
                                 content_type='multipart/form-data', data=data)
        # the login should fail and user should be redirected to login page
        self.assertEqual(response.status_code, 302)
        self.assertEqual('http://localhost/login-page', response.location)



