"""All tests for the Bill Entry application.
"""
from datetime import datetime, date
import unittest
from json import loads
from flask import url_for
from flask.ext.login import current_user
from mock import Mock

# if init_test_config() is not called before "billentry" is imported,
# "billentry" will call init_config to initialize the config object with the
# non-test config file. so init_test_config must be called before
# "billentry" is imported.
from test import init_test_config
init_test_config()

import billentry
from billentry.billentry_model import BillEntryUser, BEUtilBill
from billentry.common import replace_utilbill_with_beutilbill

from core import init_model
from core.model import Session, UtilityAccount, Address, UtilBill, Utility,\
    Charge, Register, RateClass
from brokerage.brokerage_model import BrokerageAccount
from test.setup_teardown import TestCaseWithSetup


class TestBEUtilBill(unittest.TestCase):
    """Unit test for BEUtilBill.
    """
    def setUp(self):
        self.utility = Mock(autospec=Utility)
        self.rate_class = Mock(autospec=RateClass)
        self.ua = UtilityAccount('Account 1', '11111', self.utility, None, None,
                            Address(), Address(), '1')
        self.user = Mock(autospec=BillEntryUser)
        self.ub = BEUtilBill(self.ua, UtilBill.Complete, self.utility, None,
                             self.rate_class, Address(), Address())

    def test_create_from_utilbill(self):
        utilbill = UtilBill(self.ua, UtilBill.Complete, self.utility, None,
                             self.rate_class, Address(), Address())
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

        self.ub.un_enter()
        self.assertEqual(None, self.ub.get_date())
        self.assertEqual(None, self.ub.get_user())
        self.assertFalse(self.ub.is_entered())

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
            expected = loads(expected)
        if isinstance(actual, basestring):
            actual = loads(actual)
        self.assertEqual(expected, actual)

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()
        billentry.app.config['TESTING'] = True
        # TESTING is supposed to imply LOGIN_DISABLED if the Flask-Login "login_required" decorator is used, but we
        # are using the before_request callback instead
        billentry.app.config['LOGIN_DISABLED'] = True
        # TODO: this should prevent the method decorated with
        # "app.errorhandler" from running, but doesn't
        billentry.app.config['TRAP_HTTP_EXCEPTIONS'] = True
        cls.app = billentry.app.test_client()

    def setUp(self):
        TestCaseWithSetup.truncate_tables()

        # TODO: this should not have to be done multiple times, but removing it
        # causes a failure when the session is committed below.
        init_model()

        self.utility = Utility('Example Utility', Address())
        self.utility.id = 1
        self.ua1 = UtilityAccount('Account 1', '11111', self.utility, None, None,
                                  Address(), Address(), '1')
        self.ua1.id = 1
        self.rate_class = RateClass('Some Rate Class', self.utility, 'gas')
        self.ub1 = BEUtilBill(self.ua1, self.utility, self.rate_class,
                              service_address=Address(street='1 Example St.'))
        self.ub2 = BEUtilBill(self.ua1, self.utility, None,
                            service_address=Address(street='2 Example St.'))
        self.ub1.id = 1
        self.ub2.id = 2
        s = Session()
        s.add_all([self.utility, self.ua1, self.rate_class, self.ub1, self.ub2])
        s.commit()
        # TODO: add more database objects used in multiple subclass setUps

    def tearDown(self):
        TestCaseWithSetup.truncate_tables()

