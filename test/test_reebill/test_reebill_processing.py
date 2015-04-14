import unittest
from StringIO import StringIO
from datetime import date, datetime, timedelta

from mock import Mock
import mongoengine
from sqlalchemy.orm.exc import NoResultFound
from testfixtures.tempdirectory import TempDirectory

from core import init_model
from reebill.views import column_dict
from skyliner.sky_handlers import cross_range
from reebill.reebill_model import ReeBill, UtilBill, ReeBillCustomer, \
    CustomerGroup
from core.model import UtilityAccount, Session, Address, Register, Charge
from test.setup_teardown import TestCaseWithSetup, FakeS3Manager, \
    clear_db, create_utilbill_processor, create_reebill_objects, \
    create_nexus_util
from exc import BillStateError, FormulaSyntaxError, NoSuchBillException, \
    ConfirmAdjustment, ProcessedBillError, IssuedBillError, NotIssuable, \
    BillingError
from test import testing_utils, init_test_config


def setUpModule():
    init_test_config()
    init_model()
    mongoengine.connect('test', host='localhost', port=27017, alias='journal')
    FakeS3Manager.start()

def tearDownModule():
    FakeS3Manager.stop()

class MockReeGetter(object):
    def __init__(self, quantity):
        self.quantity = quantity

    def update_renewable_readings(self, olap_id, reebill,
                                  use_olap=True, verbose=False):
        for reading in reebill.readings:
            reading.renewable_quantity = self.quantity

