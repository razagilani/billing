import json
import unittest
from StringIO import StringIO
from datetime import date, datetime, timedelta

from mock import Mock
from sqlalchemy.orm.exc import NoResultFound

from skyliner.sky_handlers import cross_range
from billing.processing.state import ReeBill, Customer, UtilBill, Register
from billing.test.setup_teardown import TestCaseWithSetup
from billing.exc import BillStateError, FormulaSyntaxError, NoSuchBillException, \
    ConfirmAdjustment, ProcessedBillError, IssuedBillError
from billing.test import testing_utils

class MockReeGetter(object):
    def __init__(self, quantity):
        self.quantity = quantity

    def update_renewable_readings(self, olap_id, reebill,
                                  use_olap=True, verbose=False):
        for reading in reebill.readings:
            reading.renewable_quantity = self.quantity

class ProcessTest(TestCaseWithSetup, testing_utils.TestCase):
    '''Tests that involve both utility bills and reebills. TODO: each of
    these should be separated apart and put in one of the other classes
    below, or made into some kind of multi-application integrationt test.
    '''

    def test_delete_utility_bill_with_reebill(self):
        account = '99999'
        start, end = date(2012, 1, 1), date(2012, 2, 1)
        # create utility bill in MySQL, Mongo, and filesystem (and make
        # sure it exists all 3 places)
        self.process.upload_utility_bill(account, 'gas', start, end,
                                         StringIO("test"), 'january.pdf')
        utilbills_data, count = self.process.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(1, count)

        # when utilbill is attached to reebill, deletion should fail
        self.process.roll_reebill(account, start_date=start)
        reebills_data = self.process.get_reebill_metadata_json(account)
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
                                          'period_end': date(2012, 2, 1),
                                          'period_start': date(2012, 1, 1),
                                          'prior_balance': 0,
                                          'processed': 0,
                                          'ree_charge': 0.0,
                                          'ree_quantity': 22.602462036826545,
                                          'ree_value': 0,
                                          'sequence': 1,
                                          'services': [],
                                          'total_adjustment': 0,
                                          'total_error': 0.0
                                      }, reebills_data[0])
        self.assertRaises(ValueError,
                          self.process.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

        # deletion should fail if any version of a reebill has an
        # association with the utility bill. so issue the reebill, add
        # another utility bill, and create a new version of the reebill
        # attached to that utility bill instead.
        self.process.issue(account, 1)
        self.process.new_version(account, 1)
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO("test"),
                                         'january-electric.pdf')
        # TODO this may not accurately reflect the way reebills get
        # attached to different utility bills; see
        # https://www.pivotaltracker.com/story/show/51935657
        self.assertRaises(ValueError,
                          self.process.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])