class TestBillEntryMain(BillEntryIntegrationTest, unittest.TestCase):
    """Integration tests using REST request handlers related to Bill Entry main
    page.
    BillEntryIntegrationTest must be the first superclass for super() to work.
    """
    def setUp(self):
        super(TestBillEntryMain, self).setUp()

        s = Session()
        utility1 = Utility('Empty Utility', Address())
        utility2 = Utility('Some Other Utility',  Address())
        ua2 = UtilityAccount('Account 2', '22222', self.utility, None, None,
                             Address(), Address(), '2')
        ua3 = UtilityAccount('Not PG', '33333', self.utility, None, None,
                             Address(), Address(), '3')
        rate_class1 = RateClass('Other Rate Class', self.utility, 'electric')
        s.add_all([self.rate_class, rate_class1])
        ua2.id, ua3.id = 2, 3
        utility1.id, utility2.id = 2, 10
        s.add_all([self.utility, utility1, utility2, ua2, ua3,
                   BrokerageAccount(self.ua1), BrokerageAccount(ua2)])
        ub3 = UtilBill(ua3, utility1, None,
                       service_address=Address(street='2 Example St.'))
        ub3.id = 3

        register1 = Register(self.ub1, "ABCDEF description",
                "ABCDEF", 'therms', False, "total", None, "GHIJKL",
                quantity=150,
                register_binding='REG_TOTAL')
        register2 = Register(self.ub2, "ABCDEF description",
                "ABCDEF", 'therms', False, "total", None, "GHIJKL",
                quantity=150,
                register_binding='REG_TOTAL')
        s.add_all([register1, register2])
        self.ub1.registers = [register1]
        self.ub2.registers = [register2]

        c1 = Charge(self.ub1, 'CONSTANT', 0.4, '100', unit='dollars',
                    type='distribution', target_total=1)
        c2 = Charge(self.ub1, 'LINEAR', 0.1, 'REG_TOTAL.quantity * 3',
                    unit='therms', type='supply', target_total=2)
        c3 = Charge(self.ub2, 'LINEAR_PLUS_CONSTANT', 0.1,
                    'REG_TOTAL.quantity * 2 + 10', unit='therms',
                    type='supply')
        c4 = Charge(self.ub2, 'BLOCK_1', 0.3, 'min(100, REG_TOTAL.quantity)',
                    unit='therms', type='distribution')
        c5 = Charge(self.ub2, 'BLOCK_2', 0.4,
                    'min(200, max(0, REG_TOTAL.quantity - 100))',
                    unit='dollars', type='supply')
        c1.id, c2.id, c3.id, c4.id, c5.id = 1, 2, 3, 4, 5
        s.add_all([c1, c2, c3, c4, c5, ub3])
        s.commit()

    def test_accounts(self):
        rv = self.app.get(self.URL_PREFIX + 'accounts')
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
        rv = self.app.get(self.URL_PREFIX + 'utilitybills?id=3')
        self.assertJson(
            {'results': 1,
             'rows': [
                 {'account': None,
                  'computed_total': 0.0,
                  'due_date': None,
                  'id': 3,
                  'next_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Unknown',
                  'service': 'Unknown',
                  'service_address': '2 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 0.0,
                  'target_total': 0.0,
                  'total_energy': 0.0,
                  'utility': 'Empty Utility',
                  'utility_account_number': '3',
                  'supply_choice_id': None,
                  'wiki_url': 'http://example.com/utility:Empty Utility'
                 },
             ], }, rv.data)

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
             {'account': None,
              'computed_total': 85.0,
              'due_date': None,
              'id': 1,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': '2000-01-01',
              'processed': False,
              'rate_class': 'Some Rate Class',
              'service': 'Gas',
              'service_address': '1 Example St., ,  ',
              'supplier': 'Unknown',
              'supply_choice_id': None,
              'supply_total': 2.0,
              'target_total': 0.0,
              'total_energy': 150.0,
              'utility': 'Example Utility',
              'utility_account_number': '1',
              'wiki_url': 'http://example.com/utility:Example Utility'
              },
         'results': 1}

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
            id=2,
            period_start=datetime(2000, 1, 1).isoformat()
        ))
        expected['rows']['period_start'] = '2000-01-01'
        self.assertJson(expected, rv.data)

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
            id=2,
            next_meter_read_date=date(2000, 2, 5).isoformat()
        ))
        expected['rows']['next_meter_read_date'] = None
        self.assertJson(expected, rv.data)

        # TODO: why aren't there tests for editing all the other fields?

    def test_update_utilbill_rate_class(self):
        expected = {'results': 1,
         'rows': [
             {'account': None,
              'computed_total': 0.0,
              'due_date': None,
              'id': 3,
              'next_meter_read_date': None,
              'pdf_url': '',
              'period_end': None,
              'period_start': None,
              'processed': False,
              'rate_class': 'Unknown',
              'service': 'Unknown',
              'service_address': '2 Example St., ,  ',
              'supplier': 'Unknown',
              'supply_total': 0.0,
              'target_total': 0.0,
              'total_energy': 0.0,
              'utility': 'Empty Utility',
              'utility_account_number': '3',
              'supply_choice_id': None,
              'wiki_url': 'http://example.com/utility:Empty Utility'
             }
         ], }
        rv = self.app.get(self.URL_PREFIX + 'utilitybills?id=3')
        self.assertJson(expected, rv.data)

        # TODO reuse 'expected' in later assertions instead of repeating the
        # giant dictionary over and over

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
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
                  'due_date': None,
                  'next_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Some Rate Class',
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 2.0,
                  'target_total': 0.0,
                  'total_energy': 150.0,
                  'utility': 'Empty Utility',
                  'utility_account_number': '1',
                  'supply_choice_id': None,
                  'wiki_url': 'http://example.com/utility:Empty Utility'
            },
            }, rv.data
        )

        rv = self.app.put(self.URL_PREFIX + 'utilitybills/1', data=dict(
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
                  'due_date': None,
                  'next_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Some Rate Class',
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 2.0,
                  'target_total': 0.0,
                  'total_energy': 150.0,
                  'utility': 'Some Other Utility',
                  'utility_account_number': '1',
                  'supply_choice_id': None,
                  'wiki_url': 'http://example.com/utility:Some Other Utility'
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
        self.user1 = BillEntryUser(email='user1@example.com', )
        self.user2 = BillEntryUser(email='user2@example2.com')
        s.add_all([self.ub1, self.ub2, self.user1, self.user2])
        s.commit()

    def test_report_count_for_user(self):
        url_format = self.URL_PREFIX + 'users_counts?start=%s&end=%s'

        # no "entered" bills yet
        rv = self.app.get(url_format % (datetime(2000,1,1).isoformat(),
                                        datetime(2000,2,1).isoformat()))
        self.assertJson({"results": 2,
                         "rows": [{"user_id": self.user1.id, "count": 0},
                                  {"user_id": self.user2.id, "count": 0}]},
                        rv.data)

        self.ub1.enter(self.user1, datetime(2000,1,10))
        self.ub2.enter(self.user1, datetime(2000,1,20))

        # no bills in range
        rv = self.app.get(url_format % (datetime(2000,1,11).isoformat(),
                                        datetime(2000,1,20).isoformat()))
        self.assertJson({"results": 2,
                         "rows": [{"user_id": self.user1.id, "count": 0},
                                  {"user_id": self.user2.id, "count": 0}]},
                        rv.data)

        # user1 has 2 bills in range, user2 has none
        rv = self.app.get(url_format % (datetime(2000,1,10).isoformat(),
                                        datetime(2000,1,21).isoformat()))
        self.assertJson({"results": 2,
                         "rows": [{"user_id": self.user1.id, "count": 2},
                                  {"user_id": self.user2.id, "count": 0}]

                        }, rv.data)

    def test_report_utilbills_for_user(self):
        url_format = self.URL_PREFIX + 'user_utilitybills/%s'

        # no "entered" bills yet
        rv = self.app.get(url_format % self.user1.id)
        self.assertJson({"results": 0, "rows": []}, rv.data)

        # one "entered bill for user1
        self.ub1.enter(self.user1, datetime(2000,1,10))
        rv = self.app.get(url_format % self.user1.id)
        self.assertJson(
            {"results": 1,
             'rows':
                 [{'account': None,
                  'computed_total': 0,
                  'due_date': None,
                  'id': 1,
                  'next_meter_read_date': None,
                  'pdf_url': '',
                  'period_end': None,
                  'period_start': None,
                  'processed': False,
                  'rate_class': 'Some Rate Class',
                  'service': 'Gas',
                  'service_address': '1 Example St., ,  ',
                  'supplier': 'Unknown',
                  'supply_total': 0,
                  'target_total': 0,
                  'total_energy': 0,
                  'utility': 'Example Utility',
                  'utility_account_number': '1',
                  'supply_choice_id': None,
                  'wiki_url': 'http://example.com/utility:Example Utility'
                 }],
             }, rv.data)

        # still none for user2
        rv = self.app.get(url_format % self.user2.id)
        self.assertJson({"results": 0, "rows": []}, rv.data)


class TestReplaceUtilBillWithBEUtilBill(BillEntryIntegrationTest,
                                        unittest.TestCase):

    def test_replace_utilbill_with_beutilbill(self):
        s = Session()
        u = UtilBill(self.ua1, self.utility, self.rate_class)
        s.add(u)
        s.flush() # set u.id

        self.assertEqual(1, s.query(UtilBill).filter_by(id=u.id).count())
        self.assertEqual(0,
                         s.query(BEUtilBill).filter_by(id=u.id).count())

        the_id = u.id
        new_beutilbill = replace_utilbill_with_beutilbill(u)

        # note that new_beutilbill has the same id
        query_result = s.query(UtilBill).filter_by(id=the_id).one()
        self.assertIsNone(u.id)
        self.assertIs(new_beutilbill, query_result)
        self.assertIsInstance(new_beutilbill, BEUtilBill)
        self.assertEqual(BEUtilBill.POLYMORPHIC_IDENTITY,
                         new_beutilbill.discriminator)

class TestBillEnrtyAuthentication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()
        billentry.app.config['LOGIN_DISABLED'] = False
        cls.app = billentry.app.test_client()

    def setUp(self):
        TestCaseWithSetup.truncate_tables()
        s = Session()
        user = BillEntryUser(email='user1@test.com', password='password')
        s.add(user)
        s.commit()

    def tearDown(self):
        TestCaseWithSetup.truncate_tables()

    def test_user_login(self):
        response = self.app.get('/')
        # because user is not logged in so a redirect to login-page should
        # happen
        self.assertEqual(response.status_code, 302)
        self.assertEqual('http://localhost/login-page', response.location)
        # valid data for user login
        data = {'email':'user1@test.com', 'password': 'password'}\
        # post request for user login with valid credentials
        response = self.app.post('/userlogin?next=admin', content_type='multipart/form-data',
                                                    data=data)

        # on successful login user is routed to the next url
        self.assertTrue(response.status_code == 302)
        self.assertEqual ('http://localhost/admin', response.location)

        # logout user
        self.app.get('/logout')

        response = self.app.get('/')
        # because user is not logged in so a redirect to login-page should
        # happen
        self.assertEqual(response.status_code, 302)
        self.assertEqual('http://localhost/login-page', response.location)

        self.assertEqual('http://localhost/login-page', response.location)

        # invalid email for user login
        data = {'email':'user2@test.com', 'password': 'password'}

        # post request for user login with invalid credentials
        response = self.app.post('/userlogin', content_type='multipart/form-data',
                                                    data=data)
        # the login should fail and user should be redirected to login-page
        self.assertEqual(response.status_code, 302)
        self.assertEqual('http://localhost/login-page', response.location)

        # invalid password for user login
        data = {'email':'user1@test.com', 'password': 'password1'}

        # post request for user login with invalid credentials
        response = self.app.post('/userlogin', content_type='multipart/form-data',
                                                    data=data)
        # the login should fail and user should be redirected to login-page
        self.assertEqual(response.status_code, 302)
        self.assertEqual('http://localhost/login-page', response.location)



