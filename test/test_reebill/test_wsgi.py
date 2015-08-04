import pymongo
import mongoengine
from datetime import date
from unittest import TestCase
from brokerage.brokerage_model import BrokerageAccount
from test.setup_teardown import TestCaseWithSetup, create_reebill_objects
from test.testing_utils import ReebillRestTestClient
from test.setup_teardown import create_reebill_resource_objects
from test import init_test_config, create_tables, clear_db
from core import init_model, init_config
from core.model import Session, UtilityAccount, Address, Utility, Supplier, \
    RateClass, SupplyGroup
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
        utility_account.id = 6
        utility_account2 = UtilityAccount(
            'someaccount', '99998', test_utility, None, None, blank_address,
            blank_address)
        utility_account2.id = 7
        reebill_customer = ReeBillCustomer(
            bill_email_recipient='example1@example.com',
            utility_account=utility_account
        )
        #brokerage_account = BrokerageAccount(utility_account)
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
        session = Session()
        self.database = 'test'
        self.maxDiff = None
        # Clear out mongo database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)
        self.reebill_processor, self.views = create_reebill_objects()
        clear_db()
        #TestCaseWithSetup.insert_data()
        resource = AccountsResource(*create_reebill_resource_objects())
        self.app = ReebillRestTestClient('accounts', resource)
        fa_ba1 = Address(addressee='Test Customer 1 Billing',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        fa_sa1 = Address(addressee='Test Customer 1 Service',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        fa_ba2 = Address(addressee='Test Customer 2 Billing',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                    postal_code='12345')
        fa_sa2 = Address(addressee='Test Customer 2 Service',
                     street='123 Test Street',
                     city='Test City',
                     state='XX',
                     postal_code='12345')
        ub_sa1 = Address(addressee='Test Customer 2 UB 1 Service',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ub_ba1 = Address(addressee='Test Customer 2 UB 1 Billing',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ub_sa2 = Address(addressee='Test Customer 2 UB 2 Service',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ub_ba2 = Address(addressee='Test Customer 2 UB 2 Billing',
                         street='123 Test Street',
                         city='Test City',
                         state='XX',
                         postal_code='12345')
        ca1 = Address(addressee='Test Utilco Address',
                      street='123 Utilco Street',
                      city='Utilco City',
                      state='XX',
                      postal_code='12345')
        supplier = Supplier(name='Test Supplier', address=ca1)
        supply_group = SupplyGroup(name='test', supplier=supplier,
                                   service='gas')
        uc = Utility(name='Test Utility Company Template', address=ca1)
        rate_class = RateClass(name='Test Rate Class Template', utility=uc,
                               service='gas', sos_supply_group=supply_group)
        utility_account = UtilityAccount(
            'Test Customer', '99999', uc, supplier, rate_class, fa_ba1, fa_sa1,
            account_number='1')
        reebill_customer = ReeBillCustomer(name='Test Customer',
                                discount_rate=.12, late_charge_rate=.34,
                                service='thermal',
                                bill_email_recipient='example@example.com',
                                utility_account=utility_account,
                                payee='payee')
        session.add(reebill_customer)
        utility_account2 = UtilityAccount(
            'Test Customer 2', '100000', uc, supplier, rate_class,
            fa_ba2, fa_sa2, account_number='2')
        reebill_customer2 = ReeBillCustomer(name='Test Customer 2',
                                discount_rate=.12, late_charge_rate=.34,
                                service='thermal',
                                bill_email_recipient='example2@example.com',
                                utility_account=utility_account2,
                                payee="Someone Else!")
        u1 = UtilBill(utility_account2, uc,
                             rate_class, supplier=supplier,
                             billing_address=ub_ba1, service_address=ub_sa1,
                             period_start=date(2012, 1, 1),
                             period_end=date(2012, 1, 31),
                             target_total=50.00,
                             date_received=date(2011, 2, 3),
                             processed=True)
        session.add(u1)
        rb1 = ReeBill(reebill_customer2, 1, utilbill=u1)
        session.add(rb1)
        u2 = UtilBill(utility_account2, uc, rate_class, supplier=supplier,
                             billing_address=ub_ba2, service_address=ub_sa2,
                             period_start=date(2012, 2, 1),
                             period_end=date(2012, 2, 28),
                             target_total=65.00,
                             date_received=date(2011, 3, 3),
                             processed=True)
        session.add(u2)
        rb2 = ReeBill(reebill_customer2, 1, utilbill=u2)
        session.add(rb2)

    def tearDown(self):
        clear_db()
        # Clear out mongo database
        mongo_connection = pymongo.Connection()
        mongo_connection.drop_database(self.database)

    def test_put(self):
        self.maxDiff = None
        session = Session()
        utility_account = session.query(UtilityAccount).filter_by(
            account='99999').one()
        utility_account2 = session.query(UtilityAccount).filter_by(
            account='100000').one()
        reebill_customer = session.query(ReeBillCustomer).filter_by(
            utility_account_id=utility_account.id).one()
        account_1_bills = session.query(UtilBill).filter_by(
            utility_account_id=utility_account.id).all()
        account_2_bills = session.query(UtilBill).filter_by(
            utility_account_id=utility_account2.id).all()
        account_1_reebills = session.query(ReeBill).join(ReeBillCustomer).filter(
            ReeBillCustomer.utility_account == utility_account
        ).all()
        account_2_reebills = session.query(ReeBill).join(ReeBillCustomer).filter(
            ReeBillCustomer.utility_account == utility_account2
        ).all()


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
            'brokerage_account': False,
            'reebill_customer': True,
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '987654321',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': '',
            'payee': 'payee',
            'ba_addressee': 'Test Customer 1 Billing',
            'ba_city': 'Test City',
            'ba_postal_code': '12345',
            'ba_state': 'XX',
            'ba_street':'123 Test Street',
            'discount_rate': 0.12,
            'late_charge_rate': 0.34,
            'name': 'Test Customer',
            'sa_addressee': 'Test Customer 1 Service',
            'sa_city': 'Test City',
            'sa_postal_code': '12345',
            'sa_state': 'XX',
            'sa_street': '123 Test Street',
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
            'brokerage_account': False,
            'reebill_customer': True,
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '987654321',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': 'some tag,some other tag',
            'payee': 'payee',
            'ba_addressee': 'Test Customer 1 Billing',
            'ba_city': 'Test City',
            'ba_postal_code': '12345',
            'ba_state': 'XX',
            'ba_street':'123 Test Street',
            'discount_rate': 0.12,
            'late_charge_rate': 0.34,
            'name': 'Test Customer',
            'sa_addressee': 'Test Customer 1 Service',
            'sa_city': 'Test City',
            'sa_postal_code': '12345',
            'sa_state': 'XX',
            'sa_street': '123 Test Street',
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
            'brokerage_account': False,
            'reebill_customer': True,
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '987654321',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': 'some other tag,one more tag',
            'payee': 'payee',
            'ba_addressee': 'Test Customer 1 Billing',
            'ba_city': 'Test City',
            'ba_postal_code': '12345',
            'ba_state': 'XX',
            'ba_street':'123 Test Street',
            'discount_rate': 0.12,
            'late_charge_rate': 0.34,
            'name': 'Test Customer',
            'sa_addressee': 'Test Customer 1 Service',
            'sa_city': 'Test City',
            'sa_postal_code': '12345',
            'sa_state': 'XX',
            'sa_street': '123 Test Street',
        }]})
        self.assertEqual([g.name for g in reebill_customer.get_groups()],
                         ['some other tag', 'one more tag'])

        # Update Reebill_customer discount_rate
        self.assertEqual(reebill_customer.discountrate, 0.12)
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'discount_rate': 0.25,
                'utility_account_id': utility_account.id
            }
        )
        self.assertEqual(reebill_customer.discountrate, 0.25)

        ###############################
        # Update Reebill customer late_charge_rate
        self.assertEqual(reebill_customer.latechargerate, 0.34)
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'discount_rate': 0.45,
                'utility_account_id': utility_account.id
            }
        )
        self.assertEqual(reebill_customer.discountrate, 0.45)
        ###############################
        # Update utility account fb_billing_address
        address = session.query(Address).filter_by(
            addressee='Test Customer 1 Billing'
        ).first()
        self.assertEqual(utility_account.fb_billing_address, address)
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'ba_addressee': 'Test Addressee',
                'ba_city': 'Test City',
                'ba_postal_code': '78910',
                'ba_state': 'YY',
                'ba_street': 'Test Street',
                'utility_account_id': utility_account.id
            }
        )
        address = session.query(Address).filter_by(
            state='YY').one()
        self.assertEqual(utility_account.fb_billing_address, address)
        
        ###############################
        # Update utility account fb_billing_address
        address = session.query(Address).filter_by(
            addressee='Test Customer 1 Service'
        ).first()
        self.assertEqual(utility_account.fb_service_address, address)
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'sa_addressee': 'Test Addressee',
                'sa_city': 'Test City',
                'sa_postal_code': '78910',
                'sa_state': 'ZZ',
                'sa_street': 'Test Street',
                'utility_account_id': utility_account.id
            }
        )
        address = session.query(Address).filter_by(
            state='ZZ').one()
        self.assertEqual(utility_account.fb_service_address, address)

     ###############################
        # Move Bills from one Account to another
        self.assertEqual(len(account_1_bills), 0)
        self.assertEqual(len(account_2_bills),2)
        self.assertEqual(len(account_1_reebills), 0)
        self.assertEqual(len(account_2_reebills), 2)
        success, response = self.app.put(
            '/accounts/%s' % utility_account.id, data={
                'accounts_deleted': utility_account2.id,
                'utility_account_id': utility_account.id
            }
        )
        bills = session.query(UtilBill).filter_by(
            utility_account_id=utility_account.id).all()
        reebills = session.query(ReeBill).join(ReeBillCustomer).filter(
            ReeBillCustomer.utility_account == utility_account).all()
        self.assertEqual(len(bills), 2)
        self.assertEqual(len(reebills), 2)