class ProcessTest(testing_utils.TestCase):
    '''Tests that involve both utility bills and reebills. TODO: each of
    these should be separated apart and put in one of the other classes
    below, or made into some kind of multi-application integrationt test.
    '''
    @classmethod
    def setUpClass(cls):
        # these objects don't change during the tests, so they should be
        # created only once.
        cls.utilbill_processor = create_utilbill_processor()
        cls.billupload = cls.utilbill_processor.bill_file_handler
        cls.reebill_processor, cls.views = create_reebill_objects()
        cls.nexus_util = create_nexus_util()

    def setUp(self):
        clear_db()
        TestCaseWithSetup.insert_data()

    def tearDown(self):
        clear_db()

    def test_delete_utility_bill_with_reebill(self):
        account = '99999'
        start, end = date(2000, 1, 1), date(2000, 2, 1)
        # create utility bill in MySQL, Mongo, and filesystem (and make
        # sure it exists all 3 places)
        u = self.utilbill_processor.upload_utility_bill(account, StringIO(
            "test1"), start, end, 'gas')
        utilbills_data, count = self.views.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(1, count)

        self.utilbill_processor.update_utilbill_metadata(u.id, processed=True)

        # when utilbill is attached to reebill, deletion should fail
        self.reebill_processor.roll_reebill(account, start_date=start)
        reebills_data = self.views.get_reebill_metadata_json(account)
        self.assertDictContainsSubset({
                                          'actual_total': 0,
                                          'balance_due': 0.0,
                                          'balance_forward': 0,
                                          'corrections': '(never issued)',
                                          'hypothetical_total': 0,
                                          'issue_date': None,
                                          'issued': 0,
                                          'version': 0,
                                          'payment_received': 0.0,
                                          'period_end': date(2000, 2, 1),
                                          'period_start': date(2000, 1, 1),
                                          'prior_balance': 0,
                                          'processed': 0,
                                          'ree_charge': 0.0,
                                          'ree_quantity': 21.63261765398553,
                                          'ree_value': 0,
                                          'sequence': 1,
                                          'services': [],
                                          'total_adjustment': 0,
                                          'total_error': 0.0
                                      }, reebills_data[0])
        self.assertRaises(BillingError,
                          self.utilbill_processor.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

        # deletion should fail if any version of a reebill has an
        # association with the utility bill. so issue the reebill, add
        # another utility bill, and create a new version of the reebill
        # attached to that utility bill instead.
        self.reebill_processor.issue(account, 1)
        self.reebill_processor.new_version(account, 1)
        self.utilbill_processor.upload_utility_bill(account, StringIO("test2"),
                                         date(2000, 2, 1), date(2000, 3, 1),
                                         'gas')
        # TODO this may not accurately reflect the way reebills get
        # attached to different utility bills; see
        # https://www.pivotaltracker.com/story/show/51935657
        self.assertRaises(BillingError,
                          self.utilbill_processor.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

    def test_get_create_customer_group(self):
        # Create a new group
        group, created = self.reebill_processor.get_create_customer_group('new')
        self.assertEqual(True, isinstance(group, CustomerGroup))
        self.assertEqual(group.name, 'new')
        self.assertEqual(group.bill_email_recipient, '')
        self.assertTrue(created)
        # Assert the same group is returned on the second call
        group2, created = self.reebill_processor.get_create_customer_group(
            'new')
        self.assertEqual(True, isinstance(group2, CustomerGroup))
        self.assertEqual(group2.name, 'new')
        self.assertEqual(group2.bill_email_recipient, '')
        self.assertFalse(created)
        self.assertEqual(group2, group)
    def test_set_groups_for_utility_account(self):
        utility_account = Session().query(UtilityAccount).filter_by(
            account='99999').one()
        reebill_customer = Session().query(ReeBillCustomer).filter_by(
            utility_account_id=utility_account.id).one()
        self.assertEqual(reebill_customer.get_groups(), [])
        # Add some groups
        self.reebill_processor.set_groups_for_utility_account(
            utility_account.id, ['group1', 'another group', 'unit test'])
        customer_groups = reebill_customer.get_groups()
        self.assertEqual([g.name for g in customer_groups],
                         ['group1', 'another group', 'unit test'])
        another_group_id = customer_groups[1].id
        # Add and remove some groups
        self.reebill_processor.set_groups_for_utility_account(
            utility_account.id, ['another group', 'something else'])
        customer_groups = reebill_customer.get_groups()
        self.assertEqual([g.name for g in customer_groups],
                         ['another group', 'something else'])
        # Assert 'another group' remained the same object
        self.assertEqual(another_group_id, customer_groups[0].id)
class ReebillProcessingTest(testing_utils.TestCase):
    '''Integration tests for the ReeBill application back end including
    database.
    These tests unavoidably involve creating/editing utility bills, because
    those are needed to create reebills, but that should become part of the
    setup process for each test and there is no need to make assertions about
    the behavior of code that only involves utility bills.
    '''
    @classmethod
    def setUpClass(cls):
        cls.reebill_processor, cls.views = create_reebill_objects()
        cls.state_db = cls.reebill_processor.state_db
        cls.nexus_util = cls.reebill_processor.nexus_util
        cls.payment_dao = cls.reebill_processor.payment_dao
        cls.utilbill_processor = create_utilbill_processor()

        # example data to be used in most tests below
        cls.account = '99999'

    def setUp(self):
        clear_db()
        TestCaseWithSetup.insert_data()

    def tearDown(self):
        clear_db()

    def test_list_account_status(self):
        # NOTE this test does not add any data to the database beyond what is
        # inserted in setup

        utility_account_9 = Session().query(UtilityAccount).filter_by(
            account='99999').one()
        utility_account_0 = Session().query(UtilityAccount).filter_by(
            account='100000').one()
        utility_account_1 = Session().query(UtilityAccount).filter_by(
            account='100001').one()
        count, data = self.views.list_account_status()
        self.assertEqual(3, count)
        self.assertEqual([{
            'utility_account_id': utility_account_9.id,
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_utility_name': 'Test Utility Company Template',
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '1',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': '',
            }, {
            'utility_account_id': utility_account_1.id,
            'account': '100001',
            'fb_rate_class': 'Other Rate Class',
            'fb_utility_name': 'Other Utility',
            'casualname': 'Example 4',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '',
            'codename': '',
            'primusname': '1788 Massachusetts Ave.',
            'lastevent': '',
            'tags': '',
            }, {
            'utility_account_id': utility_account_0.id,
            'account': '100000',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_utility_name': 'Test Utility Company Template',
            'casualname': 'Example 3',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '2',
            'codename': '',
            'primusname': '1787 Massachusetts Ave.',
            'lastevent': '',
            'tags': '',
        }], data)

        # get only one account
        count, data = self.views.list_account_status(account='99999')
        self.assertEqual(1, count)
        self.assertEqual([{
            'utility_account_id': utility_account_9.id,
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_utility_name': 'Test Utility Company Template',
            'casualname': 'Example 1',
            'utilityserviceaddress': '123 Test Street, Test City, XX 12345',
            'utility_account_number': '1',
            'codename': '',
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            'tags': '',
        }], data)

    def test_correction_adjustment(self):
        '''Tests that adjustment from a correction is applied to (only) the
            earliest unissued bill.'''
        # replace process.ree_getter with one that always sets the renewable
        # energy readings to a known value
        self.reebill_processor.ree_getter = MockReeGetter(10)
        acc = '99999'

        # create 3 utility bills: Jan, Feb, Mar
        def setup_dummy_utilbill_calc_charges(acc, begin_date, end_date):
            """Upload a dummy-utilbill, add a charge, and calculate charges
            """
            utilbill = self.utilbill_processor.upload_utility_bill(
                acc, StringIO('a utility bill %s %s %s' % (
                    acc, begin_date, end_date)), begin_date, end_date, 'gas')
            Session().add(utilbill)
            self.utilbill_processor.add_charge(utilbill.id)
            self.utilbill_processor.update_charge(
                {
                    'rsi_binding': 'A',
                    'quantity_formula': Charge.get_simple_formula(
                        Register.TOTAL),
                    'rate': 1
                }, utilbill_id=utilbill.id, rsi_binding='New Charge 1')
            self.utilbill_processor.compute_utility_bill(utilbill.id)
            self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                                             processed=True)
        for i in range(3):
            setup_dummy_utilbill_calc_charges(acc, date(2000, i + 1, 1),
                                              date(2000, i + 2, 1))

        # create 1st reebill and issue it
        self.reebill_processor.roll_reebill(acc, start_date=date(2000, 1, 1))
        self.reebill_processor.bind_renewable_energy(acc, 1)
        self.reebill_processor.compute_reebill(acc, 1)
        self.reebill_processor.issue(acc, 1, issue_date=datetime(2000, 3, 15))
        reebill_metadata = self.views.get_reebill_metadata_json('99999')
        self.assertDictContainsSubset({
                                          'sequence': 1,
                                          'version': 0,
                                          'issued': 1,
                                          'issue_date': datetime(2000,3,15),
                                          'actual_total': 0.,
                                          'hypothetical_total': 10,
                                          'payment_received': 0.,
                                          'period_start': date(2000, 1, 1),
                                          'period_end': date(2000, 2, 1),
                                          'prior_balance': 0.,
                                          'processed': 1,
                                          'ree_charge': 8.8,
                                          'ree_value': 10,
                                          'services': [],
                                          'total_adjustment': 0.,
                                          'total_error': 0.,
                                          'balance_due': 8.8,
                                          'balance_forward': 0,
                                          'corrections': '-',
                                          }, reebill_metadata[0])
        self.assertAlmostEqual(10, reebill_metadata[0]['ree_quantity'])
        account_info_v0 = self.reebill_processor.get_sequential_account_info('99999', 1)

        # create 2nd reebill, leaving it unissued
        self.reebill_processor.ree_getter.quantity = 0
        self.reebill_processor.roll_reebill(acc)
        # make a correction on reebill #1. this time 20 therms of renewable
        # energy instead of 10 were consumed.
        self.reebill_processor.ree_getter.quantity = 20
        self.reebill_processor.new_version(acc, 1)
        self.reebill_processor.compute_reebill(acc, 2)

        for x, y in zip([{
                             'actual_total': 0,
                             'balance_due': 17.6,
                             'balance_forward': 17.6,
                             'corrections': '(never issued)',
                             'hypothetical_total': 0,
                             'issue_date': None,
                             'issued': 0,
                             'version': 0,
                             'payment_received': 0.0,
                             'period_end': date(2000, 3, 1),
                             'period_start': date(2000, 2, 1),
                             'prior_balance': 8.8,
                             'processed': 0,
                             'ree_charge': 0.0,
                             'ree_value': 0,
                             'sequence': 2,
                             'services': [],
                             'total_adjustment': 8.8,
                             'total_error': 0.0
                         }, {
                             'actual_total': 0,
                             'balance_due': 17.6,
                             'balance_forward': 0,
                             'corrections': '#1 not issued',
                             'hypothetical_total': 20.0,
                             'issue_date': None,
                             'issued': 0,
                             'version': 1,
                             'payment_received': 0.0,
                             'period_end': date(2000, 2, 1),
                             'period_start': date(2000, 1, 1),
                             'prior_balance': 0,
                             'processed': 0,
                             'ree_charge': 17.6,
                             'ree_value': 20,
                             'sequence': 1,
                             'services': [],
                             'total_adjustment': 0,
                             'total_error': 8.8,
                             }], self.views.get_reebill_metadata_json('99999')):
            self.assertDictContainsSubset(x, y)
            reebill_data = self.views.get_reebill_metadata_json('99999')
            self.assertAlmostEqual(reebill_data[0]['ree_quantity'], 0)
            self.assertAlmostEqual(reebill_data[1]['ree_quantity'], 20)

        # all "sequential account info" gets copied from one version to the next
        account_info_v1 = self.reebill_processor.get_sequential_account_info('99999', 1)
        self.assertEqual(account_info_v0, account_info_v1)

        # when you issue a bill and it has corrections applying to it, and you don't specify apply_corrections=True,
        # it raises an exception ConfirmAdjustment
        self.assertRaises(ConfirmAdjustment ,self.reebill_processor.issue_and_mail, False, account=acc, sequence=2)

        # when you make a bill processed and it has corrections applying to it, and you don't specify apply_corrections=True,
        # it raises an exception ConfirmAdjustment
        self.assertRaises(ConfirmAdjustment ,self.reebill_processor.toggle_reebill_processed, acc, 2, apply_corrections=False)
        self.reebill_processor.toggle_reebill_processed(acc,2,apply_corrections=True)
        reebill = self.state_db.get_reebill(acc, 2)
        correction = self.state_db.get_reebill(acc, 1, version=1)
        # any processed regular bill or correction can't be modified (compute, bind_ree, sequential_account_info)
        self.assertRaises(ProcessedBillError, self.reebill_processor.compute_reebill, acc, reebill.sequence)
        self.assertRaises(ProcessedBillError, self.reebill_processor.bind_renewable_energy, acc, reebill.sequence)
        self.assertRaises(ProcessedBillError, self.reebill_processor.update_sequential_account_info, acc, reebill.sequence)
        self.assertRaises(ProcessedBillError, self.reebill_processor.compute_reebill, acc, correction.sequence)
        self.assertRaises(ProcessedBillError, self.reebill_processor.bind_renewable_energy, acc, correction.sequence)
        self.assertRaises(ProcessedBillError, self.reebill_processor.update_sequential_account_info, acc, correction.sequence)

        # when you do specify apply_corrections=True, the corrections are marked as processed.
        self.assertEqual(reebill.processed, True)
        self.assertEqual(correction.processed, True)
        # When toggle_reebill_processed is called for a processed reebill,
        # reebill becomes unprocessed
        self.reebill_processor.toggle_reebill_processed(acc, 2, apply_corrections=False)
        self.assertEqual(reebill.processed, False)

        self.reebill_processor.issue(acc, reebill.sequence, issue_date=datetime(2000,3,10))
        self.assertRaises(IssuedBillError, self.reebill_processor.bind_renewable_energy, acc, reebill.sequence)
        # when toggle_reebill_processed is called for issued reebill it raises IssuedBillError
        self.assertRaises(IssuedBillError,
                          self.reebill_processor.toggle_reebill_processed, acc, reebill.sequence,
                          apply_corrections=False)


    def test_create_first_reebill(self):
        '''Test creating the first utility bill and reebill for an account,
            making sure the reebill is correct with respect to the utility bill.
            '''
        # at first, there are no utility bills
        self.assertEqual(([], 0), self.views.get_all_utilbills_json(
            '99999', 0, 30))

        # upload a utility bill
        ub = self.utilbill_processor.upload_utility_bill(
            '99999', StringIO('January 2013'), date(2013, 1, 1),
            date(2013, 2, 1), 'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)

        utilbill_data = self.views.get_all_utilbills_json(
            '99999', 0, 30)[0][0]
        self.assertDictContainsSubset({
                                          'account': '99999',
                                          'computed_total': 0,
                                          'period_end': date(2013, 2, 1),
                                          'period_start': date(2013, 1, 1),
                                          'processed': True,
                                          'rate_class':
                                              self.views.get_rate_class('Test Rate Class Template').name,
                                          'reebills': [],
                                          'service': 'Gas',
                                          'state': 'Final',
                                          'total_charges': 0.0,
                                          'utility':
                                          column_dict(
                                              self.views.get_utility(
                                                  'Test Utility Company Template')),
                                          }, utilbill_data)

        # create a reebill
        self.reebill_processor.roll_reebill('99999', start_date=date(2013, 1, 1))

        utilbill_data = self.views.get_all_utilbills_json(
            '99999', 0, 30)[0][0]
        self.assertDictContainsSubset({'issue_date': None, 'sequence': 1, 'version': 0},
                                      utilbill_data['reebills'][0])

        self.assertDictContainsSubset(
            {
                'account': '99999',
                'computed_total': 0,
                'period_end': date(2013, 2, 1),
                'period_start': date(2013, 1, 1),
                'processed': True,
                'rate_class': self.views.get_rate_class(
                    'Test Rate Class Template').name,
                'service': 'Gas', 'state': 'Final',
                'total_charges': 0.0,
                'utility': column_dict(
                    self.views.get_utility(
                    'Test Utility Company Template')),
            }, utilbill_data)


        # TODO: fields not checked above that should be checked some other
        # way:
        # email recipient
        # utilbills
        # ree_charge
        # ree_savings
        # late_charges
        # ree_value
        # late_charge_rate
        # discount_rate
        # payment_received
        # total_adjustment
        # billing_address
        # service_address

        billing_address = {
            'addressee': 'Andrew Mellon',
            'street': '1785 Massachusetts Ave. NW',
            'city': 'Washington',
            'state': 'DC',
            'postal_code': '20036',
            }
        service_address = {
            'addressee': 'Skyline Innovations',
            'street': '1606 20th St. NW',
            'city': 'Washington',
            'state': 'DC',
            'postal_code': '20009',
            }
        self.reebill_processor.create_new_account('55555', 'Another New Account',
                                        'thermal', 0.6, 0.2, billing_address,
                                        service_address, '99999', '123')
        self.assertRaises(ValueError, self.reebill_processor.roll_reebill,
                          '55555', start_date=date(2013, 2, 1))

    def test_correction_issuing(self):
        """Test creating corrections on reebills, and issuing them to create
        adjustments on other reebills.
        """
        acc = '99999'
        rp = self.reebill_processor
        base_date = date(2012, 1, 1)

        for i in xrange(4):
            ub = self.utilbill_processor.upload_utility_bill(
                acc, StringIO('utility bill %s' % i),
                base_date + timedelta(days=30 * i),
                base_date + timedelta(days=30 * (i + 1)), 'gas')

            self.utilbill_processor.add_charge(ub.id)  #creates a charge with
            # rsi_binding 'New RSI #1'
            #update the just-created charge
            self.utilbill_processor.update_charge(
                {'rsi_binding': 'THE_CHARGE',
                 'quantity_formula':  Charge.get_simple_formula(Register.TOTAL),
                'rate': 1}, utilbill_id=ub.id, rsi_binding='New Charge 1')

            self.utilbill_processor.update_register(ub.registers[0].id,
                                                    {'quantity': 100})
            self.utilbill_processor.compute_utility_bill(ub.id)
            self.utilbill_processor.update_utilbill_metadata(ub.id,
                                                             processed=True)

        for seq, reg_tot, strd in [(1, 100, base_date),
                                   (2, 200, None),
                                   (3, 300, None)]:
            rb = rp.roll_reebill(acc, start_date=strd)
            rp.update_sequential_account_info(acc, seq, discount_rate=0.5)
            rp.ree_getter = MockReeGetter(reg_tot)
            rp.bind_renewable_energy(acc, seq)
            rp.compute_reebill(acc, seq)
            rp.issue(acc, seq)

            self.assertEqual(rb.ree_charge, reg_tot / 2.0,
                             "Reebill %s recharge should equal %s; not %s" \
                             % (seq, reg_tot / 2.0, rb.ree_charge))

        self.assertEquals([], rp.get_unissued_corrections(acc),
                            "There should be no unissued corrections.")
        self.assertEquals(0, rp.get_total_adjustment(acc),
                          "There should be no total adjustments.")

        rp.roll_reebill(acc)  # Fourth Reebill

        # it is OK to call issue_corrections() when no corrections
        # exist: nothing should happen
        rp.issue_corrections(acc, 4)

        reebill_data = lambda seq: next(
            d for d in self.views.get_reebill_metadata_json(acc)
            if d['sequence'] == seq)

        # Update the discount rate for reebill sequence 1
        rp.new_version(acc, 1)
        rp.update_reebill_readings(acc, 1)
        rp.update_sequential_account_info(acc, 1, discount_rate=0.75)
        rp.ree_getter = MockReeGetter(100)
        rp.bind_renewable_energy(acc, 1)
        rp.compute_reebill(acc, 1, version=1)

        d = reebill_data(1)
        self.assertEqual(d['ree_charge'], 25.0)

        #Update the discount rate for reebill sequence 3
        rp.new_version(acc, 3)
        rp.update_reebill_readings(acc, 3)
        rp.update_sequential_account_info(acc, 3, discount_rate=0.25)
        rp.ree_getter = MockReeGetter(300)
        rp.bind_renewable_energy(acc, 3)
        rp.compute_reebill(acc, 3)
        d = reebill_data(3)
        self.assertEqual(d['ree_charge'], 225.0,
                         "Charges for reebill seq 3 should be updated to 225")

        # there should be 2 adjustments: -25 for the first bill, and +75
        # for the 3rd
        self.assertEqual([(1, 1, -25), (3, 1, 75)],
                         rp.get_unissued_corrections(acc))
        self.assertEqual(50, rp.get_total_adjustment(acc))

        # try to apply corrections to an issued bill
        self.assertRaises(ValueError, rp.issue_corrections, acc, 2)
        # try to apply corrections to a correction
        self.assertRaises(ValueError, rp.issue_corrections, acc, 3)

        self.assertFalse(reebill_data(1)['issued'])
        self.assertFalse(reebill_data(3)['issued'])

        # get original balance of reebill 4 before applying corrections
        #four = self.state_db.get_reebill(session, acc, 4)
        # we sometimes see this error message being printed at some point in
        # this call:
        # /Users/dan/.virtualenvs/b/lib/python2.7/site-packages/sqlalchemy/orm/persistence.py:116: SAWarning: DELETE statement on table 'reebill_charge' expected to delete 1 row(s); 0 were matched.  Please set confirm_deleted_rows=False within the mapper configuration to prevent this warning.
        # it doesn't always happen and doesn't always happen in the same place.
        rp.compute_reebill(acc, 4)

        # apply corrections to un-issued reebill 4. reebill 4 should be
        # updated, and the corrections (1 & 3) should be issued
        rp.issue_corrections(acc, 4)
        rp.compute_reebill(acc, 4)
        # for some reason, adjustment is part of "balance forward"
        # https://www.pivotaltracker.com/story/show/32754231

        four = reebill_data(4)
        self.assertEqual(four['prior_balance'] - four['payment_received'] +
                         four['total_adjustment'], four['balance_forward'])
        self.assertEquals(four['balance_forward'] + four['ree_charge'],
                          four['balance_due'])

        self.assertTrue(reebill_data(1)['issued'])
        self.assertTrue(reebill_data(3)['issued'])

        self.assertEqual([], rp.get_unissued_corrections(acc))

    # TODO rename
    def test_roll(self):
        '''Tests creation of reebills and dependency of each reebill on its
        predecessor.'''
        account = '99999'
        self.reebill_processor.ree_getter = MockReeGetter(100)

        ub = self.utilbill_processor.upload_utility_bill(
            account, StringIO('April 2000'), date(2000, 1, 4), date(2000, 2, 2),
            'gas')
        # add a register to the first utility bill so there are 2,
        # total and demand
        id_1 = self.views.get_all_utilbills_json(account, 0, 30)[0][0]['id']
        register = self.utilbill_processor.new_register(
            id_1, meter_identifier='M60324', identifier='R')
        self.utilbill_processor.update_register(
            register.id, {'register_binding': Register.DEMAND})
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)

        # 2nd utility bill should have the same registers as the first
        utilbill = self.utilbill_processor.upload_utility_bill(
            account, StringIO('May 2000'), date(2000, 2, 2), date(2000, 3, 3),
            'gas')

        # create reebill based on first utility bill
        reebill1 = self.reebill_processor.roll_reebill(account,
                                             start_date=date(2000, 1, 4))

        self.reebill_processor.compute_reebill(account, 1)
        self.reebill_processor.issue(account, 1,
                           issue_date=datetime(2000, 2, 1))
        # delete register from the 2nd utility bill
        id_2 = self.views.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']

        register = filter(lambda x: x.identifier == 'R' and
                                    x.meter_identifier == 'M60324',
                          utilbill.registers)[0]
        self.utilbill_processor.delete_register(register.id)

        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                                         processed=True)
        # 2nd reebill should NOT have a reading corresponding to the
        # additional register, which was removed
        reebill2 = self.reebill_processor.roll_reebill(account)
        utilbill_data, count = self.views.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(2, count)
        self.assertEqual(reebill1.readings[0].measure, reebill2.readings[0].measure)
        self.assertEqual(reebill1.readings[0].aggregate_function,
                         reebill2.readings[0].aggregate_function)
        self.assertDictContainsSubset(
            {
                'sequence': 1,
                'version': 0,
                'issue_date': datetime(2000, 2, 1),
            }, utilbill_data[1]['reebills'][0])
        self.assertDictContainsSubset(
            {'sequence': 2,
             'version': 0,
             'issue_date': None,
            }, utilbill_data[0]['reebills'][0])

        reebill_2_data, reebill_1_data = self.views.get_reebill_metadata_json(
            account)
        self.assertAlmostEqual(100, reebill_1_data['ree_quantity'])
        self.assertAlmostEqual(100, reebill_2_data['ree_quantity'])

        # addresses should be preserved from one reebill document to the
        # next
        billing_address = {
            u"postal_code" : u"12345",
            u"city" : u"Test City",
            u"state" : u"XX",
            u"addressee" : u"Test Customer 1 Billing",
            u"street" : u"123 Test Street"
        }
        service_address = {
            u"postal_code" : u"12345",
            u"city" : u"Test City",
            u"state" : u"XX",
            u"addressee" : u"Test Customer 1 Service",
            u"street" : u"123 Test Street"
        }
        account_info = self.reebill_processor.get_sequential_account_info(account, 1)
        self.assertDictContainsSubset(billing_address,
                                      account_info['billing_address'])
        self.assertDictContainsSubset(service_address,
                                      account_info['service_address'])
        self.assertEqual(account_info['discount_rate'], 0.12)
        self.assertEqual(account_info['late_charge_rate'], 0.34)

        # add two more utility bills: UtilityEstimated and Complete
        self.utilbill_processor.upload_utility_bill(account, StringIO('July 2000'),
                                         date(2000, 4, 1), date(2000, 4, 30),
                                         'gas')
        utilbill_data, count = self.views.get_all_utilbills_json(account,
                0, 30)
        self.assertEqual(3, count)
        self.assertEqual(['Final', 'Final', 'Final'],
                         [u['state'] for u in utilbill_data])

        ub = self.utilbill_processor.upload_utility_bill(
            account, StringIO('June 2000'), date(2000, 3, 3), date(2000, 4, 1),
            'gas', state=UtilBill.UtilityEstimated)
        utilbill_data, count = self.views.get_all_utilbills_json(account,
                0, 30)
        self.assertEqual(4, count)
        self.assertEqual(['Final', 'Utility Estimated', 'Final', 'Final'],
                         [u['state'] for u in utilbill_data])
        last_utilbill_id, formerly_hyp_utilbill_id = (u['id'] for u in
                                                      utilbill_data[:2])
        self.utilbill_processor.update_utilbill_metadata(ub.id,
                                                         processed=True)
        self.reebill_processor.roll_reebill(account)

        # if a utiltity bill has an error in its charges, an exception should
        # be raised when computing the reebill, but Process.roll_reebill ignores
        # it and catches it
        last_utilbill_id = utilbill_data[0]['id']
        charge = self.utilbill_processor.add_charge(last_utilbill_id)
        charge.quantity_formula = '1 +'
        self.utilbill_processor.update_utilbill_metadata(last_utilbill_id,
                                                         processed=True)
        self.reebill_processor.roll_reebill(account)
        self.reebill_processor.compute_reebill(account, 2)

        self.reebill_processor.issue(account, 2)

        # Shift later_utilbill a few days into the future so that there is
        # a time gap after the last attached utilbill
        self.utilbill_processor.update_utilbill_metadata(
            formerly_hyp_utilbill_id, processed=False)
        self.utilbill_processor.update_utilbill_metadata(
            last_utilbill_id, processed=False)
        self.utilbill_processor.update_utilbill_metadata(
            formerly_hyp_utilbill_id, period_start=date(2000, 3, 8))
        self.utilbill_processor.update_utilbill_metadata(last_utilbill_id,
                                              period_end=date(2000, 4, 6))

        # can't create another reebill because there are no more utility
        # bills
        with self.assertRaises(NoSuchBillException) as context:
            self.reebill_processor.roll_reebill(account)

