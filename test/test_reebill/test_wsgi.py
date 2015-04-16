from test.setup_teardown import TestCaseWithSetup, clear_db
from test.testing_utils import TestCase, ReebillRestTestClient
from test.setup_teardown import create_reebill_resource_objects
from test import init_test_config
from core import init_model
from core.model import Session, UtilityAccount
from reebill.reebill_model import ReeBillCustomer
from reebill.wsgi import AccountsResource
from reebill.reebill_dao import ReeBillDAO
from reebill.payment_dao import PaymentDAO
from reebill.users import UserDAO
from reebill.bill_mailer import Mailer
from reebill.journal import JournalDAO
from skyliner.mock_skyliner import MockSplinter
from reebill import fetch_bill_data as fbd
import pymongo
import mongoengine
import logging


def setUpModule():
    init_test_config()
    init_model()
    mongoengine.connect('test', host='localhost', port=27017, alias='journal')


class AccountsResourceTest(TestCase):

    def setUp(self):
        from core import config
        self.database = 'test'
        # Clear out mongo database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)
        clear_db()
        TestCaseWithSetup.insert_data()
        resource = AccountsResource(*create_reebill_resource_objects())
        self.app = ReebillRestTestClient('accounts', resource)

    def tearDown(self):
        clear_db()
        # Clear out mongo database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)

    def test_put(self):
        session = Session()
        utility_account = session.query(UtilityAccount).filter_by(
            account='99999').one()
        reebill_customer = session.query(ReeBillCustomer).filter_by(
            utility_account_id=utility_account.id).one()

        ###############################
        # Update Utility Account Number
        self.assertEqual(utility_account.account_number, '1')
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'utility_account_number': '987654321',
                'utility_account_id': utility_account.id
            }
        )
        self.assertTrue(success)
        self.assertEqual(response, {'results': 1, 'rows': [{
            'utility_account_id': utility_account.id,
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_utility_name': 'Test Utility Company Template',
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '987654321',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': '',
        }]})
        self.assertEqual(utility_account.account_number, '987654321')

        ###############################
        # Update tags
        self.assertEqual(reebill_customer.get_groups(), [])
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'tags': 'some tag, some other tag',
                'utility_account_id': utility_account.id
            }
        )
        self.assertTrue(success)
        self.assertEqual(response, {'results': 1, 'rows': [{
            'utility_account_id': utility_account.id,
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_utility_name': 'Test Utility Company Template',
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '987654321',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': 'some tag,some other tag',
        }]})
        self.assertEqual([g.name for g in reebill_customer.get_groups()],
                         ['some tag', 'some other tag'])

        # Assert Input is properly sanitized by server
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'tags': 'some other tag , one more tag , ',
                'utility_account_id': utility_account.id
            }
        )
        self.assertTrue(success)
        self.assertEqual(response, {'results': 1, 'rows': [{
            'utility_account_id': utility_account.id,
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_utility_name': 'Test Utility Company Template',
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '987654321',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': 'some other tag,one more tag',
        }]})
        self.assertEqual([g.name for g in reebill_customer.get_groups()],
                         ['some other tag', 'one more tag'])