class ReebillProcessingTest(TestCaseWithSetup, testing_utils.TestCase):
    '''Integration tests for the ReeBill application back end including
    database.
    These testse unavoidably involve creating/editing utility bills, because
    those are needed to create reebills, but that should become part of the
    setup process for each testj and there is no need to make assertions about
    the behavior of code that only involves utility bills.
    '''
    def setup_dummy_utilbill_calc_charges(self, acc, begin_date, end_date):
        """Upload a dummy-utilbill, add an RSI, and calculate charges
        """
        utilbill = self.process.upload_utility_bill(acc,
                                                    'gas', begin_date, end_date,
                                                    StringIO('a utility bill'),
                                                    'filename.pdf')
        self.process.add_charge(utilbill.id)
        self.process.update_charge({
                                       'rsi_binding': 'A',
                                       'quantity_formula': 'REG_TOTAL.quantity',
                                       'rate': 1
                                   }, utilbill_id=utilbill.id, rsi_binding='New RSI #1')
        self.process.refresh_charges(utilbill.id)  # creates charges
        self.process.compute_utility_bill(utilbill.id)  # updates charge values
    def test_list_account_status(self):
        count, data = self.process.list_account_status()
        self.assertEqual(3, count)
        self.assertEqual([{
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_service_address': None,
            'fb_utility_name': 'Test Utility Company Template',
            'lastrateclass': '',
            'casualname': 'Example 1',
            'lastutilityserviceaddress': '',
            'lastissuedate': '',
            'provisionable': False,
            'codename': '',
            'lastperiodend': None,
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
            }, {
            'account': '100001',
            'fb_rate_class': 'Other Rate Class',
            'fb_service_address': False,
            'fb_utility_name': 'Other Utility',
            'lastrateclass': 'Other Rate Class',
            'casualname': 'Example 4',
            'lastutilityserviceaddress': '123 Test Street, Test City, XX',
            'lastissuedate': '',
            'provisionable': False,
            'codename': '',
            'lastperiodend': date(2012, 1, 31),
            'primusname': '1788 Massachusetts Ave.',
            'lastevent': '',
            }, {
            'account': '100000',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_service_address': False,
            'fb_utility_name': 'Test Utility Company Template',
            'lastrateclass': 'Test Rate Class Template',
            'casualname': 'Example 3',
            'lastutilityserviceaddress': '123 Test Street, Test City, XX',
            'lastissuedate': '',
            'provisionable': False,
            'codename': '',
            'lastperiodend': date(2012, 2, 28),
            'primusname': '1787 Massachusetts Ave.',
            'lastevent': '',
        }], data)

        # get only one account
        count, data = self.process.list_account_status(account='99999')
        self.assertEqual(1, count)
        self.assertEqual([{
            'account': '99999',
            'fb_rate_class': 'Test Rate Class Template',
            'fb_service_address': None,
            'fb_utility_name': 'Test Utility Company Template',
            'lastrateclass': '',
            'casualname': 'Example 1',
            'lastutilityserviceaddress': '',
            'lastissuedate': '',
            'provisionable': False,
            'codename': '',
            'lastperiodend': None,
            'primusname': '1785 Massachusetts Ave.',
            'lastevent': '',
        }], data)

    def test_get_late_charge(self):
        '''Tests computation of late charges.
        '''
        # TODO: when possible, convert this into a unit test that checks the
        # get_late_charge method, whatever class it may belong to by then
        # (ReeBill?). See 69883814.
        acc = '99999'
        # create utility bill with a charge in it
        u = self.process.upload_utility_bill(acc, 'gas',
                                             date(2000, 1, 1), date(2000, 2, 1),
                                             StringIO('January 2000'), 'january.pdf')
        self.process.add_charge(u.id)
        self.process.update_charge({
                                       'rsi_binding': 'THE_CHARGE',
                                       'quantity_formula': 'REG_TOTAL.quantity',
                                       'quantity_units': 'therms',
                                       'rate': 1,
                                       'group': 'All Charges',
                                       }, utilbill_id=u.id, rsi_binding='New RSI #1')
        self.process.refresh_charges(u.id)
        self.process.update_utilbill_metadata(u.id, processed=True)

        # create first reebill
        bill1 = self.process.roll_reebill(acc, start_date=date(2000, 1, 1))
        self.process.update_sequential_account_info(acc, 1,
                                                    discount_rate=.5, late_charge_rate=.34)
        self.process.ree_getter = MockReeGetter(100)
        self.process.bind_renewable_energy(acc, 1)
        self.process.compute_reebill(acc, 1)
        self.assertEqual(0, self.process.get_late_charge(bill1,
                                                         date(1999, 12, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                                                         date(2000, 1, 1)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                                                         date(2000, 1, 2)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                                                         date(2000, 2, 1)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                                                         date(2000, 2, 2)))

        # issue first reebill, so a later bill can have a late charge
        # based on the customer's failure to pay bill1 by its due date,
        # i.e. 30 days after the issue date.
        self.process.issue(acc, bill1.sequence, issue_date=datetime(2000, 4, 1))
        self.assertEqual(date(2000, 5, 1), bill1.due_date)
        self.assertEqual(50, bill1.balance_due)
        # create 2nd utility bill and reebill
        u2 = self.process.upload_utility_bill(acc, 'gas', date(2000, 2, 1),
                                              date(2000, 3, 1), StringIO('February 2000'), 'february.pdf')
        self.session.flush()

        self.process.update_utilbill_metadata(u2.id, processed=True)
        bill2 = self.process.roll_reebill(acc)
        self.process.update_sequential_account_info(acc, 2,
                                                    discount_rate=.5, late_charge_rate=.34)
        self.process.ree_getter = MockReeGetter(200)
        self.process.bind_renewable_energy(acc, 2)
        self.process.compute_reebill(acc, 2)
        assert bill2.discount_rate == 0.5
        assert bill2.ree_charge == 100

        # bill2's late charge should be 0 before bill1's due date; on/after
        # the due date, it's balance * late charge rate, i.e.
        # 50 * .34 = 17
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(1999, 12, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2000, 1, 2)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2000, 3, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2000, 4, 1)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2000, 4, 2)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2000, 4, 30)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2000, 5, 1)))
        self.assertEqual(17, self.process.get_late_charge(bill2,
                                                          date(2000, 5, 2)))
        self.assertEqual(17, self.process.get_late_charge(bill2,
                                                          date(2013, 1, 1)))

        # in order to get late charge of a 3rd bill, bill2 must be computed
        self.process.compute_reebill(acc, 2)

        # create a 3rd bill without issuing bill2. bill3 should have None
        # as its late charge for all dates
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2000, 3, 1), date(2000, 4, 1), StringIO('March 2000'),
                                         'march.pdf')
        bill3 = self.process.roll_reebill(acc)
        self.assertEqual(0, self.process.get_late_charge(bill3,
                                                            date(1999, 12, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill3,
                                                            date(2013, 1, 1)))

        # late charge should be based on the version with the least total
        # of the bill from which it derives. on 2013-01-15, make a version
        # 1 of bill 1 with a lower total, and then on 2013-03-15, a version
        # 2 with a higher total, and check that the late charge comes from
        # version 1.
        self.process.new_version(acc, 1)
        bill1_1 = self.state_db.get_reebill(acc, 1, version=1)
        self.process.ree_getter = MockReeGetter(100)
        self.process.bind_renewable_energy(acc, 1)
        bill1_1.discount_rate = 0.75
        self.process.compute_reebill(acc, 1, version=1)
        self.assertEqual(25, bill1_1.ree_charge)
        self.assertEqual(25, bill1_1.balance_due)
        self.process.issue(acc, 1, issue_date=datetime(2013, 3, 15))
        late_charge_source_amount = bill1_1.balance_due

        self.process.new_version(acc, 1)
        self.process.bind_renewable_energy(acc, 2)
        self.process.update_sequential_account_info(acc, 1,
                                                    discount_rate=.25)
        bill1_2 = self.state_db.get_reebill(acc, 1, version=2)
        self.process.compute_reebill(acc, 1, version=2)
        self.assertEqual(75, bill1_2.ree_charge)
        self.assertEqual(75, bill1_2.balance_due)
        self.process.issue(acc, 1)

        # note that the issue date on which the late charge in bill2 is
        # based is the issue date of version 0--it doesn't matter when the
        # corrections were issued.
        late_charge = self.process.get_late_charge(bill2, date(2013, 4, 18))
        self.assertEqual(late_charge_source_amount * bill2.late_charge_rate,
                         late_charge)

        # add a payment between 2000-01-01 (when bill1 version 0 was
        # issued) and 2013-01-01 (the present), to make sure that payment
        # is deducted from the balance on which the late charge is based
        self.state_db.create_payment(acc, date(2000, 6, 5),
                                     'a $10 payment in june', 10)
        self.assertEqual((late_charge_source_amount - 10) *
                         bill2.late_charge_rate,
                         self.process.get_late_charge(bill2, date(2013, 1, 1)))

        # Pay off the bill, make sure the late charge is 0
        self.process.create_payment(acc, date(2000, 6, 6),
                                    'a $40 payment in june', 40)
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2013, 1, 1)))

        #Overpay the bill, make sure the late charge is still 0
        self.process.create_payment(acc, date(2000, 6, 7),
                                    'a $40 payment in june', 40)
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2013, 1, 1)))

    def test_issue(self):
        '''Tests issuing of reebills.'''
        acc = '99999'
        # two utilbills, with reebills
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO('january 2012'),
                                         'january.pdf')
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('february 2012'),
                                         'february.pdf')
        one = self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        two = self.process.roll_reebill(acc)

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
        self.assertRaises(BillStateError, self.process.issue, acc, 2)

        # issue one
        self.process.issue(acc, 1, issue_date=datetime(2013, 4, 1))

        self.assertEquals(True, one.issued)
        self.assertEquals(True, one.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals(datetime(2013, 4, 1), one.issue_date)
        self.assertEquals((one.issue_date + timedelta(30)).date(), one.due_date)
        self.assertEquals('example@example.com', one.email_recipient)

        customer = self.state_db.get_customer(acc)
        customer.bill_email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue two
        self.process.issue(acc, 2, issue_date=datetime(2013, 5, 1, 12))

        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, two.issued)
        self.assertEquals(True, two.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals(datetime(2013, 5, 1, 12), two.issue_date)
        self.assertEquals((two.issue_date + timedelta(30)).date(), two.due_date)
        self.assertEquals('test1@example.com, test2@exmaple.com',
                          two.email_recipient)

    def test_issue_2_at_once(self):
        '''Tests issuing one bill immediately after another, without
        recomputing it. In bug 64403990, a bill could be issued with a wrong
        "prior balance" because it was not recomputed before issuing to
        reflect a change to its predecessor.
        '''
        acc = '99999'
        # first reebill is needed so the others get computed correctly
        self.process.upload_utility_bill(acc, 'gas', date(2000, 1, 1),
                                         date(2000, 2, 1), StringIO('january 2000'), 'january.pdf')
        self.process.roll_reebill(acc, start_date=date(2000, 1, 1))
        self.process.issue(acc, 1, datetime(2000, 2, 15))

        # two more utility bills and reebills
        self.process.upload_utility_bill(acc, 'gas', date(2000, 2, 1),
                                         date(2000, 3, 1), StringIO('february 2000'), 'february.pdf')
        self.process.upload_utility_bill(acc, 'gas', date(2000, 3, 1),
                                         date(2000, 4, 1), StringIO('february 2000'), 'february.pdf')
        two = self.process.roll_reebill(acc)
        three = self.process.roll_reebill(acc)

        # add a payment, shown on bill #2
        self.state_db.create_payment(acc, date(2000, 2, 16), 'a payment', 100)
        # TODO bill shows 0 because bill has no energy in it and
        # payment_received is 0
        self.process.compute_reebill(acc, 2)
        self.assertEqual(100, two.payment_received)
        self.assertEqual(-100, two.balance_due)

        # the payment does not appear on #3, since #3 has not be
        # recomputed
        self.assertEqual(0, three.payment_received)
        self.assertEqual(0, three.prior_balance)
        self.assertEqual(0, three.balance_forward)
        self.assertEqual(0, three.balance_due)

        # issue #2 and #3
        self.process.issue(acc, 2, datetime(2000, 5, 15))
        self.process.issue(acc, 3, datetime(2000, 5, 15))

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
        acc = '99999'
        # two utilbills, with reebills
        self.process.bill_mailer = Mock()
        self.process.renderer = Mock()
        self.process.renderer.render_max_version.return_value = 1
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO('january 2012'),
                                         'january.pdf')
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('february 2012'),
                                         'february.pdf')
        one = self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        two = self.process.roll_reebill(acc)

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
        self.assertRaises(BillStateError, self.process.issue, acc, 2)
        one.email_recipient = 'one@example.com, one@gmail.com'

        # issue and email one
        self.process.issue_and_mail(False, account=acc, sequence=1,
                                    recipients=one.email_recipient)

        self.assertEquals(True, one.issued)
        self.assertEquals(True, one.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals((one.issue_date + timedelta(30)).date(), one.due_date)

        customer = self.state_db.get_customer(acc)
        two.email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue and email two
        self.process.renderer.render_max_version.return_value = 2
        self.process.issue_and_mail(False, account=acc, sequence=2,
                                    recipients=two.email_recipient)

        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, two.issued)
        self.assertEquals(True, two.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals((two.issue_date + timedelta(30)).date(), two.due_date)

    def test_issue_processed_and_mail(self):
        '''Tests issuing and mailing of processed reebills.'''
        acc = '99999'
        # two utilbills, with reebills
        self.process.bill_mailer = Mock()
        self.process.renderer = Mock()
        self.process.renderer.render_max_version.return_value = 1
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO('january 2012'),
                                         'january.pdf')
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('february 2012'),
                                         'february.pdf')
        one = self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        one.processed = 1
        two = self.process.roll_reebill(acc)
        two.processed = 1

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
        self.assertRaises(BillStateError, self.process.issue, acc, 2)
        one.email_recipient = 'one@example.com, one@gmail.com'

        # issue and email one
        self.process.issue_and_mail(False, processed=True)

        self.assertEquals(True, one.issued)
        self.assertEquals(True, one.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals((one.issue_date + timedelta(30)).date(), one.due_date)

        customer = self.state_db.get_customer(acc)
        two.email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue and email two
        self.process.renderer.render_max_version.return_value = 2
        self.process.issue_and_mail(False, processed=True)

        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, two.issued)
        self.assertEquals(True, two.processed)
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals((two.issue_date + timedelta(30)).date(), two.due_date)

    def test_delete_reebill(self):
        account = '99999'
        # create 2 utility bills for Jan-Feb 2012
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO('january 2012'), 'january.pdf')
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('february 2012'), 'february.pdf')
        utilbill = self.session.query(UtilBill).join(Customer). \
            filter(Customer.account == account).order_by(
            UtilBill.period_start).first()

        reebill = self.process.roll_reebill(account,
                                            start_date=date(2012, 1, 1))
        self.process.roll_reebill(account)

        # only the last reebill is deletable: deleting the 2nd one should
        # succeed, but deleting the 1st one should fail
        with self.assertRaises(IssuedBillError):
            self.process.delete_reebill(account, 1)
        self.process.delete_reebill(account, 2)
        with self.assertRaises(NoResultFound):
            self.state_db.get_reebill(account, 2, version=0)
        self.assertEquals(1, self.session.query(ReeBill).count())
        self.assertEquals([1], self.state_db.listSequences(account))
        self.assertEquals([utilbill], reebill.utilbills)

        # issued reebill should not be deletable
        self.process.issue(account, 1)
        self.assertEqual(1, reebill.issued)
        self.assertEqual([utilbill], reebill.utilbills)
        self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)
        self.assertRaises(IssuedBillError, self.process.delete_reebill,
                          account, 1)

        # create a new verison and delete it, returning to just version 0
        self.process.new_version(account, 1)
        self.session.query(ReeBill).filter_by(version=1).one()
        self.assertEqual(1, self.state_db.max_version(account, 1))
        self.assertFalse(self.state_db.is_issued(account, 1))
        self.process.delete_reebill(account, 1)
        self.assertEqual(0, self.state_db.max_version(account, 1))
        self.assertTrue(self.state_db.is_issued(account, 1))

        # original version should still be attached to utility bill
        # TODO this will have to change. see
        # https://www.pivotaltracker.com/story/show/31629749
        self.assertEqual([utilbill], reebill.utilbills)
        self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)

    def test_correction_adjustment(self):
        '''Tests that adjustment from a correction is applied to (only) the
            earliest unissued bill.'''
        # replace process.ree_getter with one that always sets the renewable
        # energy readings to a known value
        self.process.ree_getter = MockReeGetter(10)
        acc = '99999'

        # create 3 utility bills: Jan, Feb, Mar
        for i in range(3):
            self.setup_dummy_utilbill_calc_charges(acc, date(2012, i + 1, 1),
                                                   date(2012, i + 2, 1))

        # create 1st reebill and issue it
        self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        self.process.bind_renewable_energy(acc, 1)
        self.process.compute_reebill(acc, 1)
        self.process.issue(acc, 1, issue_date=datetime(2012, 3, 15))
        reebill_metadata = self.process.get_reebill_metadata_json('99999')
        self.assertDictContainsSubset({
                                          'sequence': 1,
                                          'version': 0,
                                          'issued': 1,
                                          'issue_date': datetime(2012,3,15),
                                          'actual_total': 0.,
                                          'hypothetical_total': 10,
                                          'payment_received': 0.,
                                          'period_start': date(2012, 1, 1),
                                          'period_end': date(2012, 2, 1),
                                          'prior_balance': 0.,
                                          'processed': 1,
                                          'ree_charge': 8.8,
                                          'ree_value': 10,
                                          'services': [],
                                          'total_adjustment': 0.,
                                          'total_error': 0.,
                                          'ree_quantity': 10,
                                          'balance_due': 8.8,
                                          'balance_forward': 0,
                                          'corrections': '-',
                                          }, reebill_metadata[0])

        # create 2nd reebill, leaving it unissued
        self.process.ree_getter.quantity = 0
        self.process.roll_reebill(acc)
        # make a correction on reebill #1. this time 20 therms of renewable
        # energy instead of 10 were consumed.
        self.process.ree_getter.quantity = 20
        self.process.new_version(acc, 1)
        self.process.compute_reebill(acc, 2)

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
                             'period_end': date(2012, 3, 1),
                             'period_start': date(2012, 2, 1),
                             'prior_balance': 8.8,
                             'processed': 0,
                             'ree_charge': 0.0,
                             'ree_quantity': 0,
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
                             'period_end': date(2012, 2, 1),
                             'period_start': date(2012, 1, 1),
                             'prior_balance': 0,
                             'processed': 0,
                             'ree_charge': 17.6,
                             'ree_quantity': 20,
                             'ree_value': 20,
                             'sequence': 1,
                             'services': [],
                             'total_adjustment': 0,
                             'total_error': 8.8,
                             }], self.process.get_reebill_metadata_json('99999')):
            self.assertDictContainsSubset(x, y)




        # when you make a bill processed and it has corrections applying to it, and you don't specify apply_corrections=True,
        # it raises an exception ConfirmAdjustment
        self.assertRaises(ConfirmAdjustment ,self.process.toggle_reebill_processed, acc, 2, apply_corrections=False)
        self.process.toggle_reebill_processed(acc,2,apply_corrections=True)
        reebill = self.state_db.get_reebill(acc, 2)
        correction = self.state_db.get_reebill(acc, 1, version=1)
        # any processed regular bill or correction can't be modified (compute, bind_ree, sequential_account_info)
        self.assertRaises(ProcessedBillError, self.process.compute_reebill, acc, reebill.sequence)
        self.assertRaises(ProcessedBillError, self.process.bind_renewable_energy, acc, reebill.sequence)
        self.assertRaises(ProcessedBillError, self.process.update_sequential_account_info, acc, reebill.sequence)
        self.assertRaises(ProcessedBillError, self.process.compute_reebill, acc, correction.sequence)
        self.assertRaises(ProcessedBillError, self.process.bind_renewable_energy, acc, correction.sequence)
        self.assertRaises(ProcessedBillError, self.process.update_sequential_account_info, acc, correction.sequence)

        # when you do specify apply_corrections=True, the corrections are marked as processed.
        self.assertEqual(reebill.processed, True)
        self.assertEqual(correction.processed, True)
        # When toggle_reebill_processed is called for a processed reebill, reebill becomes unprocessed
        self.process.toggle_reebill_processed(acc, 2, apply_corrections=False)
        self.assertEqual(reebill.processed, False)
        # when toggle_reebill_processed is called for issued reebill it raises IssuedBillError
        self.process.issue(acc, reebill.sequence, issue_date=datetime(2012,3,10))
        self.assertRaises(IssuedBillError, self.process.bind_renewable_energy, acc, reebill.sequence)
        self.assertRaises(IssuedBillError,
                          self.process.toggle_reebill_processed, acc, reebill.sequence,
                          apply_corrections=False)

    def test_create_first_reebill(self):
        '''Test creating the first utility bill and reebill for an account,
            making sure the reebill is correct with respect to the utility bill.
            '''
        # at first, there are no utility bills
        self.assertEqual(([], 0), self.process.get_all_utilbills_json(
            '99999', 0, 30))

        # upload a utility bill
        self.process.upload_utility_bill('99999', 'gas',
                                         date(2013, 1, 1), date(2013, 2, 1), StringIO('January 2013'),
                                         'january.pdf')

        utilbill_data = self.process.get_all_utilbills_json(
            '99999', 0, 30)[0][0]
        self.assertDictContainsSubset({
                                          'account': '99999',
                                          'computed_total': 0,
                                          'period_end': date(2013, 2, 1),
                                          'period_start': date(2013, 1, 1),
                                          'processed': 0,
                                          'rate_class': 'Test Rate Class Template',
                                          'reebills': [],
                                          'service': 'Gas',
                                          'state': 'Final',
                                          'total_charges': 0.0,
                                          'utility': 'Test Utility Company Template',
                                          }, utilbill_data)

        # create a reebill
        self.process.roll_reebill('99999', start_date=date(2013, 1, 1))

        utilbill_data = self.process.get_all_utilbills_json(
            '99999', 0, 30)[0][0]
        self.assertDictContainsSubset({'issue_date': None, 'sequence': 1, 'version': 0},
                                      utilbill_data['reebills'][0])

        self.assertDictContainsSubset({
                                          'account': '99999',
                                          'computed_total': 0,
                                          'period_end': date(2013, 2, 1),
                                          'period_start': date(2013, 1, 1),
                                          'processed': 0,
                                          'rate_class': 'Test Rate Class Template',
                                          'service': 'Gas', 'state': 'Final',
                                          'total_charges': 0.0,
                                          'utility': 'Test Utility Company Template',
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
        self.process.create_new_account('55555', 'Another New Account',
                                        'thermal', 0.6, 0.2, billing_address,
                                        service_address, '99999')
        self.assertRaises(ValueError, self.process.roll_reebill,
                          '55555', start_date=date(2013, 2, 1))

    def test_uncomputable_correction_bug(self):
        '''Regresssion test for
            https://www.pivotaltracker.com/story/show/53434901.'''
        account = '99999'
        # create reebill and utility bill
        self.process.upload_utility_bill(account, 'gas', date(2013, 1, 1),
                                         date(2013, 2, 1), StringIO('January 2013'), 'january.pdf')
        utilbill_id = self.process.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']
        self.process.roll_reebill(account, start_date=date(2013, 1, 1))
        # bind, compute, issue
        self.process.bind_renewable_energy(account, 1)
        self.process.compute_reebill(account, 1)
        self.process.issue(account, 1)

        # create new version
        self.process.new_version(account, 1)
        self.assertEquals(1, self.state_db.max_version(account, 1))

        # initially, reebill version 1 can be computed without an error
        self.process.compute_reebill(account, 1, version=1)

        # put it in an un-computable state by adding a charge with a syntax
        # error in its formula. it should now raise an RSIError.
        # (computing a utility bill doesn't raise an exception by default, but
        # computing a reebill based on the utility bill does.)
        charge = self.process.add_charge(utilbill_id)
        self.process.update_charge({
                                       'quantity_formula': '1 + ',
                                       'rsi_binding': 'some_rsi'
                                   }, charge_id=charge.id)
        with self.assertRaises(FormulaSyntaxError):
            self.process.compute_reebill(account, 1, version=1)

        # delete the new version
        self.process.delete_reebill(account, 1)
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertEquals(0, reebill_data[0]['version'])

        # try to create a new version again: it should succeed, even though
        # there was a KeyError due to a missing RSI when computing the bill
        self.process.new_version(account, 1)
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertEquals(1, reebill_data[0]['version'])

    def test_correction_issuing(self):
        """Test creating corrections on reebills, and issuing them to create
        adjustments on other reebills.
        """
        acc = '99999'
        p = self.process
        base_date = date(2012, 1, 1)

        for i in xrange(4):
            ub = p.upload_utility_bill(acc, 'gas',
                                       base_date + timedelta(days=30 * i),
                                       base_date + timedelta(
                                           days=30 * (i + 1)),
                                       StringIO('a utility bill'),
                                       'filename.pdf')

            p.add_charge(ub.id)  #creates a charge with rsi_binding 'New RSI #1'
            #update the just-created charge
            p.update_charge({'rsi_binding': 'THE_CHARGE',
                             'quantity_formula': 'REG_TOTAL.quantity',
                             'rate': 1,
                             'group': 'All Charges'}, utilbill_id=ub.id,
                            rsi_binding='New RSI #1')

            p.update_register(ub.registers[0].id, {'quantity': 100})

            p.refresh_charges(ub.id)  # creates charges
            p.compute_utility_bill(ub.id)  # updates charge values

        for seq, reg_tot, strd in [(1, 100, base_date),
                                   (2, 200, None),
                                   (3, 300, None)]:
            rb = p.roll_reebill(acc, start_date=strd)
            p.update_sequential_account_info(acc, seq, discount_rate=0.5)
            p.ree_getter = MockReeGetter(reg_tot)
            p.bind_renewable_energy(acc, seq)
            p.compute_reebill(acc, seq)
            p.issue(acc, seq)

            self.assertEqual(rb.ree_charge, reg_tot / 2.0,
                             "Reebill %s recharge should equal %s; not %s" \
                             % (seq, reg_tot / 2.0, rb.ree_charge))

        self.assertEquals([], p.get_unissued_corrections(acc),
                            "There should be no unissued corrections.")
        self.assertEquals(0, p.get_total_adjustment(acc),
                          "There should be no total adjustments.")

        p.roll_reebill(acc)  # Fourth Reebill

        # try to issue nonexistent corrections
        self.assertRaises(ValueError, p.issue_corrections, acc, 4)

        reebill_data = lambda seq: next(d for d in \
                                        p.get_reebill_metadata_json(acc)
                                        if d['sequence'] == seq)

        # Update the discount rate for reebill sequence 1
        p.new_version(acc, 1)
        p.update_sequential_account_info(acc, 1, discount_rate=0.75)
        p.ree_getter = MockReeGetter(100)
        p.bind_renewable_energy(acc, 1)
        p.compute_reebill(acc, 1, version=1)

        d = reebill_data(1)
        self.assertEqual(d['ree_charge'], 25.0,
                         "Charges for reebill seq 1 should be updated to 25")

        #Update the discount rate for reebill sequence 3
        p.new_version(acc, 3)
        p.update_sequential_account_info(acc, 3, discount_rate=0.25)
        p.ree_getter = MockReeGetter(300)
        p.bind_renewable_energy(acc, 3)
        p.compute_reebill(acc, 3)
        d = reebill_data(3)
        self.assertEqual(d['ree_charge'], 225.0,
                         "Charges for reebill seq 3 should be updated to 225")

        # there should be 2 adjustments: -25 for the first bill, and +75
        # for the 3rd
        self.assertEqual([(1, 1, -25), (3, 1, 75)],
                         p.get_unissued_corrections(acc))
        self.assertEqual(50, p.get_total_adjustment(acc))

        # try to apply corrections to an issued bill
        self.assertRaises(ValueError, p.issue_corrections, acc, 2)
        # try to apply corrections to a correction
        self.assertRaises(ValueError, p.issue_corrections, acc, 3)

        self.assertFalse(reebill_data(1)['issued'])
        self.assertFalse(reebill_data(3)['issued'])

        # get original balance of reebill 4 before applying corrections
        #four = self.state_db.get_reebill(session, acc, 4)
        p.compute_reebill(acc, 4)

        # apply corrections to un-issued reebill 4. reebill 4 should be
        # updated, and the corrections (1 & 3) should be issued
        p.issue_corrections(acc, 4)
        p.compute_reebill(acc, 4)
        # for some reason, adjustment is part of "balance forward"
        # https://www.pivotaltracker.com/story/show/32754231

        four = reebill_data(4)
        self.assertEqual(four['prior_balance'] - four['payment_received'] +
                         four['total_adjustment'], four['balance_forward'])
        self.assertEquals(four['balance_forward'] + four['ree_charge'],
                          four['balance_due'])

        self.assertTrue(reebill_data(1)['issued'])
        self.assertTrue(reebill_data(3)['issued'])

        self.assertEqual([], p.get_unissued_corrections(acc))

    def test_late_charge_correction(self):
        acc = '99999'
        # set customer late charge rate
        customer = self.state_db.get_customer(acc)
        customer.set_discountrate(.5)
        customer.set_late_charge_rate(.34)

        # first utility bill (ensure that an RSI and a charge exist,
        # and mark as "processed" so next utility bill will have them too
        u1 = self.process.upload_utility_bill(acc, 'gas',
                                              date(2012, 1, 1),
                                              date(2012, 2, 1),
                                              StringIO('January 2012'),
                                              'january.pdf')

        charge = self.process.add_charge(u1.id)
        self.process.update_charge(dict(rsi_binding='THE_CHARGE',
                                        quantity_formula="REG_TOTAL.quantity",
                                        quantity_units='therms', rate=1,
                                        group='All Charges'), charge_id=charge.id)

        self.process.update_utilbill_metadata(u1.id,
                                              processed=True)

        # 2nd utility bill
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('February 2012'),
                                         'february.pdf')

        # 1st reebill, with a balance of 100, issued 40 days ago and unpaid
        # (so it's 10 days late)
        one = self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        # TODO control amount of renewable energy given by mock_skyliner
        # so there's no need to replace that value with a known one here
        one.set_renewable_energy_reading('REG_TOTAL', 100 * 1e5)
        self.process.compute_reebill(acc, 1)
        assert one.ree_charge == 50
        assert one.balance_due == 50
        self.process.issue(acc, 1,
                           issue_date=datetime.utcnow() - timedelta(40))

        # 2nd reebill, which will get a late charge from the 1st
        two = self.process.roll_reebill(acc)

        # "bind REE" in 2nd reebill
        # (it needs energy data only so its correction will have the same
        # energy in it as the original version; only the late charge will
        # differ)
        self.process.ree_getter.update_renewable_readings(
            self.nexus_util.olap_id(acc), two)

        # if given a late_charge_rate > 0, 2nd reebill should have a late
        # charge
        two.late_charge_rate = .5
        self.process.compute_reebill(acc, 2)
        self.assertEqual(25, two.late_charge)

        # issue 2nd reebill so a new version of it can be created
        self.process.issue(acc, 2)

        # add a payment of $30 30 days ago (10 days after 1st reebill was
        # issued). the late fee above is now wrong; it should be 50% of
        # the unpaid $20 instead of 50% of the entire $50.
        self.process.create_payment(acc, datetime.utcnow() - timedelta(30),
                                    'backdated payment', 30)

        # now a new version of the 2nd reebill should have a different late
        # charge: $10 instead of $50.
        self.process.new_version(acc, 2)
        two_1 = self.state_db.get_reebill(acc, 2, version=1)
        assert two_1.late_charge_rate == .5
        self.process.compute_reebill(acc, 2, version=1)
        self.assertEqual(10, two_1.late_charge)

        # that difference should show up as an error
        corrections = self.process.get_unissued_corrections(acc)
        assert len(corrections) == 1
        # self.assertEquals((2, 1, 25 - 15), corrections[0])
        # for some reason there's a tiny floating-point error in the
        # correction amount so it must be compared with assertAlmostEqual
        # (which doesn't work on tuples)
        sequence, version, amount = corrections[0]
        self.assertEqual(2, sequence)
        self.assertEqual(1, version)
        self.assertAlmostEqual(-15, amount)

    # TODO rename
    def test_roll(self):
        '''Tests creation of reebills and dependency of each reebill on its
        predecessor.'''
        account = '99999'
        self.process.ree_getter = MockReeGetter(100)

        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 4, 4), date(2013, 5, 2), StringIO('April 2013'),
                                         'april.pdf')
        # add a register to the first utility bill so there are 2,
        # REG_TOTAL and OTHER
        id_1 = self.process.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']
        register = self.process.new_register(id_1, {'meter_id': 'M60324',
                                                    'register_id': 'R'})
        self.process.update_register(register.id, {'register_binding': 'OTHER'})

        # 2nd utility bill should have the same registers as the first
        utilbill = self.process.upload_utility_bill(account, 'gas',
                                                    date(2013, 5, 2), date(2013, 6, 3), StringIO('May 2013'),
                                                    'may.pdf')

        # create reebill based on first utility bill
        reebill1 = self.process.roll_reebill(account,
                                             start_date=date(2013, 4, 4))

        self.process.compute_reebill(account, 1)
        self.process.issue(account, 1,
                           issue_date=datetime(2013, 5, 1))
        # delete register from the 2nd utility bill
        id_2 = self.process.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']

        register = filter(lambda x: x.identifier == 'R' and
                                    x.meter_identifier == 'M60324',
                          utilbill.registers)[0]
        self.process.delete_register(register.id)

        # 2nd reebill should NOT have a reading corresponding to the
        # additional register, which was removed
        reebill2 = self.process.roll_reebill(account)
        utilbill_data, count = self.process.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(2, count)
        self.assertEqual(reebill1.readings[0].measure, reebill2.readings[0].measure)
        self.assertEqual(reebill1.readings[0].aggregate_function,
                         reebill2.readings[0].aggregate_function)
        self.assertDictContainsSubset({
                                          'sequence': 1,
                                          'version': 0,
                                          'issue_date': datetime(2013, 5, 1),
                                          }, utilbill_data[1]['reebills'][0])
        self.assertDictContainsSubset({
                                          'sequence': 2,
                                          'version': 0,
                                          'issue_date': None,
                                          }, utilbill_data[0]['reebills'][0])

        # the 1st reebill has a reading for both the "REG_TOTAL" register
        # and the "OTHER" register, for a total of 200 therms of renewable
        # energy. since the 2nd utility bill no longer has the "OTHER" register,
        # the 2nd reebill does not have a reading fot it, even though the 1st
        # reebill has it.
        reebill_2_data, reebill_1_data = self.process \
            .get_reebill_metadata_json(account)
        self.assertEqual(200, reebill_1_data['ree_quantity'])
        self.assertEqual(100, reebill_2_data['ree_quantity'])

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
        account_info = self.process.get_sequential_account_info(account, 1)
        self.assertDictContainsSubset(billing_address,
                                      account_info['billing_address'])
        self.assertDictContainsSubset(service_address,
                                      account_info['service_address'])
        self.assertEqual(account_info['discount_rate'], 0.12)
        self.assertEqual(account_info['late_charge_rate'], 0.34)

        # add two more utility bills: UtilityEstimated and Complete
        self.process.upload_utility_bill(account, 'gas', date(2013, 7, 1),
                date(2013, 7, 30), StringIO('July 2013'), 'july.pdf')
        utilbill_data, count = self.process.get_all_utilbills_json(account,
                0, 30)
        self.assertEqual(3, count)
        self.assertEqual(['Final', 'Final', 'Final'],
                         [u['state'] for u in utilbill_data])

        self.process.upload_utility_bill(account, 'gas', date(2013, 6, 3),
                date(2013, 7, 1), StringIO('June 2013'), 'june.pdf',
                state=UtilBill.UtilityEstimated)
        utilbill_data, count = self.process.get_all_utilbills_json(account,
                0, 30)
        self.assertEqual(4, count)
        self.assertEqual(['Final', 'Utility Estimated', 'Final', 'Final'],
                         [u['state'] for u in utilbill_data])
        last_utilbill_id, formerly_hyp_utilbill_id = (u['id'] for u in
                                                      utilbill_data[:2])

        self.process.roll_reebill(account)

        # if a utiltity bill has an error in its charges, an exception should
        # be raised when computing the reebill, but Process.roll_reebill ignores
        # it and catches it
        last_utilbill_id = utilbill_data[0]['id']
        charge = self.process.add_charge(last_utilbill_id)
        charge.quantity_formula = '1 +'
        self.process.roll_reebill(account)
        self.process.compute_reebill(account, 2)

        self.process.issue(account, 2)

        # Shift later_utilbill a few days into the future so that there is
        # a time gap after the last attached utilbill
        self.process.update_utilbill_metadata(
            formerly_hyp_utilbill_id, period_start=date(2013, 6, 8))
        self.process.update_utilbill_metadata(last_utilbill_id,
                                              period_end=date(2013, 7, 6))

        # can't create another reebill because there are no more utility
        # bills
        with self.assertRaises(NoSuchBillException) as context:
            self.process.roll_reebill(account)

    def test_list_all_versions(self):
        account = '99999'
        utilbill = self.process.upload_utility_bill(
            account, 'gas', date(2013, 5, 2), date(2013, 6, 3),
            StringIO('May 2013'), 'may.pdf')
        reebill = self.process.roll_reebill(
            account, start_date=date(2013, 4, 4))
        self.process.compute_reebill(account, 1)
        self.process.issue(account, 1, issue_date=datetime(2013, 5, 1))
        self.process.new_version(account, 1)
        reebill_data = self.process.list_all_versions(account, 1)
        dicts = [{
            'sequence': 1,
            'version': 1,
            'issued': 0,
            'issue_date': None,
            'payment_received': 0.,
            'period_start': date(2013, 5, 2),
            'period_end': date(2013, 6, 3),
            'prior_balance': 0.,
            'processed': False,
            'balance_forward': 0.,
            'corrections': '#1 not issued'
        }, {
            'sequence': 1,
            'version': 0,
            'issued': 1,
            'issue_date': datetime(2013, 5, 1),
            'payment_received': 0.,
            'period_start': date(2013, 5, 2),
            'period_end': date(2013, 6, 3),
            'prior_balance': 0.,
            'processed': 1,
            'balance_forward': 0.,
            'corrections': '-'
        }]

        for i, reebill_dct in enumerate(reebill_data):
            self.assertDictContainsSubset(dicts[i], reebill_dct)


    def test_compute_reebill(self):
        '''Basic test of reebill processing with an emphasis on making sure
            the accounting numbers in reebills are correct.
            '''
        account = '99999'
        energy_quantity = 100.0
        payment_amount = 100.0
        self.process.ree_getter = MockReeGetter(energy_quantity)

        # create 2 utility bills with 1 charge in them
        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 1, 1), date(2013, 2, 1),
                                         StringIO('January 2013'),
                                         'january.pdf')
        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 2, 1), date(2013, 3, 1),
                                         StringIO('February 2013'),
                                         'february.pdf')
        utilbills_data, _ = self.process.get_all_utilbills_json(account, 0, 30)
        id_2, id_1 = (obj['id'] for obj in utilbills_data)
        self.process.add_charge(id_1)
        self.process.update_charge({'rsi_binding': 'THE_CHARGE',
                                    'quantity_formula': 'REG_TOTAL.quantity',
                                    'rate': 1},
                                   utilbill_id=id_1,
                                   rsi_binding='New RSI #1')
        self.process.refresh_charges(id_1)
        self.process.update_utilbill_metadata(id_1, processed=True)
        self.process.regenerate_uprs(id_2)
        self.process.refresh_charges(id_2)
        self.process.update_utilbill_metadata(id_2, processed=True)

        # create, process, and issue reebill
        self.process.roll_reebill(account, start_date=date(2013, 1, 1))
        self.process.update_sequential_account_info(account, 1,
                                                    discount_rate=0.5)

        # get renewable energy and compute the reebill. make sure this is
        # idempotent because in the past there was a bug where it was not.
        for i in range(2):
            self.process.bind_renewable_energy(account, 1)
            self.process.compute_reebill(account, 1)
            reebill_data = self.process.get_reebill_metadata_json(account)
            self.assertDictContainsSubset({
                                              'sequence': 1,
                                              'version': 0,
                                              'issued': 0,
                                              'issue_date': None,
                                              'actual_total': 0.,
                                              'hypothetical_total': energy_quantity,
                                              'payment_received': 0.,
                                              'period_start': date(2013, 1, 1),
                                              'period_end': date(2013, 2, 1),
                                              'prior_balance': 0.,
                                              'processed': False,
                                              'ree_charge': energy_quantity * .5,
                                              'ree_value': energy_quantity,
                                              'services': [],
                                              'total_adjustment': 0.,
                                              'total_error': 0.,
                                              'ree_quantity': energy_quantity,
                                              'balance_due': energy_quantity * .5,
                                              'balance_forward': 0.,
                                              'corrections': '(never issued)'}, reebill_data[0])

        self.process.issue(account, 1, issue_date=datetime(2013, 2, 15))
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertDictContainsSubset({
                                          'sequence': 1,
                                          'version': 0,
                                          'issued': 1,
                                          'issue_date': datetime(2013, 2, 15),
                                          'actual_total': 0.,
                                          'hypothetical_total': energy_quantity,
                                          'payment_received': 0.,
                                          'period_start': date(2013, 1, 1),
                                          'period_end': date(2013, 2, 1),
                                          'prior_balance': 0.,
                                          'processed': 1,
                                          'ree_charge': energy_quantity * .5,
                                          'ree_value': energy_quantity,
                                          'services': [],
                                          'total_adjustment': 0.,
                                          'total_error': 0.,
                                          'ree_quantity': energy_quantity,
                                          'balance_due': energy_quantity * .5,
                                          'balance_forward': 0.0,
                                          'corrections': '-',
                                          }, reebill_data[0])

        # add a payment so payment_received is not 0
        self.process.create_payment(account, date(2013, 2, 17),
                                    'a payment for the first reebill', payment_amount)

        # 2nd reebill
        self.process.roll_reebill(account)
        self.process.update_sequential_account_info(account, 2,
                                                    discount_rate=0.2)
        self.process.compute_reebill(account, 2)
        reebill_data = self.process.get_reebill_metadata_json(account)
        dictionaries = [{
                            'sequence': 2,
                            'version': 0L,
                            'issued': 0,
                            'issue_date': None,
                            'actual_total': 0,
                            'hypothetical_total': energy_quantity,
                            'payment_received': payment_amount,
                            'period_start': date(2013, 2, 1),
                            'period_end': date(2013, 3, 1),
                            'prior_balance': energy_quantity * .5,
                            'processed': 0,
                            'ree_charge': energy_quantity * .8,
                            'ree_value': energy_quantity,
                            'services': [],
                            'total_adjustment': 0,
                            'total_error': 0.0,
                            'ree_quantity': energy_quantity,
                            'balance_due': energy_quantity * .5 +
                                           energy_quantity * .8 - payment_amount,
                            'balance_forward': energy_quantity * .5 -
                                               payment_amount,
                            'corrections': '(never issued)',
                            }, {
                            'sequence': 1L,
                            'version': 0L,
                            'issued': 1,
                            'issue_date': datetime(2013, 2, 15),
                            'actual_total': 0,
                            'hypothetical_total': energy_quantity,
                            'payment_received': 0.0,
                            'period_start': date(2013, 1, 1),
                            'period_end': date(2013, 2, 1),
                            'prior_balance': 0,
                            'processed': 1,
                            'ree_charge': energy_quantity * .5,
                            'ree_value': energy_quantity,
                            'services': [],
                            'total_adjustment': 0,
                            'total_error': 0.0,
                            'ree_quantity': energy_quantity,
                            'balance_due': energy_quantity * .5,
                            'balance_forward': 0.0,
                            'corrections': '-',
                            }]

        for i, reebill_dct in enumerate(reebill_data):
            self.assertDictContainsSubset(dictionaries[i], reebill_dct)

        # make a correction on reebill #1: payment does not get applied to
        # #1, and does get applied to #2
        # NOTE because #1-1 is unissued, its utility bill document should
        # be "current", not frozen
        self.process.new_version(account, 1)
        self.process.compute_reebill(account, 1)
        self.process.compute_reebill(account, 2)
        reebill_data = self.process.get_reebill_metadata_json(account)
        dictionaries = [{
                            'sequence': 2,
                            'version': 0,
                            'issued': 0,
                            'issue_date': None,
                            'actual_total': 0,
                            'hypothetical_total': energy_quantity,
                            'payment_received': payment_amount,
                            'period_start': date(2013, 2, 1),
                            'period_end': date(2013, 3, 1),
                            'prior_balance': energy_quantity * .5,
                            'processed': 0,
                            'ree_charge': energy_quantity * .8,
                            'ree_value': energy_quantity,
                            'services': [],
                            'total_adjustment': 0,
                            'total_error': 0,
                            'ree_quantity': energy_quantity,
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
                            'period_start': date(2013, 1, 1),
                            'period_end': date(2013, 2, 1),
                            'prior_balance': 0,
                            'processed': 0,
                            'ree_charge': energy_quantity * .5,
                            'ree_value': energy_quantity,
                            'services': [],
                            'total_adjustment': 0,
                            'total_error': 0,
                            'ree_quantity': energy_quantity,
                            'balance_due': energy_quantity * .5,
                            'balance_forward': 0,
                            'corrections': '#1 not issued',
                            }]

        for i, reebill_dct in enumerate(reebill_data):
            self.assertDictContainsSubset(dictionaries[i], reebill_dct)

    def test_payment_application(self):
        """Test that payments are applied to reebills according their "date
            received", including when multiple payments are applied and multiple
            bills are issued in the same day.
            """
        account = '99999'
        self.process.upload_utility_bill(account, 'gas', date(2000, 1, 1),
                                         date(2000, 2, 1), StringIO('January'), 'january.pdf')
        self.process.upload_utility_bill(account, 'gas', date(2000, 2, 1),
                                         date(2000, 3, 1), StringIO('February'), 'March.pdf')
        self.process.upload_utility_bill(account, 'gas', date(2000, 3, 1),
                                         date(2000, 4, 1), StringIO('March'), 'March.pdf')

        # create 2 reebills
        reebill_1 = self.process.roll_reebill(account,
                                              start_date=date(2000, 1, 1))
        reebill_2 = self.process.roll_reebill(account)

        # 1 payment applied today at 1:00, 1 payment applied at 2:00
        self.process.create_payment(account, datetime(2000, 1, 1, 1), 'one', 10)
        self.process.create_payment(account, datetime(2000, 1, 1, 2), 'two', 12)

        # 1st reebill has both payments applied to it, 2nd has neither
        self.process.compute_reebill(account, 1)
        self.process.compute_reebill(account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(0, reebill_2.payment_received)

        # issue the 1st bill
        self.process.issue(account, 1, issue_date=datetime(2000, 1, 1, 3))
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(0, reebill_2.payment_received)
        self.process.compute_reebill(account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(0, reebill_2.payment_received)

        # now later payments apply to the 2nd bill
        self.process.create_payment(account, datetime(2000, 1, 1, 3), 'three', 30)
        self.process.compute_reebill(account, 2)
        self.assertEqual(30, reebill_2.payment_received)

        # even when a correction is made on the 1st bill
        self.process.new_version(account, 1)
        self.process.compute_reebill(account, 1)
        self.process.compute_reebill(account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(30, reebill_2.payment_received)

        # a payment that is backdated to before a corrected bill was issued
        # does not appear on the corrected version
        self.process.create_payment(account, datetime(2000, 1, 1, 2, 30),
                                    'backdated payment', 230)
        self.process.compute_reebill(account, 1)
        self.process.compute_reebill(account, 2)
        self.assertEqual(22, reebill_1.payment_received)
        self.assertEqual(30, reebill_2.payment_received)

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

        self.process.ree_getter.get_billable_energy_timeseries = \
            get_mock_energy_consumption

        self.process.upload_utility_bill(account, 'gas', date(2000, 1, 1),
                                         date(2000, 2, 1), StringIO('January'), 'january.pdf')

        # modify registers of this utility bill so they are TOU
        u = self.session.query(UtilBill).join(Customer). \
            filter_by(account='99999').one()
        active_periods_str = json.dumps({
            'active_periods_weekday': [[9, 9]],
            'active_periods_weekend': [[11, 11]],
            'active_periods_holiday': [[13, 13]]
        })
        self.session.add(Register(u, 'time-of-use register', 0, 'btu',
                                  'test2', False, 'tou', 'TOU', active_periods_str, ''))
        self.process.roll_reebill(account, start_date=date(2000, 1, 1))

        # the total energy consumed over the 3 non-0 days is
        # 3 * (0 + 2 + ... + 23) = 23 * 24 / 2 = 276.
        # when only the hours 9, 11, and 13 are included, the total is just
        # 9 + 11 + 13 = 33.
        total_renewable_btu = 23 * 24 / 2. * 3
        total_renewable_therms = total_renewable_btu / 1e5
        tou_renewable_btu = 9 + 11 + 13

        # check reading of the reebill corresponding to the utility register
        total_reading, tou_reading = self.session.query(ReeBill).one().readings
        self.assertEqual('therms', total_reading.unit)
        self.assertEqual(total_renewable_therms,
                         total_reading.renewable_quantity)
        self.assertEqual('btu', tou_reading.unit)
        self.assertEqual(tou_renewable_btu, tou_reading.renewable_quantity)

    def test_update_readings(self):
        '''Simple test to get coverage on Process.update_reebill_readings.
        This can be expanded or merged into another test method later on.
        '''
        account = '99999'
        self.process.upload_utility_bill(account, 'gas', date(2000, 1, 1),
                                         date(2000, 2, 1), StringIO('January'),
                                         'january.pdf')
        self.process.roll_reebill(account, start_date=date(2000, 1, 1))
        self.process.update_reebill_readings(account, 1)
        self.process.update_sequential_account_info(account, 1, processed=True)
        with self.assertRaises(ProcessedBillError):
            self.process.update_reebill_readings(account, 1)
        self.process.issue(account, 1)
        with self.assertRaises(IssuedBillError):
            self.process.update_reebill_readings(account, 1)


    def test_compute_realistic_charges(self):
        '''Tests computing utility bill charges and reebill charge for a
        reebill based on the utility bill, using a set of charge from an actual
        bill.
        '''
        account = '99999'
        # create utility bill and reebill
        self.process.upload_utility_bill(account, 'gas', date(2012, 1, 1),
                                         date(2012, 2, 1), StringIO('January 2012'), 'january.pdf')
        utilbill_id = self.process.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']

        example_charge_fields = [
            dict(rate=23.14,
                 rsi_binding='PUC',
                 description='Peak Usage Charge',
                 quantity_formula='1'),
            dict(rate=0.03059,
                 rsi_binding='RIGHT_OF_WAY',
                 roundrule='ROUND_HALF_EVEN',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=0.01399,
                 rsi_binding='SETF',
                 roundrule='ROUND_UP',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rsi_binding='SYSTEM_CHARGE',
                 rate=11.2,
                 quantity_formula='1'),
            dict(rsi_binding='DELIVERY_TAX',
                 rate=0.07777,
                 quantity_units='therms',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=.2935,
                 rsi_binding='DISTRIBUTION_CHARGE',
                 roundrule='ROUND_UP',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=.7653,
                 rsi_binding='PGC',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=0.006,
                 rsi_binding='EATF',
                 quantity_formula='REG_TOTAL.quantity'),
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
            self.process.add_charge(utilbill_id)
            self.process.update_charge(fields, utilbill_id=utilbill_id,
                                       rsi_binding="New RSI #1")
        self.process.refresh_charges(utilbill_id)

        # ##############################################################
        # check that each actual (utility) charge was computed correctly:
        quantity = self.process.get_registers_json(
            utilbill_id)[0]['quantity']
        actual_charges = self.process.get_utilbill_charges_json(utilbill_id)

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
        self.assertEqual(0.06 * sum(map(get_total, non_tax_rsi_bindings)),
                         get_total('SALES_TAX'))

        # ##############################################################
        # check that each hypothetical charge was computed correctly:
        self.process.roll_reebill(account, start_date=date(2012, 1, 1))
        reebill = self.process.compute_reebill(account, 1)
        reebill_charges = \
            self.process.get_hypothetical_matched_charges(reebill.id)

        def get_h_total(rsi_binding):
            charge = next(c for c in reebill_charges
                          if c['rsi_binding'] == rsi_binding)
            return charge['total']

        h_quantity = self.process.get_reebill_metadata_json(
            account)[0]['ree_quantity']
        self.assertEqual(11.2, get_h_total('SYSTEM_CHARGE'))
        self.assertEqual(0.03059 * h_quantity, get_h_total('RIGHT_OF_WAY'))
        self.assertEqual(0.01399 * h_quantity, get_h_total('SETF'))
        self.assertEqual(0.006 * h_quantity, get_h_total('EATF'))
        self.assertEqual(0.07777 * h_quantity, get_h_total('DELIVERY_TAX'))
        self.assertEqual(23.14, get_h_total('PUC'))
        self.assertEqual(.2935 * h_quantity,
                         get_h_total('DISTRIBUTION_CHARGE'))
        self.assertEqual(.7653 * h_quantity, get_h_total('PGC'))
        self.assertEqual(0.06 * sum(map(get_h_total, non_tax_rsi_bindings)),
                         get_h_total('SALES_TAX'))

    def test_delete_utility_bill_with_reebill(self):
        account = '99999'
        start, end = date(2012, 1, 1), date(2012, 2, 1)
        # create utility bill in MySQL, Mongo, and filesystem (and make
        # sure it exists all 3 places)
        self.process.upload_utility_bill(account, 'gas', start, end,
                                         StringIO("test"), 'january.pdf')
        utilbills_data, count = self.process.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(1, count)

        # when utilbill is attached to reebill, deletion should fail
        self.process.roll_reebill(account, start_date=start)
        reebills_data = self.process.get_reebill_metadata_json(account)
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
                                          'period_end': date(2012, 2, 1),
                                          'period_start': date(2012, 1, 1),
                                          'prior_balance': 0,
                                          'processed': 0,
                                          'ree_charge': 0.0,
                                          'ree_quantity': 22.602462036826545,
                                          'ree_value': 0,
                                          'sequence': 1,
                                          'services': [],
                                          'total_adjustment': 0,
                                          'total_error': 0.0
                                      }, reebills_data[0])
        self.assertRaises(ValueError,
                          self.process.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

        # deletion should fail if any version of a reebill has an
        # association with the utility bill. so issue the reebill, add
        # another utility bill, and create a new version of the reebill
        # attached to that utility bill instead.
        self.process.issue(account, 1)
        self.process.new_version(account, 1)
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO("test"),
                                         'january-electric.pdf')
        # TODO this may not accurately reflect the way reebills get
        # attached to different utility bills; see
        # https://www.pivotaltracker.com/story/show/51935657
        self.assertRaises(ValueError,
                          self.process.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])
if __name__ == '__main__':
    unittest.main()