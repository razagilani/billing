from billing.test.setup_teardown import init_logging, TestCaseWithSetup
init_logging()




import unittest
from datetime import date, datetime
from sqlalchemy.orm.exc import NoResultFound
from billing import init_config, init_model
from billing.processing import state
from billing.processing.state import Customer, UtilBill, ReeBill, Session, \
    Address

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}

class StateTest(TestCaseWithSetup):
    '''Tests for ReeBill-specific data-access objects, including the database.
    '''

    def setUp(self):
        # clear out database
        init_config('test/tstsettings.cfg')
        init_model()
        self.session = Session()
        TestCaseWithSetup.truncate_tables(self.session)
        blank_address = Address()
        self.customer = Customer('Test Customer', 99999, .12, .34,
                            'example@example.com', 'FB Test Utility Name',
                            'FB Test Rate Class', blank_address, blank_address)
        self.session.add(self.customer)
        self.session.commit()
        self.state_db = state.StateDB()

    def tearDown(self):
        self.session.rollback()
        self.truncate_tables(self.session)

    def test_versions(self):
        '''Tests max_version(), max_issued_version(), increment_version(), and
        the behavior of is_issued() with multiple versions.'''
        session = Session()
        acc, seq = '99999', 1
        # initially max_version is 0, max_issued_version is None, and issued
        # is false
        b = ReeBill(self.customer, seq)
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
        self.session.add(Customer('someone', '11111', 0.5, 0.1,
                'customer1@example.com', 'FB Test Utility',
                'FB Test Rate Class', Address(), Address()))
        self.session.add(Customer('someone', '22222', 0.5, 0.1,
                'customer2@example.com', 'FB Test Utility',
                'FB Test Rate Class', Address(), Address()))
        session.add(ReeBill(self.state_db.get_customer('11111'), 1))
        session.add(ReeBill(self.state_db.get_customer('11111'), 2))
        session.add(ReeBill(self.state_db.get_customer('22222'), 1))
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
        session.add(ReeBill(self.customer, 1))
        session.add(ReeBill(self.customer, 2))
        session.add(ReeBill(self.customer, 3))
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

    def test_payments(self):
        acc = '99999'
        # one payment on jan 15
        self.state_db.create_payment(acc, date(2012,1,15), 'payment 1', 100)
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2011,12,1), date(2012,1,14)))
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2012,1,16), date(2012,2,1)))
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2012,2,1), date(2012,1,1)))
        payments = self.state_db.find_payment(acc, date(2012,1,1),
                date(2012,2,1))
        p = payments[0]
        self.assertEqual(1, len(payments))
        self.assertEqual((acc, datetime(2012,1,15), 'payment 1', 100),
                (p.customer.account, p.date_applied, p.description,
                p.credit))
        self.assertDatetimesClose(datetime.utcnow(), p.date_received)
        # should be editable since it was created today
        #self.assertEqual(True, p.to_dict()['editable'])

        # another payment on feb 1
        self.state_db.create_payment(acc, date(2012, 2, 1),
                'payment 2', 150)
        self.assertEqual([p], self.state_db.find_payment(acc,
                date(2012,1,1), date(2012,1,31)))
        self.assertEqual([], self.state_db.find_payment(acc,
                date(2012,2,2), date(2012,3,1)))
        payments = self.state_db.find_payment(acc, date(2012,1,16),
                date(2012,3,1))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,2,1), 'payment 2', 150),
                (q.customer.account, q.date_applied, q.description,
                q.credit))
        self.assertEqual(sorted([p, q]), sorted(self.state_db.payments(acc)))

        # update feb 1: move it to mar 1
        q.date_applied = datetime(2012,3,1)
        q.description = 'new description'
        q.credit = 200
        payments = self.state_db.find_payment(acc, datetime(2012,1,16),
                datetime(2012,3,2))
        self.assertEqual(1, len(payments))
        q = payments[0]
        self.assertEqual((acc, datetime(2012,3,1), 'new description', 200),
                (q.customer.account, q.date_applied, q.description,
                q.credit))

        # delete jan 15
        self.state_db.delete_payment(p.id)
        self.assertEqual([q], self.state_db.find_payment(acc,
                datetime(2012,1,1), datetime(2012,4,1)))


    def test_get_accounts_grid_data(self):
        empty_address = Address()
        fake_address = Address('Addressee', 'Street', 'City', 'ST', '12345')
        # Create 2 customers
        customer1 = self.session.query(Customer).one()
        customer2 = Customer('Test Customer', 99998, .12, .34,
                            'example@example.com', 'FB Test Utility Name',
                            'FB Test Rate Class', empty_address, empty_address)
        self.session.add(customer2)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(),
            [('99999', 'FB Test Utility Name', 'FB Test Rate Class', None,
              None, None, None, None, None, None),
             ('99998', 'FB Test Utility Name', 'FB Test Rate Class', None,
              None, None, None, None, None, None)])
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [('99998', 'FB Test Utility Name', 'FB Test Rate Class', None,
              None, None, None, None, None, None)])

        # Attach two utilitybills with out addresses but with rate class to one
        # of the customers, and one utilbill with empty rateclass but with
        # address to the other customer
        gas_bill_1 = UtilBill(customer1, 0, 'gas', 'washgas',
                'DC Non Residential Non Heat', empty_address, empty_address,
                period_start=date(2000, 1, 1), period_end=date(2000, 2, 1),
                processed=True)
        gas_bill_2 = UtilBill(customer1, 0, 'gas', 'washgas',
                'DC Non Residential Non Heat', empty_address, empty_address,
                period_start=date(2000, 3, 1), period_end=date(2000, 4, 1))
        gas_bill_3 = UtilBill(customer2, 0, 'gas', 'washgas',
                '', fake_address, fake_address,
                period_start=date(2000, 4, 1), period_end=date(2000, 5, 1),
                processed=True)
        self.session.add(gas_bill_1)
        self.session.add(gas_bill_2)
        self.session.add(gas_bill_3)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(),[
                ('99999', 'FB Test Utility Name', 'FB Test Rate Class',
                 False, None, None, None, 'DC Non Residential Non Heat',
                    empty_address, date(2000, 2, 1)),
                ('99998', 'FB Test Utility Name', 'FB Test Rate Class',
                 False, None, None, None, '',
                    fake_address, date(2000, 5, 1))])
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [('99998', 'FB Test Utility Name', 'FB Test Rate Class', False,
              None, None, None, '', fake_address, date(2000, 5, 1))]
        )

        # Now Attach a reebill to one and issue it , and a utilbill with a
        # different rateclass to the other
        reebill = ReeBill(customer1, 1, 0, utilbills=[gas_bill_1])
        gas_bill_4 = UtilBill(customer2, 0, 'gas', 'washgas',
                'New Rateclass', fake_address, fake_address,
                period_start=date(2000, 5, 1), period_end=date(2000, 6, 1),
                processed=True)
        issue_date = datetime(2014, 8, 9, 21, 6, 6)

        self.session.add(gas_bill_4)
        self.session.add(reebill)
        self.state_db.issue('99999', 1, issue_date)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(), [
                ('99999', 'FB Test Utility Name', 'FB Test Rate Class',
                 False, 1L, 0L, issue_date, 'DC Non Residential Non Heat',
                    empty_address, date(2000, 2, 1)),
                ('99998', 'FB Test Utility Name', 'FB Test Rate Class',
                 False, None, None, None, 'New Rateclass', fake_address,
                 date(2000, 6, 1))]
        )
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [('99998', 'FB Test Utility Name', 'FB Test Rate Class', False,
              None, None, None, 'New Rateclass', fake_address,
              date(2000, 6, 1))]
        )

        # Create another reebill, but don't issue it. The data should not change
        reebill_2 = ReeBill(customer1, 2, 0, utilbills=[gas_bill_2])
        self.session.add(reebill_2)
        self.session.commit()

        self.assertEqual(
            self.state_db.get_accounts_grid_data(), [
                ('99999', 'FB Test Utility Name', 'FB Test Rate Class',
                 False, 1L, 0L, issue_date, 'DC Non Residential Non Heat',
                    empty_address, date(2000, 2, 1)),
                ('99998', 'FB Test Utility Name', 'FB Test Rate Class',
                 False, None, None, None, 'New Rateclass', fake_address,
                 date(2000, 6, 1))]
        )
        self.assertEqual(
            self.state_db.get_accounts_grid_data('99998'),
            [('99998', 'FB Test Utility Name', 'FB Test Rate Class', False,
              None, None, None, 'New Rateclass', fake_address,
              date(2000, 6, 1))]
        )

if __name__ == '__main__':
    unittest.main()
