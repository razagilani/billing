import pymongo
import mongoengine
from datetime import date
from unittest import TestCase
from test.setup_teardown import TestCaseWithSetup
from test.testing_utils import ReebillRestTestClient
from test.setup_teardown import create_reebill_resource_objects
from test import init_test_config, create_tables, clear_db
from core import init_model, init_config
from core.model import Session, UtilityAccount, Address, Utility, Supplier, \
    RateClass
from core.model.utilbill import UtilBill
from reebill.reebill_model import ReeBillCustomer, ReeBill
from reebill.wsgi import AccountsResource, IssuableReebills


def setUpModule():
    init_test_config()
    create_tables()
    init_model()
    mongoengine.connect('test', host='localhost', port=27017, alias='journal')


class IssuableReebillsTest(TestCase):

    def setUp(self):
        self.database = 'test'
        # Clear out mongo database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)
        clear_db()
        TestCaseWithSetup.insert_data()

        # Set up the test client
        resource = IssuableReebills(*create_reebill_resource_objects())
        self.app = ReebillRestTestClient('issuable', resource)

        blank_address = Address()
        test_utility = Utility(name='FB Test Utility Name',
                               address=blank_address)
        utility_account = UtilityAccount(
            'someaccount', '99999', test_utility, None, None, blank_address,
            blank_address)
        utility_account.id = 1
        utility_account2 = UtilityAccount(
            'someaccount', '99998', test_utility, None, None, blank_address,
            blank_address)
        utility_account2.id = 2
        reebill_customer = ReeBillCustomer(
            bill_email_recipient='example1@example.com',
            utility_account=utility_account
        )
        reebill_customer2 = ReeBillCustomer(
            bill_email_recipient='example2@example.com',
            utility_account=utility_account2
        )


        session = Session()
        ub1 = UtilBill(utility_account, test_utility, None,
                       period_start=date(2011, 1, 1),
                       period_end=date(2011, 2, 1), processed=True)
        rb1 = ReeBill(reebill_customer, 1, utilbill=ub1)
        rb1.issued = True
        rb1.processed = True
        rb1_1 = ReeBill(reebill_customer, 1, version=1, utilbill=ub1)
        rb1_1.processed = True
        ub2 = UtilBill(utility_account, test_utility, None,
            period_start=date(2011, 2, 1),
            period_end=date(2011, 3, 1), processed=True)
        rb2 = ReeBill(reebill_customer, 2, utilbill=ub2)
        rb2.processed = True
        ub3 = UtilBill(utility_account, test_utility, None,
            period_start=date(2012, 12, 1),
            period_end=date(2013, 1, 1), processed=True)
        rb3 = ReeBill(reebill_customer2, 1, utilbill=ub3)
        rb3.processed = True
        session.add_all([rb1, rb1_1, rb2, rb3])

    def tearDown(self):
        clear_db()
        # Clear out mongo database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)

    def test_get(self):
        success, response = self.app.get('/issuable')
        self.assertTrue(success)
        self.assertDictContainsSubset({
            'account': '99999',
            'sequence': 2,
            'mailto': 'example1@example.com'
        }, response['rows'][0])
        self.assertDictContainsSubset({
            'account': '99998',
            'sequence': 1,
            'mailto': 'example2@example.com'
        }, response['rows'][1])


class AccountsResourceTest(TestCase):

    def setUp(self):
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
            'payee': 'payee'
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
            'payee': 'payee'
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
            'payee': 'payee'
        }]})
        self.assertEqual([g.name for g in reebill_customer.get_groups()],
                         ['some other tag', 'one more tag'])