class ReeBillProcessingTestWithBills(testing_utils.TestCase):
    '''This class is like ReeBillProcessingTest but includes methods that
    share test data to reduce duplicate code. As many methods as possible from
    ReeBillProcessingTest should be moved here.
    '''
    @classmethod
    def setUpClass(cls):
        cls.reebill_processor, cls.views = create_reebill_objects()
        cls.state_db = cls.reebill_processor.state_db
        cls.nexus_util = cls.reebill_processor.nexus_util
        cls.payment_dao = cls.reebill_processor.payment_dao
        cls.utilbill_processor = create_utilbill_processor()
        cls.mailer = cls.reebill_processor.bill_mailer

        # example data to be used in most tests below
        cls.account = '99999'

    def setUp(self):
        clear_db()
        # TODO: do not rely on previously inserted data
        TestCaseWithSetup.insert_data()
        self.utilbill = self.utilbill_processor.upload_utility_bill(
            self.account, StringIO('test'), date(2000, 1, 1), date(2000, 2, 1),
            'gas')
        self.utility = self.utilbill.get_utility()
        s = Session()
        self.utility_account = s.query(UtilityAccount).filter_by(
            account='99999').one()
        self.customer = s.query(ReeBillCustomer).filter_by(
            utility_account_id=self.utility_account.id).one()

    def tearDown(self):
        clear_db()

    def test_get_late_charge(self):
        '''Tests computation of late charges.
        '''
        # TODO: when possible, convert this into a unit test that checks the
        # get_late_charge method, whatever class it may belong to by then
        # (ReeBill?). See 69883814.
        acc = '99999'
        # create utility bill with a charge in it
        self.utilbill_processor.add_charge(self.utilbill.id)
        self.utilbill_processor.update_charge(
            {
                'rsi_binding': 'THE_CHARGE',
                'quantity_formula': Charge.get_simple_formula(Register.TOTAL),
                'unit': 'therms',
                'rate': 1,
            }, utilbill_id=self.utilbill.id, rsi_binding='New Charge 1')
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)

        # create first reebill
        bill1 = self.reebill_processor.roll_reebill(acc, start_date=date(
            2000, 1, 1))
        self.reebill_processor.update_sequential_account_info(acc, 1,
                                                              discount_rate=.5, late_charge_rate=.34)
        self.reebill_processor.ree_getter = MockReeGetter(100)
        self.reebill_processor.bind_renewable_energy(acc, 1)
        self.reebill_processor.compute_reebill(acc, 1)
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill1,
                                                                   date(1999, 12, 31)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill1,
                                                                   date(2000, 1, 1)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill1,
                                                                   date(2000, 1, 2)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill1,
                                                                   date(2000, 2, 1)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill1,
                                                                   date(2000, 2, 2)))

        # issue first reebill, so a later bill can have a late charge
        # based on the customer's failure to pay bill1 by its due date,
        # i.e. 30 days after the issue date.
        self.reebill_processor.issue(acc, bill1.sequence, issue_date=datetime(2000, 4, 1))
        self.assertEqual(date(2000, 5, 1), bill1.due_date)
        self.assertEqual(50, bill1.balance_due)
        # create 2nd utility bill and reebill
        u2 = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('February 2000'), date(2000, 2, 1), date(2000, 3, 1),
            'gas')
        Session().flush()

        self.utilbill_processor.update_utilbill_metadata(u2.id, processed=True)
        bill2 = self.reebill_processor.roll_reebill(acc)
        self.reebill_processor.update_sequential_account_info(acc, 2,
                                                              discount_rate=.5, late_charge_rate=.34)
        self.reebill_processor.ree_getter = MockReeGetter(200)
        self.reebill_processor.bind_renewable_energy(acc, 2)
        self.reebill_processor.compute_reebill(acc, 2)
        assert bill2.discount_rate == 0.5
        assert bill2.ree_charge == 100

        # bill2's late charge should be 0 before bill1's due date; on/after
        # the due date, it's balance * late charge rate, i.e.
        # 50 * .34 = 17
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(1999, 12, 31)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2000, 1, 2)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2000, 3, 31)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2000, 4, 1)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2000, 4, 2)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2000, 4, 30)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2000, 5, 1)))
        self.assertEqual(17, self.reebill_processor.get_late_charge(bill2,
                                                                    date(2000, 5, 2)))
        self.assertEqual(17, self.reebill_processor.get_late_charge(bill2,
                                                                    date(2013, 1, 1)))

        # in order to get late charge of a 3rd bill, bill2 must be computed
        self.reebill_processor.compute_reebill(acc, 2)

        # create a 3rd bill without issuing bill2. bill3 should have None
        # as its late charge for all dates
        ub = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('March 2000'), date(2000, 3, 1), date(2000, 4, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)
        bill3 = self.reebill_processor.roll_reebill(acc)
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill3,
                                                                   date(1999, 12, 31)))
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill3,
                                                                   date(2013, 1, 1)))

        # late charge should be based on the version with the least total
        # of the bill from which it derives. on 2013-01-15, make a version
        # 1 of bill 1 with a lower total, and then on 2013-03-15, a version
        # 2 with a higher total, and check that the late charge comes from
        # version 1.
        self.reebill_processor.new_version(acc, 1)
        bill1_1 = self.state_db.get_reebill(acc, 1, version=1)
        self.reebill_processor.ree_getter = MockReeGetter(100)
        self.reebill_processor.bind_renewable_energy(acc, 1)
        bill1_1.discount_rate = 0.75
        self.reebill_processor.compute_reebill(acc, 1, version=1)
        self.assertEqual(25, bill1_1.ree_charge)
        self.assertEqual(25, bill1_1.balance_due)
        self.reebill_processor.issue(acc, 1, issue_date=datetime(2013, 3, 15))
        late_charge_source_amount = bill1_1.balance_due

        self.reebill_processor.new_version(acc, 1)
        self.reebill_processor.bind_renewable_energy(acc, 2)
        self.reebill_processor.update_sequential_account_info(acc, 1,
                                                              discount_rate=.25)
        bill1_2 = self.state_db.get_reebill(acc, 1, version=2)
        self.reebill_processor.compute_reebill(acc, 1, version=2)
        self.assertEqual(75, bill1_2.ree_charge)
        self.assertEqual(75, bill1_2.balance_due)
        self.reebill_processor.issue(acc, 1)

        # note that the issue date on which the late charge in bill2 is
        # based is the issue date of version 0--it doesn't matter when the
        # corrections were issued.
        late_charge = self.reebill_processor.get_late_charge(bill2, date(2013, 4, 18))
        self.assertEqual(late_charge_source_amount * bill2.late_charge_rate,
                         late_charge)

        # add a payment between 2000-01-01 (when bill1 version 0 was
        # issued) and 2013-01-01 (the present), to make sure that payment
        # is deducted from the balance on which the late charge is based
        self.payment_dao.create_payment(acc, date(2000, 6, 5),
                                        'a $10 payment in june', 10)
        self.assertEqual((late_charge_source_amount - 10) *
                         bill2.late_charge_rate,
                         self.reebill_processor.get_late_charge(bill2, date(2013, 1, 1)))

        # Pay off the bill, make sure the late charge is 0
        self.payment_dao.create_payment(acc, date(2000, 6, 6),
                                        'a $40 payment in june', 40)
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2013, 1, 1)))

        #Overpay the bill, make sure the late charge is still 0
        self.payment_dao.create_payment(acc, date(2000, 6, 7),
                                        'a $40 payment in june', 40)
        self.assertEqual(0, self.reebill_processor.get_late_charge(bill2,
                                                                   date(2013, 1, 1)))

    def test_issue(self):
        '''Tests issuing of reebills.'''
        acc = '99999'
        # two utilbills, with reebills
        ub2 = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('february 2000'), date(2000, 2, 1), date(2000, 3, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)
        self.utilbill_processor.update_utilbill_metadata(ub2.id,
                                                         processed=True)
        one = self.reebill_processor.roll_reebill(acc,
                                                  start_date=date(2000, 1, 1))
        two = self.reebill_processor.roll_reebill(acc)

        # neither reebill should be issued yet
        self.assertEquals(False, self.state_db.is_issued(acc, 1))
        self.assertEquals(None, one.issue_date)
        self.assertEquals(None, one.due_date)
        self.assertEqual(None, one.email_recipient)
        self.assertEquals(False, self.state_db.is_issued(acc, 2))
        self.assertEquals(None, two.issue_date)
        self.assertEquals(None, two.due_date)
        self.assertEqual(None, two.email_recipient)

        # two should not be issuable until one_doc is issued
        self.assertRaises(BillStateError, self.reebill_processor.issue, acc, 2)

        # issue one
        self.reebill_processor.issue(acc, 1, issue_date=datetime(2001, 4, 1))

        self.assertEquals(True, one.issued)
        self.assertEquals(True, one.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals(datetime(2001, 4, 1), one.issue_date)
        self.assertEquals((one.issue_date + timedelta(30)).date(), one.due_date)
        self.assertEquals('example@example.com', one.email_recipient)

        customer = self.state_db.get_reebill_customer(acc)
        customer.bill_email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue two
        self.reebill_processor.issue(acc, 2,
                                     issue_date=datetime(2001, 5, 1, 12))

        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, two.issued)
        self.assertEquals(True, two.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals(datetime(2001, 5, 1, 12), two.issue_date)
        self.assertEquals((two.issue_date + timedelta(30)).date(), two.due_date)
        self.assertEquals('test1@example.com, test2@exmaple.com',
                          two.email_recipient)

    def test_issue_2_at_once(self):
        '''Tests issuing one bill immediately after another, without
        recomputing it. In bug 64403990, a bill could be issued with a wrong
        "prior balance" because it was not recomputed before issuing to
        reflect a change to its predecessor.
        '''
        acc = self.account
        # first reebill is needed so the others get computed correctly
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)
        self.reebill_processor.roll_reebill(acc, start_date=date(2000, 1, 1))
        self.reebill_processor.issue(acc, 1, datetime(2000, 2, 15))

        # two more utility bills and reebills
        ub = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('february 2000'), date(2000, 2, 1), date(2000, 3, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)
        ub = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('march 2000'), date(2000, 3, 1), date(2000, 4, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)
        two = self.reebill_processor.roll_reebill(acc)
        three = self.reebill_processor.roll_reebill(acc)

        # add a payment, shown on bill #2
        self.payment_dao.create_payment(acc, date(2000, 2, 16), 'a payment',
                                        100)
        # TODO bill shows 0 because bill has no energy in it and
        # payment_received is 0
        self.reebill_processor.compute_reebill(acc, 2)
        self.assertEqual(100, two.payment_received)
        self.assertEqual(-100, two.balance_due)

        # the payment does not appear on #3, since #3 has not be
        # recomputed
        self.assertEqual(0, three.payment_received)
        self.assertEqual(0, three.prior_balance)
        self.assertEqual(0, three.balance_forward)
        self.assertEqual(0, three.balance_due)

        # make bills processed before issuing to test alternate methods of
        # issuing.
        # it is necessary to compute bill 3 before it becomes processed
        # because that is not done by update_sequential_account_info
        self.reebill_processor.compute_reebill(acc, 3)
        self.reebill_processor.update_sequential_account_info(acc, 2, processed=True)
        self.reebill_processor.update_sequential_account_info(acc, 3, processed=True)

        # issue #2 and #3, using two different methods
        # (the second is the equivalent of "Issue All Processed Reebills" in
        # the UI)
        self.reebill_processor.issue_and_mail(True, account=acc, sequence=2)
        self.reebill_processor.issue_processed_and_mail(True)

        # #2 is still correct, and #3 should be too because it was
        # automatically recomputed before issuing
        self.assertEqual(100, two.payment_received)
        self.assertEqual(-100, two.balance_due)
        self.assertEqual(-100, three.prior_balance)
        self.assertEqual(0, three.payment_received)
        self.assertEqual(-100, three.balance_forward)
        self.assertEqual(-100, three.balance_due)

    def test_issue_and_mail(self):
        '''Tests issuing and mailing of reebills.'''
        acc = self.account
        # two utilbills, with reebills
        self.reebill_processor.bill_mailer = Mock()
        self.reebill_processor.reebill_file_handler = Mock()
        self.reebill_processor.reebill_file_handler.render_max_version.return_value = 1
        self.reebill_processor.reebill_file_handler.get_file_path = Mock()
        temp_dir = TempDirectory()
        self.reebill_processor.reebill_file_handler.get_file_contents.return_value = \
            temp_dir, StringIO().read()
        self.utilbill_processor.update_utilbill_metadata(
            self.utilbill.id, processed=True)
        ub = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('february 2000'), date(2000, 2, 1), date(2000, 3, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)
        one = self.reebill_processor.roll_reebill(
            acc, start_date=date(2000, 1, 1))
        two = self.reebill_processor.roll_reebill(acc)

        # neither reebill should be issued yet
        self.assertEquals(False, self.state_db.is_issued(acc, 1))
        self.assertEquals(None, one.issue_date)
        self.assertEquals(None, one.due_date)
        self.assertEqual(None, one.email_recipient)
        self.assertEquals(False, self.state_db.is_issued(acc, 2))
        self.assertEquals(None, two.issue_date)
        self.assertEquals(None, two.due_date)
        self.assertEqual(None, two.email_recipient)

        # two should not be issuable until one is issued
        self.assertRaises(BillStateError, self.reebill_processor.issue, acc, 2)
        self.assertRaises(NotIssuable, self.reebill_processor.issue_and_mail,
                          False, acc, 2)
        one.email_recipient = 'one@example.com, one@gmail.com'

        # issue and email one
        self.reebill_processor.issue_and_mail(False, account=acc, sequence=1,
                                              recipients=one.email_recipient)

        self.assertEquals(True, one.issued)
        self.assertEquals(True, one.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals((one.issue_date + timedelta(30)).date(), one.due_date)
        # make a correction on reebill #1. this time 20 therms of renewable
        # energy instead of 10 were consumed.
        self.reebill_processor.ree_getter.quantity = 20
        self.reebill_processor.new_version(acc, 1)

        customer = self.state_db.get_reebill_customer(acc)
        two.email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue and email two
        self.reebill_processor.reebill_file_handler.render_max_version.return_value = 2
        # issuing a reebill that has corrections with apply_corrections False raises ConfirmAdjustment Exception
        with self.assertRaises(ConfirmAdjustment):
            self.reebill_processor.issue_and_mail(
                False, account=acc, sequence=2, recipients=two.email_recipient)
        #ValueError is Raised if an issued Bill is issued again
        with  self.assertRaises(ValueError):
            self.reebill_processor.issue_and_mail(
                True, account=acc, sequence=1, recipients=two.email_recipient)
        self.reebill_processor.toggle_reebill_processed(acc, 2, True)
        self.assertEqual(True, two.processed)
        self.reebill_processor.issue_processed_and_mail(True)
        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, two.issued)
        self.assertEquals(True, two.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals((two.issue_date + timedelta(30)).date(), two.due_date)

        temp_dir.cleanup()

    def test_issue_processed_and_mail(self):
        '''Tests issuing and mailing of processed reebills.'''
        acc = self.account
        # two utilbills, with reebills
        self.reebill_processor.bill_mailer = self.mailer
        self.reebill_processor.reebill_file_handler = Mock()
        self.reebill_processor.reebill_file_handler.render_max_version \
            .return_value = 1
        self.reebill_processor.reebill_file_handler.get_file_contents = Mock()
        temp_dir = TempDirectory()
        self.reebill_processor.reebill_file_handler \
            .get_file_contents.return_value = \
            temp_dir.path, StringIO().read()
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)
        ub = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('february 2000'), date(2000, 2, 1), date(2000, 3, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)
        one = self.reebill_processor.roll_reebill(acc,
                                                  start_date=date(2000, 1, 1))
        one.processed = True
        two = self.reebill_processor.roll_reebill(acc)
        two.processed = True

        # neither reebill should be issued yet
        self.assertEquals(False, self.state_db.is_issued(acc, 1))
        self.assertEquals(None, one.issue_date)
        self.assertEquals(None, one.due_date)
        self.assertEqual(None, one.email_recipient)
        self.assertEquals(False, self.state_db.is_issued(acc, 2))
        self.assertEquals(None, two.issue_date)
        self.assertEquals(None, two.due_date)
        self.assertEqual(None, two.email_recipient)

        # two should not be issuable until one_doc is issued
        self.assertRaises(BillStateError, self.reebill_processor.issue, acc, 2)
        one.email_recipient = 'one@example.com, one@gmail.com'

        # issue and email one
        self.reebill_processor.issue_processed_and_mail(False)

        self.assertEquals(True, one.issued)
        self.assertEquals(True, one.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals((one.issue_date + timedelta(30)).date(), one.due_date)

        customer = self.state_db.get_reebill_customer(acc)
        two.email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue and email two
        self.reebill_processor.reebill_file_handler.render_max_version.\
            return_value = 2
        self.reebill_processor.issue_processed_and_mail(False)

        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, two.issued)
        self.assertEquals(True, two.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals((two.issue_date + timedelta(30)).date(), two.due_date)

        temp_dir.cleanup()

    def test_delete_reebill(self):
        account = self.account
        # create 2 utility bills for Jan-Feb 2012
        ub2 = self.utilbill_processor.upload_utility_bill(
            account, StringIO('february 2000'), date(2000, 2, 1),
            date(2000, 3, 1), 'gas')
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)
        self.utilbill_processor.update_utilbill_metadata(ub2.id,
                                                         processed=True)
        utilbill = Session().query(UtilBill).join(UtilityAccount) \
            .filter(UtilityAccount.account==account) \
            .order_by(UtilBill.period_start).first()

        reebill = self.reebill_processor.roll_reebill(
            account, start_date=date(2000, 1, 1))
        self.reebill_processor.roll_reebill(account)

        # only the last reebill is deletable: deleting the 2nd one should
        # succeed, but deleting the 1st one should fail
        with self.assertRaises(IssuedBillError):
            self.reebill_processor.delete_reebill(account, 1)
        self.reebill_processor.delete_reebill(account, 2)
        with self.assertRaises(NoResultFound):
            self.state_db.get_reebill(account, 2, version=0)
        self.assertEquals(1, Session().query(ReeBill).count())
        self.assertEquals([(1,)], Session().query(ReeBill.sequence).all())
        self.assertEquals([utilbill], reebill.utilbills)

        # issued reebill should not be deletable
        self.reebill_processor.issue(account, 1)
        self.assertEqual(1, reebill.issued)
        self.assertEqual([utilbill], reebill.utilbills)
        self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)
        self.assertRaises(IssuedBillError,
                          self.reebill_processor.delete_reebill, account, 1)

        # create a new verison and delete it, returning to just version 0
        self.reebill_processor.new_version(account, 1)
        Session().query(ReeBill).filter_by(version=1).one()
        self.assertEqual(1, self.state_db.max_version(account, 1))
        self.assertFalse(self.state_db.is_issued(account, 1))
        self.reebill_processor.delete_reebill(account, 1)
        self.assertEqual(0, self.state_db.max_version(account, 1))
        self.assertTrue(self.state_db.is_issued(account, 1))

        # original version should still be attached to utility bill
        # TODO this will have to change. see
        # https://www.pivotaltracker.com/story/show/31629749
        self.assertEqual([utilbill], reebill.utilbills)
        self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)

    def test_uncomputable_correction_bug(self):
        '''Regresssion test for
            https://www.pivotaltracker.com/story/show/53434901.'''
        account = self.account
        # create reebill and utility bill
        utilbill_id = self.views.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']
        self.utilbill_processor.update_utilbill_metadata(
            utilbill_id, processed=True)
        self.reebill_processor.roll_reebill(account,
                                            start_date=date(2000, 1, 1))
        self.reebill_processor.bind_renewable_energy(account, 1)
        self.reebill_processor.compute_reebill(account, 1)
        self.reebill_processor.issue(account, 1)

        # create new version
        self.reebill_processor.new_version(account, 1)
        self.assertEquals(1, self.state_db.max_version(account, 1))

        # initially, reebill version 1 can be computed without an error
        self.reebill_processor.compute_reebill(account, 1, version=1)

        # put it in an un-computable state by adding a charge with a syntax
        # error in its formula. it should now raise an RSIError.
        # (computing a utility bill doesn't raise an exception by default, but
        # computing a reebill based on the utility bill does.)
        # NOTE it is possible to un-process a utility bill after a reebill
        # has been created from it
        self.utilbill_processor.update_utilbill_metadata(utilbill_id,
                                                         processed=False)
        charge = self.utilbill_processor.add_charge(utilbill_id)
        self.utilbill_processor.update_charge({
                                                  'quantity_formula': '1 + ',
                                                  'rsi_binding': 'some_rsi'
                                              }, charge_id=charge.id)
        with self.assertRaises(FormulaSyntaxError):
            self.reebill_processor.compute_reebill(account, 1, version=1)

        # delete the new version
        self.reebill_processor.delete_reebill(account, 1)
        reebill_data = self.views.get_reebill_metadata_json(account)
        self.assertEquals(0, reebill_data[0]['version'])

        # try to create a new version again: it should succeed, even though
        # there was a KeyError due to a missing RSI when computing the bill
        self.reebill_processor.new_version(account, 1)
        reebill_data = self.views.get_reebill_metadata_json(account)
        self.assertEquals(1, reebill_data[0]['version'])

    def test_late_charge_correction(self):
        acc = self.account
        # set customer late charge rate
        customer = self.state_db.get_reebill_customer(acc)
        customer.set_discountrate(.5)
        customer.set_late_charge_rate(.34)

        # first utility bill (ensure that an RSI and a charge exist,
        # and mark as "processed" so next utility bill will have them too
        charge = self.utilbill_processor.add_charge(self.utilbill.id)
        self.utilbill_processor.update_charge(
            dict(rsi_binding='THE_CHARGE',
                 quantity_formula=Charge.get_simple_formula(Register.TOTAL),
                 unit='therms', rate=1), charge_id=charge.id)

        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)

        # 2nd utility bill
        u2 = self.utilbill_processor.upload_utility_bill(
            acc, StringIO('February 2000'), date(2000, 2, 1), date(2000, 3, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(u2.id, processed=True)

        # 1st reebill, with a balance of 100, issued 40 days ago and unpaid
        # (so it's 10 days late)
        one = self.reebill_processor.roll_reebill(acc,
                                                  start_date=date(2000, 1, 1))
        # TODO control amount of renewable energy given by mock_skyliner
        # so there's no need to replace that value with a known one here
        one.set_renewable_energy_reading(Register.TOTAL, 100 * 1e5)
        self.reebill_processor.compute_reebill(acc, 1)
        self.assertAlmostEqual(50.0, one.ree_charge)
        self.assertAlmostEqual(50.0, one.balance_due)
        self.reebill_processor.issue(
            acc, 1, issue_date=datetime.utcnow() - timedelta(40))

        # 2nd reebill, which will get a late charge from the 1st
        two = self.reebill_processor.roll_reebill(acc)

        # "bind REE" in 2nd reebill
        # (it needs energy data only so its correction will have the same
        # energy in it as the original version; only the late charge will
        # differ)
        self.reebill_processor.ree_getter.update_renewable_readings(
            self.nexus_util.olap_id(acc), two)

        # if given a late_charge_rate > 0, 2nd reebill should have a late
        # charge
        two.late_charge_rate = .5
        self.reebill_processor.compute_reebill(acc, 2)
        self.assertEqual(25, two.late_charge)

        # issue 2nd reebill so a new version of it can be created
        self.reebill_processor.issue(acc, 2)

        # add a payment of $30 30 days ago (10 days after 1st reebill was
        # issued). the late fee above is now wrong; it should be 50% of
        # the unpaid $20 instead of 50% of the entire $50.
        self.payment_dao.create_payment(acc, datetime.utcnow() - timedelta(30),
                                        'backdated payment', 30)

        # now a new version of the 2nd reebill should have a different late
        # charge: $10 instead of $50.
        self.reebill_processor.new_version(acc, 2)
        two_1 = self.state_db.get_reebill(acc, 2, version=1)
        assert two_1.late_charge_rate == .5
        self.reebill_processor.compute_reebill(acc, 2, version=1)
        self.assertEqual(10, two_1.late_charge)

        # that difference should show up as an error
        corrections = self.reebill_processor.get_unissued_corrections(acc)
        assert len(corrections) == 1
        # self.assertEquals((2, 1, 25 - 15), corrections[0])
        # for some reason there's a tiny floating-point error in the
        # correction amount so it must be compared with assertAlmostEqual
        # (which doesn't work on tuples)
        sequence, version, amount = corrections[0]
        self.assertEqual(2, sequence)
        self.assertEqual(1, version)
        # TODO: find out why this is -15.000013775364522
        self.assertAlmostEqual(-15, amount, places=2)

    def test_compute_reebill(self):
        '''Basic test of reebill processing with an emphasis on making sure
            the accounting numbers in reebills are correct.
            '''
        account = '99999'
        energy_quantity = 100.0
        payment_amount = 100.0
        self.reebill_processor.ree_getter = MockReeGetter(energy_quantity)

        # create 2 utility bills with 1 charge in them
        self.utilbill_processor.upload_utility_bill(
            account, StringIO('February 2000'), date(2000, 2, 1),
            date(2000, 3, 1), 'gas')
        utilbills_data, _ = self.views.get_all_utilbills_json(
            account, 0, 30)
        id_2, id_1 = (obj['id'] for obj in utilbills_data)
        self.utilbill_processor.add_charge(id_1)
        self.utilbill_processor.update_charge(
            {'rsi_binding': 'THE_CHARGE',
             'quantity_formula': Charge.get_simple_formula(Register.TOTAL),
             'rate': 1},
            utilbill_id=id_1,
            rsi_binding='New Charge 1')
        self.utilbill_processor.update_utilbill_metadata(id_1, processed=True)
        self.utilbill_processor.regenerate_charges(id_2)
        self.utilbill_processor.update_utilbill_metadata(id_2, processed=True)

        # create, process, and issue reebill
        self.reebill_processor.roll_reebill(
            account, start_date=date(2000, 1, 1))
        self.reebill_processor.update_sequential_account_info(
            account, 1, discount_rate=0.5)

        # get renewable energy and compute the reebill. make sure this is
        # idempotent because in the past there was a bug where it was not.
        for i in range(2):
            self.reebill_processor.bind_renewable_energy(account, 1)
            self.reebill_processor.compute_reebill(account, 1)
            self.reebill_processor.update_bill_email_recipient(
                account, 1, 'test@someone.com')
            reebill_data = self.views.get_reebill_metadata_json(account)
            self.assertDictContainsSubset(
                {
                    'sequence': 1,
                    'version': 0,
                    'issued': 0,
                    'issue_date': None,
                    'actual_total': 0.,
                    'hypothetical_total': energy_quantity,
                    'payment_received': 0.,
                    'period_start': date(2000, 1, 1),
                    'period_end': date(2000, 2, 1),
                    'prior_balance': 0.,
                    'processed': False,
                    'ree_charge': energy_quantity * .5,
                    'ree_value': energy_quantity,
                    'services': [],
                    'total_adjustment': 0.,
                    'total_error': 0.,
                    # 'ree_quantity': energy_quantity,
                    'balance_due': energy_quantity * .5,
                    'balance_forward': 0.,
                    'corrections': '(never issued)',
                    'mailto': 'test@someone.com'}, reebill_data[0])

        self.reebill_processor.issue(account, 1, issue_date=datetime(2000, 2,
                                                                     15))
        reebill_data = self.views.get_reebill_metadata_json(account)
        self.assertDictContainsSubset(
            {
                'sequence': 1,
                'version': 0,
                'issued': 1,
                'issue_date': datetime(2000, 2, 15),
                'actual_total': 0.,
                'hypothetical_total': energy_quantity,
                'payment_received': 0.,
                'period_start': date(2000, 1, 1),
                'period_end': date(2000, 2, 1),
                'prior_balance': 0.,
                'processed': 1,
                'ree_charge': energy_quantity * .5,
                'ree_value': energy_quantity,
                'services': [],
                'total_adjustment': 0.,
                'total_error': 0.,
                'balance_due': energy_quantity * .5,
                'balance_forward': 0.0,
                'corrections': '-',
                'email_recipient': 'test@someone.com'
            }, reebill_data[0])
        self.assertAlmostEqual(energy_quantity, reebill_data[0]['ree_quantity'])
        # add a payment so payment_received is not 0
        self.payment_dao.create_payment(account, date(2000, 2, 17),
                                        'a payment for the first reebill',
                                        payment_amount)

        # 2nd reebill
        self.reebill_processor.roll_reebill(account)
        self.reebill_processor.update_sequential_account_info(account, 2,
                                                              discount_rate=0.2)
        self.reebill_processor.compute_reebill(account, 2)
        reebill_data = self.views.get_reebill_metadata_json(account)
        dictionaries = [
            {
                'sequence': 2,
                'version': 0L,
                'issued': 0,
                'issue_date': None,
                'actual_total': 0,
                'hypothetical_total': energy_quantity,
                'payment_received': payment_amount,
                'period_start': date(2000, 2, 1),
                'period_end': date(2000, 3, 1),
                'prior_balance': energy_quantity * .5,
                'processed': 0,
                'ree_charge': energy_quantity * .8,
                'ree_value': energy_quantity,
                'services': [],
                'total_adjustment': 0,
                'total_error': 0.0,
                'balance_due': energy_quantity * .5 +
                               energy_quantity * .8 - payment_amount,
                'balance_forward': energy_quantity * .5 -
                                   payment_amount,
                'corrections': '(never issued)',
            }, {
                'sequence': 1L,
                'version': 0L,
                'issued': 1,
                'issue_date': datetime(2000, 2, 15),
                'actual_total': 0,
                'hypothetical_total': energy_quantity,
                'payment_received': 0.0,
                'period_start': date(2000, 1, 1),
                'period_end': date(2000, 2, 1),
                'prior_balance': 0,
                'processed': 1,
                'ree_charge': energy_quantity * .5,
                'ree_value': energy_quantity,
                'services': [],
                'total_adjustment': 0,
                'total_error': 0.0,
                'balance_due': energy_quantity * .5,
                'balance_forward': 0.0,
                'corrections': '-',
            }]

        for i, reebill_dct in enumerate(reebill_data):
            self.assertDictContainsSubset(dictionaries[i], reebill_dct)
        self.assertAlmostEqual(reebill_data[0]['ree_quantity'], energy_quantity)
        self.assertAlmostEqual(reebill_data[1]['ree_quantity'], energy_quantity)

        # make a correction on reebill #1: payment does not get applied to
        # #1, and does get applied to #2
        # NOTE because #1-1 is unissued, its utility bill document should
        # be "current", not frozen
        self.reebill_processor.new_version(account, 1)
        self.reebill_processor.compute_reebill(account, 1)
        self.reebill_processor.compute_reebill(account, 2)
        reebill_data = self.views.get_reebill_metadata_json(account)
        dictionaries = [
            {
                'sequence': 2,
                'version': 0,
                'issued': 0,
                'issue_date': None,
                'actual_total': 0,
                'hypothetical_total': energy_quantity,
                'payment_received': payment_amount,
                'period_start': date(2000, 2, 1),
                'period_end': date(2000, 3, 1),
                'prior_balance': energy_quantity * .5,
                'processed': 0,
                'ree_charge': energy_quantity * .8,
                'ree_value': energy_quantity,
                'services': [],
                'total_adjustment': 0,
                'total_error': 0,
                'balance_due': energy_quantity * .5 +
                               energy_quantity * .8 - payment_amount,
                'balance_forward': energy_quantity * .5 -
                                   payment_amount,
                'corrections': '(never issued)',
            }, {
                'sequence': 1,
                'version': 1,
                'issued': 0,
                'issue_date': None,
                'actual_total': 0,
                'hypothetical_total': energy_quantity,
                'payment_received': 0,
                'period_start': date(2000, 1, 1),
                'period_end': date(2000, 2, 1),
                'prior_balance': 0,
                'processed': 0,
                'ree_charge': energy_quantity * .5,
                'ree_value': energy_quantity,
                'services': [],
                'total_adjustment': 0,
                'total_error': 0,
                'balance_due': energy_quantity * .5,
                'balance_forward': 0,
                'corrections': '#1 not issued',
            }]

        for i, reebill_dct in enumerate(reebill_data):
            self.assertDictContainsSubset(dictionaries[i], reebill_dct)
        self.assertAlmostEqual(reebill_data[0]['ree_quantity'], energy_quantity)
        self.assertAlmostEqual(reebill_data[1]['ree_quantity'], energy_quantity)

    def test_payment_application(self):
        """Test that payments are applied to reebills according their "date
            received", including when multiple payments are applied and multiple
            bills are issued in the same day.
            """
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)
        ub = self.utilbill_processor.upload_utility_bill(
            self.account, StringIO('February'), date(2000, 2, 1),
            date(2000, 3, 1), 'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)
        ub = self.utilbill_processor.upload_utility_bill(
            self.account, StringIO('March'), date(2000, 3, 1), date(2000, 4, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(ub.id, processed=True)

        # create 2 reebills
        reebill_1 = self.reebill_processor.roll_reebill(
            self.account, start_date=date(2000, 1, 1))
        reebill_2 = self.reebill_processor.roll_reebill(self.account)

        # 1 payment applied today at 1:00, 1 payment applied at 2:00
        self.payment_dao.create_payment(self.account, datetime(2000, 1, 1, 1),
                                        'one', 10)
        self.payment_dao.create_payment(self.account, datetime(2000, 1, 1, 2),
                                        'two', 12)

        # 1st reebill has both payments applied to it, 2nd has neither
        self.reebill_processor.compute_reebill(self.account, 1)
        self.reebill_processor.compute_reebill(self.account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(0, reebill_2.payment_received)

        # issue the 1st bill
        self.reebill_processor.issue(self.account, 1,
                                     issue_date=datetime(2000, 1, 1, 3))
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(0, reebill_2.payment_received)
        self.reebill_processor.compute_reebill(self.account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(0, reebill_2.payment_received)

        # now later payments apply to the 2nd bill
        self.payment_dao.create_payment(self.account,
                                        datetime(2000, 1, 1, 3), 'three', 30)
        self.reebill_processor.compute_reebill(self.account, 2)
        self.assertEqual(30, reebill_2.payment_received)

        # even when a correction is made on the 1st bill
        self.reebill_processor.new_version(self.account, 1)
        self.reebill_processor.compute_reebill(self.account, 1)
        self.reebill_processor.compute_reebill(self.account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(30, reebill_2.payment_received)

        # a payment that is backdated to before a corrected bill was issued
        # does not appear on the corrected version
        self.payment_dao.create_payment(
            self.account, datetime(2000, 1, 1, 2,  30),
            'backdated payment', 230)
        self.reebill_processor.compute_reebill(self.account, 1)
        self.reebill_processor.compute_reebill(self.account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(30, reebill_2.payment_received)

    def test_payments(self):
        '''tests creating, updating, deleting and retrieving payments'''
        account = '99999'
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)

        # create a reebill
        reebill = self.reebill_processor.roll_reebill(
            account, start_date=date(2000, 1, 1))

        # 1 payment applied today at 1:00, 1 payment applied at 2:00
        self.payment_dao.create_payment(account, datetime(2000, 1, 1, 1), 'one',
                                        10)
        self.payment_dao.create_payment(account, datetime(2000, 1, 1, 2), 'two',
                                        12)

        #self.reebill_processor.compute_reebill(account, 1)

        payments = [p.column_dict() for p in self.payment_dao.get_payments(
            account)]
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments[0]['credit'], 10)
        self.assertEqual(payments[1]['credit'], 12)
        self.payment_dao.update_payment(payments[0]['id'], payments[0][
            'date_applied'], 'changed credit', 20)
        payments = [p.column_dict() for p in self.payment_dao.get_payments(
            account)]
        self.assertEqual(payments[0]['credit'], 20)
        self.payment_dao.delete_payment(payments[0]['id'])
        self.assertEqual(len(self.payment_dao.get_payments(account)), 1)

        # 1st reebill has the only payment applied to it,
        self.reebill_processor.compute_reebill(account, 1)
        self.reebill_processor.issue(account, 1)
        payment = self.payment_dao.get_payments(account)[0].column_dict()
        self.assertRaises(IssuedBillError, self.payment_dao.delete_payment,
                          payment['id'])

    def test_update_readings(self):
        '''Simple test to get coverage on Process.update_reebill_readings.
        This can be expanded or merged into another test method later on.
        '''
        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)
        self.reebill_processor.roll_reebill(self.account,
                                            start_date=date(2000, 1, 1))
        self.reebill_processor.update_reebill_readings(self.account, 1)
        self.reebill_processor.update_sequential_account_info(self.account, 1,
                                                              processed=True)
        with self.assertRaises(ProcessedBillError):
            self.reebill_processor.update_reebill_readings(self.account, 1)
        self.reebill_processor.issue(self.account, 1)
        with self.assertRaises(IssuedBillError):
            self.reebill_processor.update_reebill_readings(self.account, 1)

    def test_compute_realistic_charges(self):
        '''Tests computing utility bill charges and reebill charge for a
        reebill based on the utility bill, using a set of charge from an actual
        bill.
        '''
        account = '99999'
        # create utility bill and reebill
        utilbill_id = self.views.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']

        formula = Charge.get_simple_formula(Register.TOTAL)
        example_charge_fields = [
            dict(rate=23.14,
                 rsi_binding='PUC',
                 description='Peak Usage Charge',
                 quantity_formula='1'),
            dict(rate=0.03059,
                 rsi_binding='RIGHT_OF_WAY',
                 roundrule='ROUND_HALF_EVEN',
                 quantity_formula=formula),
            dict(rate=0.01399,
                 rsi_binding='SETF',
                 roundrule='ROUND_UP',
                 quantity_formula=formula),
            dict(rsi_binding='SYSTEM_CHARGE',
                 rate=11.2,
                 quantity_formula='1'),
            dict(rsi_binding='DELIVERY_TAX',
                 rate=0.07777,
                 unit='therms',
                 quantity_formula=formula),
            dict(rate=.2935,
                 rsi_binding='DISTRIBUTION_CHARGE',
                 roundrule='ROUND_UP',
                 quantity_formula=formula),
            dict(rate=.7653,
                 rsi_binding='PGC',
                 quantity_formula=formula),
            dict(rate=0.006,
                 rsi_binding='EATF',
                 quantity_formula=formula),
            dict(rate=0.06,
                 rsi_binding='SALES_TAX',
                 quantity_formula=(
                     'SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + '
                     'PGC.total + RIGHT_OF_WAY.total + PUC.total + '
                     'SETF.total + EATF.total + DELIVERY_TAX.total'))
        ]

        # there are no charges in this utility bill yet because there are no
        # other utility bills in the db, so add charges. (this is the same way
        # the user would manually add charges when processing the
        # first bill for a given rate structure.)
        for fields in example_charge_fields:
            self.utilbill_processor.add_charge(utilbill_id)
            self.utilbill_processor.update_charge(
                fields, utilbill_id=utilbill_id, rsi_binding="New Charge 1")

        self.utilbill_processor.update_utilbill_metadata(utilbill_id,
                                                         processed=True)

        # ##############################################################
        # check that each actual (utility) charge was computed correctly:
        quantity = self.views.get_registers_json(
            utilbill_id)[0]['quantity']
        actual_charges = self.views.get_utilbill_charges_json(
            utilbill_id)

        def get_total(rsi_binding):
            charge = next(c for c in actual_charges
                          if c['rsi_binding'] == rsi_binding)
            return charge['total']

        self.assertEqual(11.2, get_total('SYSTEM_CHARGE'))
        self.assertEqual(0.03059 * quantity, get_total('RIGHT_OF_WAY'))
        self.assertEqual(0.01399 * quantity, get_total('SETF'))
        self.assertEqual(0.006 * quantity, get_total('EATF'))
        self.assertEqual(0.07777 * quantity, get_total('DELIVERY_TAX'))
        self.assertEqual(23.14, get_total('PUC'))
        self.assertEqual(.2935 * quantity, get_total('DISTRIBUTION_CHARGE'))
        self.assertEqual(.7653 * quantity, get_total('PGC'))
        # sales tax depends on all of the above
        non_tax_rsi_bindings = [
            'SYSTEM_CHARGE',
            'DISTRIBUTION_CHARGE',
            'PGC',
            'RIGHT_OF_WAY',
            'PUC',
            'SETF',
            'EATF',
            'DELIVERY_TAX'
        ]
        self.assertEqual(
            round(0.06 * sum(map(get_total, non_tax_rsi_bindings)), 2),
            get_total('SALES_TAX'))

        # ##############################################################
        # check that each hypothetical charge was computed correctly:
        self.reebill_processor.roll_reebill(
            account, start_date=date(2000, 1, 1))
        reebill = self.reebill_processor.compute_reebill(account, 1)
        reebill_charges = \
            self.reebill_processor.get_hypothetical_matched_charges(reebill.id)

        def get_h_total(rsi_binding):
            charge = next(c for c in reebill_charges
                          if c['rsi_binding'] == rsi_binding)
            return charge['total']

        h_quantity = self.views.get_reebill_metadata_json(
            account)[0]['ree_quantity']
        self.assertEqual(11.2, get_h_total('SYSTEM_CHARGE'))
        self.assertEqual(round(0.03059 * h_quantity, 2),
                         get_h_total('RIGHT_OF_WAY'))
        self.assertEqual(round(0.01399 * h_quantity, 2), get_h_total('SETF'))
        self.assertEqual(round(0.006 * h_quantity, 2), get_h_total('EATF'))
        self.assertEqual(round(0.07777 * h_quantity, 2),
                         get_h_total('DELIVERY_TAX'))
        self.assertEqual(23.14, get_h_total('PUC'))
        self.assertEqual(round(.2935 * h_quantity, 2),
                         get_h_total('DISTRIBUTION_CHARGE'))
        self.assertEqual(round(.7653 * h_quantity, 2), get_h_total('PGC'))
        self.assertEqual(
            round(0.06 * sum(map(get_h_total, non_tax_rsi_bindings)), 2),
            get_h_total('SALES_TAX'))

    def test_delete_utility_bill_with_reebill(self):
        account = '99999'
        start, end = date(2000, 1, 1), date(2000, 2, 1)
        # create utility bill in MySQL, Mongo, and filesystem (and make
        # sure it exists all 3 places)
        utilbills_data, count = self.views.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(1, count)

        self.utilbill_processor.update_utilbill_metadata(self.utilbill.id,
                                                         processed=True)

        # when utilbill is attached to reebill, deletion should fail
        self.reebill_processor.roll_reebill(account, start_date=start)
        reebills_data = self.views.get_reebill_metadata_json(account)
        self.assertEqual(1, len(reebills_data))
        self.assertEqual(1, reebills_data[0]['sequence'])
        self.assertRaises(BillingError,
                          self.utilbill_processor.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

        # deletion should fail if any version of a reebill has an
        # association with the utility bill. so issue the reebill, add
        # another utility bill, and create a new version of the reebill
        # attached to that utility bill instead.
        self.reebill_processor.issue(account, 1)
        self.reebill_processor.new_version(account, 1)
        self.utilbill_processor.upload_utility_bill(account, StringIO("test2"),
                                                    date(2000, 2, 1), date(2000, 3, 1),
                                                    'gas')
        # TODO this may not accurately reflect the way reebills get
        # attached to different utility bills; see
        # https://www.pivotaltracker.com/story/show/51935657
        self.assertRaises(BillingError,
                          self.utilbill_processor.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

    def test_two_registers_one_reading(self):
        '''Test the situation where a utiltiy bill has 2 registers, but its
        reebill has only one reading corresponding to the first register,
        so only that register gets offset by renewable energy.

        This has been done in cases where there are two "total" registers
        that get added together to measure total energy, and sometimes users
        have created two registers to represent two different utility meter
        reads that occurred within one billing period, with different pricing
        applied to each one, and want to avoid charging the customer for
        twice as much renewable energy as they actually consumed. (This is
        not strictly correct because the energy would be priced differently
        depending on which part of the period it was consumed in.)
        '''
        # utility bill with 2 registers
        utilbill_id = self.views.get_all_utilbills_json(
            '99999', 0, 30)[0][0]['id']
        def add_2nd_register():
            self.utilbill_processor.new_register(utilbill_id)
            register_id = self.views.get_registers_json(
                utilbill_id)[1]['id']
            self.utilbill_processor.update_register(
                register_id, {'register_binding': Register.DEMAND})
        add_2nd_register()

        # the utility bill must have some charges that depend on both
        # registers' values
        self.utilbill_processor.add_charge(utilbill_id)
        self.utilbill_processor.update_charge(
            {'rsi_binding': 'A',
             'quantity_formula': Charge.get_simple_formula(Register.TOTAL),
             'rate': 1}, utilbill_id=utilbill_id, rsi_binding='New Charge 1')
        self.utilbill_processor.add_charge(utilbill_id)
        self.utilbill_processor.update_charge(
            { 'rsi_binding': 'B',
              'quantity_formula': Charge.get_simple_formula(Register.DEMAND),
              'rate': 1}, utilbill_id=utilbill_id, rsi_binding='New Charge 1')
        self.utilbill_processor.update_utilbill_metadata(utilbill_id,
                                                         processed=True)

        reebill = self.reebill_processor.roll_reebill(
            '99999', start_date=date(2000,1,1))

        # verify reebill has a reading only for total register (currently
        # there is no way to do this through the UI)
        self.assertEqual(1, len(reebill.readings))
        self.assertEqual(Register.TOTAL, reebill.readings[0].register_binding)

        self.reebill_processor.compute_reebill('99999', 1)
        self.reebill_processor.bind_renewable_energy('99999', 1)
        self.reebill_processor.compute_reebill('99999', 1)
        energy_1 = self.views.get_reebill_metadata_json(
            '99999')[0]['ree_quantity']

        # when a correction is made, the readings are those of the original
        # reebill; they are not updated to match the utility bill
        # (bug BILL-5814)
        self.reebill_processor.issue('99999', 1, issue_date=datetime(2000,2,5))
        self.reebill_processor.new_version('99999', 1)
        reebill = Session().query(ReeBill).filter_by(version=1).one()
        self.assertEqual(1, len(reebill.readings))
        self.assertEqual(Register.TOTAL, reebill.readings[0].register_binding)
        self.assertAlmostEqual(energy_1,
                               reebill.readings[0].renewable_quantity, places=4)

        # "update readings" causes another reading to be added for the 2nd
        # register of the utility bill
        self.reebill_processor.update_reebill_readings('99999', 1)
        self.assertEqual(2, len(reebill.readings))
        self.assertEqual(Register.DEMAND, reebill.readings[1].register_binding)

        self.reebill_processor.bind_renewable_energy('99999', 1)
        energy_2 = (self.views.get_reebill_metadata_json('99999')[0]
                    ['ree_quantity'])

        # the total amount of renewable energy should now be double what it was
        # when there was only one register
        self.assertEqual(energy_2, 2 * energy_1)

    def test_processed_utilbill(self):
        '''A Reebill can only ony be created with a utility bill that is
        processed.
        '''
        # not processed: bad
        with self.assertRaises(BillingError):
            self.reebill_processor.roll_reebill(
                self.account, start_date=self.utilbill.period_start)

        # processed: good
        self.utilbill.processed = True
        self.reebill_processor.roll_reebill(
            self.account, start_date=self.utilbill.period_start)

class TestTouMetering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # these objects don't change during the tests, so they should be
        # created only once.
        cls.utilbill_processor = create_utilbill_processor()
        cls.billupload = cls.utilbill_processor.bill_file_handler
        cls.reebill_processor, cls.views = create_reebill_objects()
        cls.nexus_util = create_nexus_util()
        cls.mailer = cls.reebill_processor.bill_mailer

    def setUp(self):
        clear_db()
        TestCaseWithSetup.insert_data()

        self.utilbill = self.utilbill_processor.upload_utility_bill(
            '99999', StringIO('test'), date(2000, 1, 1), date(2000, 2, 1),
            'gas')
        self.utility = self.utilbill.get_utility()
        s = Session()
        self.utility_account = s.query(UtilityAccount).filter_by(
            account='99999').one()
        self.customer = s.query(ReeBillCustomer).filter_by(
            utility_account_id=self.utility_account.id).one()

    def tearDown(self):
        clear_db()

    def test_tou_metering(self):
        # TODO: possibly move to test_fetch_bill_data
        account = '99999'

        def get_mock_energy_consumption(install, start, end, measure,
                                        ignore_misisng=True, verbose=False):
            assert start, end == (date(2000, 1, 1), date(2000, 2, 1))
            result = []
            for hourly_period in cross_range(start, end):
                # for a holiday (Jan 1), weekday (Fri Jan 14), or weekend
                # (Sat Jan 15), return number of BTU equal to the hour of
                # the day. no energy is consumed on other days.
                if hourly_period.day in (1, 14, 15):
                    result.append(hourly_period.hour)
                else:
                    result.append(0)
            assert len(result) == 31 * 24  # hours in January
            return result

        self.reebill_processor.ree_getter.get_billable_energy_timeseries = \
            get_mock_energy_consumption

        # modify registers of this utility bill so they are TOU
        u = Session().query(UtilBill).join(UtilityAccount). \
            filter_by(account=account).one()
        active_periods = {
            'active_periods_weekday': [[9, 9]],
            'active_periods_weekend': [[11, 11]],
            'active_periods_holiday': [],
            }
        r = self.utilbill_processor.new_register(u.id)
        self.utilbill_processor.update_register(r.id, {
            'description': 'time-of-use register',
            'quantity': 0,
            'unit': 'BTU',
            'identifier': 'test2',
            'estimated': False,
            'reg_type': 'tou',
            'register_binding': Register.PEAK,
            'meter_identifier': '',
            # these periods do not actually correspond to normal peak time
            'active_periods': active_periods
        })
        self.utilbill_processor.update_utilbill_metadata(u.id,
                                                         processed=True)
        self.reebill_processor.roll_reebill(account,
                                            start_date=date(2000, 1, 1))

        # the reebill starts with one reading corresponding to "reg_total"
        # so the "update readings" feature must be used to get all 3
        self.reebill_processor.update_reebill_readings(account, 1)
        self.reebill_processor.bind_renewable_energy(account, 1)

        # the total energy consumed over the 3 non-0 days is
        # 3 * (0 + 2 + ... + 23) = 23 * 24 / 2 = 276.
        # when only the hours 9 and 11 are included, the total is just
        # 9 + 11 + 11 = 33.
        total_renewable_btu = 23 * 24 / 2. * 3
        total_renewable_therms = total_renewable_btu / 1e5
        tou_renewable_btu = 9 + 11 + 11

        # check reading of the reebill corresponding to the utility register
        reebill = Session().query(ReeBill).one()
        total_reading, tou_reading = reebill.readings
        self.assertAlmostEqual('therms', total_reading.unit)
        self.assertAlmostEqual(total_renewable_therms,
                               total_reading.renewable_quantity)
        self.assertEqual('BTU', tou_reading.unit)
        self.assertAlmostEqual(tou_renewable_btu,
                               tou_reading.renewable_quantity)

    def test_summary(self):
        """Issuing a summary bill for a group of accounts.
        """
        # setup: 2 different customers are needed, so another one must be
        # created
        self.utilbill.processed = True
        ua2 = UtilityAccount('', '88888', self.utilbill.utility, None, None,
                             Address(), Address())
        customer2 = ReeBillCustomer(utility_account=ua2, name='')
        utilbill2 = self.utilbill.clone()
        utilbill2.utility = self.utilbill.utility
        utilbill2.registers = [self.utilbill.registers[0].clone()]
        utilbill2.billing_address = utilbill2.service_address = Address()
        utilbill2.utility_account = ua2
        s = Session()
        s.add_all([ua2, customer2, utilbill2])

        group = CustomerGroup(name='Example Property Management Co.',
                              bill_email_recipient='example@example.com')
        group.add(self.customer)
        group.add(customer2)

        # create two reebills for two different customers in the group
        self.reebill_processor.roll_reebill(
            self.customer.get_account(), start_date=self.utilbill.period_start)
        self.reebill_processor.toggle_reebill_processed(
            self.customer.get_account(), 1, False)
        self.reebill_processor.roll_reebill(utilbill2.utility_account.account,
                                            start_date=utilbill2.period_start)
        self.reebill_processor.toggle_reebill_processed(
            utilbill2.utility_account.account, 1, False)
        # TODO: it would be a good idea to test issuing corrections along
        # with these

        # create and send the summary bill
        self.reebill_processor.issue_summary_for_bills(group.get_bills_to_issue(), group.bill_email_recipient)

        # don't care about email details
        self.mailer.mail.assert_called()

        # both bills should now be issued
        self.assertTrue(self.customer.reebills[0].issued)
        self.assertTrue(customer2.reebills[0].issued)
