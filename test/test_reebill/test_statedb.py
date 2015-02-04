'''Tests for ReeBill-specific data-access objects, including the database.
Currently the only one is StateDB.
'''
from reebill.payment_dao import PaymentDAO
from reebill.reebill_dao import ReeBillDAO
from test.setup_teardown import init_logging, TestCaseWithSetup
from core.model.model import Utility, Supplier, RateClass, UtilityAccount
from reebill.state import ReeBillCustomer

init_logging()
import unittest
from datetime import date, datetime
from sqlalchemy.orm.exc import NoResultFound
from core import init_config, init_model
from reebill import state
from core.model import UtilBill, Session, Address
from reebill.state import ReeBill

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}

class StateDBTest(TestCaseWithSetup):

    def setUp(self):
        # clear out database
        init_config('test/tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables()
        blank_address = Address()
        test_utility = Utility('FB Test Utility Name', blank_address)
        test_supplier = Supplier('FB Test Suplier', blank_address)
        self.utility_account = UtilityAccount('someaccount', 99999,
                            test_utility, test_supplier,
                            RateClass('FB Test Rate Class', test_utility),
                            blank_address, blank_address)
        self.reebill_customer = ReeBillCustomer('Test Customer',  .12, .34,
                            'thermal', 'example@example.com',
                            self.utility_account)
        self.session.add(self.utility_account)
        self.session.add(self.reebill_customer)
        self.session.commit()
        self.state_db = ReeBillDAO()
        self.payment_dao = PaymentDAO()

    def tearDown(self):
        self.session.rollback()
        self.truncate_tables()

    def test_versions(self):
        '''Tests max_version(), max_issued_version(), increment_version(), and
        the behavior of is_issued() with multiple versions.'''
        session = Session()
        acc, seq = '99999', 1
        # initially max_version is 0, max_issued_version is None, and issued
        # is false
        b = ReeBill(self.reebill_customer, seq)
        session.add(b)
        self.assertEqual(0, self.state_db.max_version(acc, seq))
        self.assertEqual(None, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # adding versions of bills for other accounts should have no effect
        fb_test_utility = Utility('FB Test Utility', Address())
        fb_test_supplier = Supplier('FB Test Supplier', Address())
        rate_class = session.query(RateClass).one()
        utility_account1 = UtilityAccount('some_account', '11111',
                fb_test_utility, fb_test_supplier, rate_class,
                Address(), Address())
        utility_account2 = UtilityAccount('another_account', '22222',
                fb_test_utility, fb_test_supplier, rate_class,
                Address(), Address())
        self.session.add(utility_account1)
        self.session.add(ReeBillCustomer('someone', 0.5, 0.1,
                'thermal', 'customer1@example.com', utility_account1))
        self.session.add(ReeBillCustomer('someone', 0.5, 0.1,
                'thermal', 'customer2@example.com', utility_account2))
        session.add(ReeBill(self.state_db.get_reebill_customer('11111'), 1))
        session.add(ReeBill(self.state_db.get_reebill_customer('11111'), 2))
        session.add(ReeBill(self.state_db.get_reebill_customer('22222'), 1))
        self.state_db.issue('11111', 1)
        self.state_db.issue('22222', 1)
        self.state_db.increment_version('11111', 1)
        self.state_db.increment_version('22222', 1)
        self.state_db.issue('22222', 1)
        self.state_db.increment_version('22222', 1)
        self.assertEqual(0, self.state_db.max_version(acc, seq))
        self.assertEqual(None, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq, version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # incrementing version to 1 should fail when the bill is not issued
        self.assertRaises(Exception, self.state_db.increment_version,
                acc, seq)
        self.assertEqual(0, self.state_db.max_version(acc, seq))
        self.assertEqual(None, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # issue & increment version to 1
        self.state_db.issue(acc, seq)
        self.assertEqual(True, self.state_db.is_issued(acc, seq)) # default version for is_issued is highest, i.e. 1
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=0))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=1)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)
        self.state_db.increment_version(acc, seq)
        self.assertEqual(1, self.state_db.max_version(acc, seq))
        self.assertEqual(0, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=0))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=1))
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)

        # issue version 1 & create version 2
        self.state_db.issue(acc, seq)
        self.assertEqual(1, self.state_db.max_issued_version(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq,
                version=0))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=1))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=2)
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)
        self.state_db.increment_version(acc, seq)
        self.assertEqual(False, self.state_db.is_issued(acc, seq))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=0))
        self.assertEqual(True, self.state_db.is_issued(acc, seq, version=1))
        self.assertEqual(False, self.state_db.is_issued(acc, seq,
                version=2))
        self.assertRaises(NoResultFound, self.state_db.is_issued,
                acc, seq, version=10)
        self.assertEqual(2, self.state_db.max_version(acc, seq))
        self.assertEqual(1, self.state_db.max_issued_version(acc, seq))

        # issue version 2
        self.state_db.issue(acc, seq)
        self.assertEqual(2, self.state_db.max_issued_version(acc, seq))


    def test_get_unissued_corrections(self):
        session = Session()
        # reebills 1-4, 1-3 issued
        session.add(ReeBill(self.reebill_customer, 1))
        session.add(ReeBill(self.reebill_customer, 2))
        session.add(ReeBill(self.reebill_customer, 3))
        self.state_db.issue('99999', 1)
        self.state_db.issue('99999', 2)
        self.state_db.issue('99999', 3)

        # no unissued corrections yet
        self.assertEquals([],
                self.state_db.get_unissued_corrections('99999'))

        # make corrections on 1 and 3
        self.state_db.increment_version('99999', 1)
        self.state_db.increment_version('99999', 3)
        self.assertEquals([(1, 1), (3, 1)],
                self.state_db.get_unissued_corrections('99999'))

        # issue 3
        self.state_db.issue('99999', 3)
        self.assertEquals([(1, 1)],
                self.state_db.get_unissued_corrections('99999'))

        # issue 1
        self.state_db.issue('99999', 1)
        self.assertEquals([],
                self.state_db.get_unissued_corrections('99999'))

    def test_get_all_reebills_for_account(self):
        session = Session()

        reebills = [
            ReeBill(self.reebill_customer, 1),
            ReeBill(self.reebill_customer, 2),
            ReeBill(self.reebill_customer, 3)
        ]

        for rb in reebills:
            session.add(rb)

        account = self.reebill_customer.get_account()
        bills = self.state_db.get_all_reebills_for_account(account)
        self.assertEqual(bills, reebills)

    def test_payments(self):
        acc = '99999'
        # one payment on jan 15
        self.payment_dao.create_payment(acc, date(2012,1,15), 'payment 1', 100)
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2011,12,1), date(2012,1,14)))
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2012,1,16), date(2012,2,1)))
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2012,2,1), date(2012,1,1)))
        payments = self.payment_dao.find_payment(acc, date(2012,1,1),
                date(2012,2,1))
        p = payments[0]
        self.assertEqual(1, len(payments))
        self.assertEqual((acc, datetime(2012,1,15), 'payment 1', 100),
                (p.reebill_customer.get_account(), p.date_applied, p.description,
                p.credit))
        self.assertDatetimesClose(datetime.utcnow(), p.date_received)
        # should be editable since it was created today
        #self.assertEqual(True, p.to_dict()['editable'])

        # another payment on feb 1
        self.payment_dao.create_payment(acc, date(2012, 2, 1),
                'payment 2', 150)
        self.assertEqual([p], self.payment_dao.find_payment(acc,
                date(2012,1,1), date(2012,1,31)))
        self.assertEqual([], self.payment_dao.find_payment(acc,
                date(2012,2,2), date(2012,3,1)))
        payments = self.payment_dao.find_payment(acc, date(2012,1,16),
                date(2012,3,1))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,2,1), 'payment 2', 150),
                (q.reebill_customer.get_account(), q.date_applied, q.description,
                q.credit))
        self.assertEqual(sorted([p, q]),
                         sorted(self.payment_dao.get_payments(acc)))

        # update feb 1: move it to mar 1
        q.date_applied = datetime(2012,3,1)
        q.description = 'new description'
        q.credit = 200
        payments = self.payment_dao.find_payment(acc, datetime(2012,1,16),
                datetime(2012,3,2))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,3,1), 'new description', 200),
                (q.reebill_customer.get_account(), q.date_applied, q.description,
                q.credit))

        # delete jan 15
        self.payment_dao.delete_payment(p.id)
        self.assertEqual([q], self.payment_dao.find_payment(acc,
                datetime(2012,1,1), datetime(2012,4,1)))


    def test_get_accounts_grid_data(self):
        empty_address = Address()
        fake_address = Address('Addressee', 'Street', 'City', 'ST', '12345')
        # Create 2 customers
        utility_account1 = self.session.query(UtilityAccount).one()
        reebill_customer1 = self.session.query(ReeBillCustomer).one()
        rateclass1 = Session().query(RateClass).filter_by(
            name='FB Test Rate Class').one()
        utility_account2 = UtilityAccount('other_account', 99998,
                            utility_account1.fb_utility,
                            utility_account1.fb_supplier, rateclass1,
                            empty_address, empty_address)
        self.session.add(utility_account2)
        reebill_customer2 = ReeBillCustomer('Test Customer', .12, .34,
                            'thermal', 'example@example.com',
                            utility_account2)
        self.session.add(reebill_customer2)
        self.session.commit()

        utility_account_8 = Session().query(UtilityAccount).filter_by(
            account='99998').one()
        utility_account_9 = Session().query(UtilityAccount).filter_by(
            account='99999').one()
        self.assertEqual(
            self.state_db.get_accounts_grid_data(),
            [(utility_account_9.id, '99999', '', 'FB Test Utility Name',
             rateclass1.name, None,
              None, None, None, None, None, None),
             (utility_account_8.id, '99998', '', 'FB Test Utility Name',
              rateclass1.name, None,
              None, None, None, None, None, None)])
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [(utility_account_8.id, '99998', '', 'FB Test Utility Name',
              rateclass1.name, None,
              None, None, None, None, None, None)])

        # Attach two utilitybills with out addresses but with rate class to one
        # of the customers, and one utilbill with empty rateclass but with
        # address to the other customer
        washgas = Utility('washgas', Address())
        supplier = Supplier('supplier', Address())
        rateclass2 = RateClass('DC Non Residential Non Heat', washgas)
        rateclass3 = RateClass('', washgas)
        gas_bill_1 = UtilBill(utility_account1, 0, 'gas', washgas, supplier,
                rateclass2, empty_address, empty_address,
                period_start=date(2000, 1, 1), period_end=date(2000, 2, 1),
                processed=True)
        gas_bill_2 = UtilBill(utility_account2, 0, 'gas', washgas, supplier,
                rateclass2, empty_address, empty_address,
                period_start=date(2000, 3, 1), period_end=date(2000, 4, 1))
        gas_bill_3 = UtilBill(utility_account2, 0, 'gas', washgas, supplier,
                rateclass3, fake_address, fake_address,
                period_start=date(2000, 4, 1), period_end=date(2000, 5, 1),
                processed=True)
        self.session.add(gas_bill_1)
        self.session.add(gas_bill_2)
        self.session.add(gas_bill_3)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(),[
                (utility_account_9.id, '99999', '', 'FB Test Utility Name',
                 rateclass1.name,
                 False, None, None, None, rateclass2.name,
                 empty_address, date(2000, 2, 1)),
                (utility_account_8.id, '99998', '', 'FB Test Utility Name',
                 rateclass1.name,
                 False, None, None, None, rateclass3.name,
                 fake_address, date(2000, 5, 1))])
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [(utility_account_8.id, '99998', '', 'FB Test Utility Name',
              rateclass1.name, False,
              None, None, None, '', fake_address, date(2000, 5, 1))]
        )

        # Now Attach a reebill to one and issue it , and a utilbill with a
        # different rateclass to the other
        reebill = ReeBill(reebill_customer1, 1, 0, utilbills=[gas_bill_1])
        newrateclass = RateClass('New Rateclass', washgas)
        gas_bill_4 = UtilBill(utility_account2, 0, 'gas', washgas, supplier,
                newrateclass, fake_address, fake_address,
                period_start=date(2000, 5, 1), period_end=date(2000, 6, 1),
                processed=True)
        issue_date = datetime(2014, 8, 9, 21, 6, 6)

        self.session.add(gas_bill_4)
        self.session.add(reebill)
        self.state_db.issue('99999', 1, issue_date)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(), [
                (utility_account_9.id, '99999', '', 'FB Test Utility Name',
                 rateclass1.name,
                 False, 1L, 0L, issue_date, rateclass2.name,
                 empty_address, date(2000, 2, 1)),
                (utility_account_8.id, '99998', '', 'FB Test Utility Name',
                 rateclass1.name,
                 False, None, None, None, newrateclass.name, fake_address,
                 date(2000, 6, 1))]
        )
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [(utility_account_8.id, '99998', '', 'FB Test Utility Name',
              rateclass1.name, False,
              None, None, None, newrateclass.name, fake_address,
              date(2000, 6, 1))]
        )

        # Create another reebill, but don't issue it. The data should not change
        reebill_2 = ReeBill(reebill_customer1, 2, 0, utilbills=[gas_bill_2])
        self.session.add(reebill_2)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(), [
                (utility_account_9.id, '99999', '', 'FB Test Utility Name',
                 rateclass1.name,
                 False, 1L, 0L, issue_date, rateclass2.name,
                    empty_address, date(2000, 2, 1)),
                (utility_account_8.id, '99998', '', 'FB Test Utility Name',
                 rateclass1.name,
                 False, None, None, None, newrateclass.name, fake_address,
                 date(2000, 6, 1))]
        )
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [(utility_account_8.id, '99998', '', 'FB Test Utility Name',
              rateclass1.name, False,
              None, None, None, newrateclass.name, fake_address,
              date(2000, 6, 1))]
        )

if __name__ == '__main__':
    unittest.main()
