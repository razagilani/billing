#!/usr/bin/python
import unittest
from datetime import date, datetime, timedelta
import MySQLdb
import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
import pymongo
from billing.processing import state
from billing.processing.state import Customer, UtilBill, ReeBill
from billing.processing import mongo
from billing.util import dateutils
from billing.processing.session_contextmanager import DBSession
from billing.processing.exceptions import NoSuchBillException
from billing.test import utils, example_data

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}

class StateTest(utils.TestCase):
    def _clear_tables(self, db_connection):
        c = db_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from reebill")
        # clearing out utilbill_reebill should not be necessary because it
        # should cascade deletion from reebill
        c.execute("delete from utilbill_reebill")
        c.execute("delete from utilbill")
        c.execute("delete from customer")
        db_connection.commit()

    def setUp(self):
        # clear out database
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        self._clear_tables(mysql_connection)

        # insert one customer (not relying on StateDB)
        c = mysql_connection.cursor()
        c.execute('''insert into customer
                (name, account, discountrate, latechargerate,
                utilbill_template_id, bill_email_recipient) values
                ('Test Customer', 99999, .12, .34,
                '000000000000000000000000', 'example@example.com')''')
        mysql_connection.commit()

        # NOTE for some reason, when this is enabled, all tests fail with a
        # SQLAlchemy-related error; see 
        # https://www.pivotaltracker.com/story/show/58851006
        #sqlalchemy.orm.clear_mappers()

        self.state_db = state.StateDB('localhost', 'test', 'dev', 'dev')
        self.reebill_dao = mongo.ReebillDAO(self.state_db,
                pymongo.Connection(billdb_config['host'],
                int(billdb_config['port']))[billdb_config['database']])

    def tearDown(self):
        '''This gets run even if a test fails.'''
        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        self._clear_tables(mysql_connection)

    @unittest.skip("TODO re-enable. creation of another StateDB instance breaks the test even though it's a different DB and clear_mappers is run in setUp")
    def test_guess_next_reebill_end_date(self):
        '''Compare real end date to the one that would have been prediected.'''
        # use the real dev database
        state_db = state.StateDB(**{
            'user':'dev',
            'password':'dev',
            'host':'localhost',
            'database':'skyline_dev'
        })
        total = 0
        count = 0
        correct_count = 0
        session = state_db.session()
        for account in state_db.listAccounts(session):
            for sequence in state_db.listSequences(session, account):
                try:
                    reebill = self.reebill_dao.load_reebill(account, sequence)
                    guessed_end_date = state.guess_next_reebill_end_date(session,
                            account, reebill.period_begin)
                    difference = abs(reebill.period_end - guessed_end_date).days
                    total += difference
                    count += 1
                    if difference == 0:
                        correct_count += 1
                except Exception as e:
                    # TODO don't bury this error
                    print '%s-%s ERROR' % (account, sequence)
        print 'average difference: %s days' % (total / float(count))
        print 'guessed correctly: %s%%' % (100 * correct_count / float(count))
        
        # if we're right 95% of the time, guess_next_reebill_end_date() works
        self.assertTrue(correct_count / float(count) > .95)
        session.commit()
        
    def test_trim_hypothetical_utilbills(self):
        with DBSession(self.state_db) as session:
            account, service = '99999', 'gas'
            today = datetime.utcnow().date()
            customer = session.query(Customer).filter_by(account=account).one()

            # when there are no utility bills, trim_hypothetical_utilbills
            # should do nothing
            assert session.query(UtilBill).count() == 0
            self.state_db.trim_hypothetical_utilbills(session, account,
                    service)
            self.assertEqual(0, session.query(UtilBill).count())

            # TODO add tests for other services to make sure e.g. "electric"
            # bills are unaffected

            # to simplify the utility-bill-creation API
            def create_bill(start, end, state):
                session.add(UtilBill(customer, state, 'gas',
                        'washgas', 'DC Non Residential Non Heat',
                        period_start=start, period_end=end,
                        date_received=today))

            # when there are only Hypothetical utility bills,
            # trim_hypothetical_utilbills should remove all of them
            create_bill(date(2012,1,1), date(2012,2,1), UtilBill.Hypothetical)
            create_bill(date(2012,2,1), date(2012,3,1), UtilBill.Hypothetical)
            create_bill(date(2012,6,1), date(2012,7,1), UtilBill.Hypothetical)
            self.state_db.trim_hypothetical_utilbills(session, account,
                    service)
            self.assertEqual(0, session.query(UtilBill).count())

            # 2 Complete bills
            create_bill(date(2012,1,1), date(2012,2,1), UtilBill.Complete)
            create_bill(date(2012,6,15), date(2012,7,15), UtilBill.Complete)

            # Hypothetical bills before, between, and after the Complete bills
            # (including some overlaps with Complete bills and each other)
            create_bill(date(2011,9,1), date(2011,10,1), UtilBill.Hypothetical)
            create_bill(date(2011,10,1), date(2011,11,15), UtilBill.Hypothetical)
            create_bill(date(2011,11,15), date(2012,1,15), UtilBill.Hypothetical)
            create_bill(date(2012,1,30), date(2012,3,1), UtilBill.Hypothetical)
            create_bill(date(2012,3,1), date(2012,4,1), UtilBill.Hypothetical)
            create_bill(date(2012,6,1), date(2012,7,1), UtilBill.Hypothetical)
            create_bill(date(2012,7,20), date(2012,8,20), UtilBill.Hypothetical)
            create_bill(date(2012,7,20), date(2012,9,1), UtilBill.Hypothetical)

            self.state_db.trim_hypothetical_utilbills(session, account,
                    service)

        with DBSession(self.state_db) as session:
            # the survivors should be the ones with at least one period date in
            # the inner interval (end of earliest non-hypothetical bill to
            # start of latest)
            bills = self.state_db.list_utilbills(session, account)[0]\
                    .filter(UtilBill.state==UtilBill.Hypothetical).all()

            # Ensure that the results are sorted in ascending order by period_start
            # because the constant indices used in the assertions below rely on that order
            bills.sort(key=lambda x: x.period_start)

            self.assertEqual(3, len(bills))
            self.assertEqual((date(2012,1,30), date(2012,3,1)),
                    (bills[0].period_start, bills[0].period_end))
            self.assertEqual((date(2012,3,1), date(2012,4,1)),
                    (bills[1].period_start, bills[1].period_end))
            self.assertEqual((date(2012,6,1), date(2012,7,1)),
                    (bills[2].period_start, bills[2].period_end))
        

    def test_new_reebill(self):
        with DBSession(self.state_db) as session:
            b = self.state_db.new_reebill(session, '99999', 1)
            self.assertEqual('99999', b.customer.account)
            self.assertEqual(1, b.sequence)
            self.assertEqual(0, b.version)
            self.assertEqual(0, b.issued)
            session.commit()

    def test_versions(self):
        '''Tests max_version(), max_issued_version(), increment_version(), and
        the behavior of is_issued() with multiple versions.'''
        acc, seq = '99999', 1
        with DBSession(self.state_db) as session:
            # initially max_version is 0, max_issued_version is None, and issued
            # is false
            b = self.state_db.new_reebill(session, acc, seq)
            self.assertEqual(0, self.state_db.max_version(session, acc, seq))
            self.assertEqual(None, self.state_db.max_issued_version(session,
                    acc, seq))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=1)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=2)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)

            # adding versions of bills for other accounts should have no effect
            session.add(Customer('someone', '11111', 0.5, 0.1,
                    'id goes here', 'customer1@example.com'))
            session.add(Customer('someone', '22222', 0.5, 0.1,
                    'id goes here', 'customer2@example.com'))
            self.state_db.new_reebill(session, '11111', 1)
            self.state_db.new_reebill(session, '11111', 2)
            self.state_db.new_reebill(session, '22222', 1)
            self.state_db.issue(session, '11111', 1)
            self.state_db.issue(session, '22222', 1)
            self.state_db.increment_version(session, '11111', 1)
            self.state_db.increment_version(session, '22222', 1)
            self.state_db.issue(session, '22222', 1)
            self.state_db.increment_version(session, '22222', 1)
            self.assertEqual(0, self.state_db.max_version(session, acc, seq))
            self.assertEqual(None, self.state_db.max_issued_version(session,
                    acc, seq))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=1)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=2)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)

            # incrementing version to 1 should fail when the bill is not issued
            self.assertRaises(Exception, self.state_db.increment_version,
                    session, acc, seq)
            self.assertEqual(0, self.state_db.max_version(session, acc, seq))
            self.assertEqual(None, self.state_db.max_issued_version(session,
                    acc, seq))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=1)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=2)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)

            # issue & increment version to 1
            self.state_db.issue(session, acc, seq)
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq)) # default version for is_issued is highest, i.e. 1
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=1)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=2)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)
            self.state_db.increment_version(session, acc, seq)
            self.assertEqual(1, self.state_db.max_version(session, acc, seq))
            self.assertEqual(0, self.state_db.max_issued_version(session, acc,
                    seq))
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq,
                    version=1))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=2)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)

            # issue version 1 & create version 2
            self.state_db.issue(session, acc, seq)
            self.assertEqual(1, self.state_db.max_issued_version(session, acc,
                    seq))
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq))
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq,
                    version=1))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=2)
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)
            self.state_db.increment_version(session, acc, seq)
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq))
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq,
                    version=0))
            self.assertEqual(True, self.state_db.is_issued(session, acc, seq,
                    version=1))
            self.assertEqual(False, self.state_db.is_issued(session, acc, seq,
                    version=2))
            self.assertRaises(NoResultFound, self.state_db.is_issued, session,
                    acc, seq, version=10)
            self.assertEqual(2, self.state_db.max_version(session, acc, seq))
            self.assertEqual(1, self.state_db.max_issued_version(session, acc,
                    seq))

            # issue version 2
            self.state_db.issue(session, acc, seq)
            self.assertEqual(2, self.state_db.max_issued_version(session, acc,
                    seq))

            session.commit()

    def test_get_unissued_corrections(self):
        with DBSession(self.state_db) as session:
            # reebills 1-4, 1-3 issued
            self.state_db.new_reebill(session, '99999', 1)
            self.state_db.new_reebill(session, '99999', 2)
            self.state_db.new_reebill(session, '99999', 3)
            self.state_db.issue(session, '99999', 1)
            self.state_db.issue(session, '99999', 2)
            self.state_db.issue(session, '99999', 3)

            # no unissued corrections yet
            self.assertEquals([],
                    self.state_db.get_unissued_corrections(session, '99999'))

            # make corrections on 1 and 3
            self.state_db.increment_version(session, '99999', 1)
            self.state_db.increment_version(session, '99999', 3)
            self.assertEquals([(1, 1), (3, 1)],
                    self.state_db.get_unissued_corrections(session, '99999'))

            # issue 3
            self.state_db.issue(session, '99999', 3)
            self.assertEquals([(1, 1)],
                    self.state_db.get_unissued_corrections(session, '99999'))

            # issue 1
            self.state_db.issue(session, '99999', 1)
            self.assertEquals([],
                    self.state_db.get_unissued_corrections(session, '99999'))

            session.commit()

    @unittest.skip('StateDB.delete_reebill no longer exists; move elsewhere?')
    def test_delete_reebill(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            # un-issued bill version 0: row is actually deleted from the table
            self.state_db.new_reebill(session, account, 1)
            assert self.state_db.max_version(session, account, 1) == 0
            assert not self.state_db.is_issued(session, account, 1)
            customer = session.query(Customer).filter_by(account=account).one()
            reebill = session.query(ReeBill).filter_by(customer=customer, sequence=1, version=0)
            self.state_db.delete_reebill(session, reebill)
            self.assertEqual([], self.state_db.listSequences(session, account))

            # issued bill can't be deleted
            self.state_db.new_reebill(session, account, 1)
            self.state_db.issue(session, account, 1)
            assert reebill.issued
            # TODO check for a more specific exception
            self.assertRaises(Exception, self.state_db.delete_reebill, session,
                    reebill)

            # make a new version, which is not issued; that can be deleted by
            # decrementing max_version
            self.state_db.increment_version(session, account, 1)
            assert self.state_db.max_version(session, account, 1) == 1
            assert not self.state_db.is_issued(session, account, 1)
            reebill_correction = session.query(ReeBill).filter_by(
                    account=account, sequence=1, version=1)
            assert not reebill_correction.issued
            self.state_db.delete_reebill(session, account, 1)
            self.assertEqual([1], self.state_db.listSequences(session, account))
            self.assertEqual(0, self.state_db.max_version(session, account, 1))

            # remaining version 0 can't be deleted
            # TODO check for a more specific exception
            self.assertRaises(Exception, self.state_db.delete_reebill, session,
                    account, 1)

            session.commit()

    def test_payments(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            # one payment on jan 15
            self.state_db.create_payment(session, acc, date(2012,1,15),
                    'payment 1', 100)
            self.assertEqual([], self.state_db.find_payment(session, acc,
                    date(2011,12,1), date(2012,1,14)))
            self.assertEqual([], self.state_db.find_payment(session, acc,
                    date(2012,1,16), date(2012,2,1)))
            self.assertEqual([], self.state_db.find_payment(session, acc,
                    date(2012,2,1), date(2012,1,1)))
            payments = self.state_db.find_payment(session, acc, date(2012,1,1),
                    date(2012,2,1))
            p = payments[0]
            self.assertEqual(1, len(payments))
            self.assertEqual((acc, date(2012,1,15), 'payment 1', 100),
                    (p.customer.account, p.date_applied, p.description,
                    p.credit))
            self.assertDatetimesClose(datetime.utcnow(), p.date_received)
            # should be editable since it was created today
            #self.assertEqual(True, p.to_dict()['editable'])

            # another payment on feb 1
            self.state_db.create_payment(session, acc, date(2012, 2, 1),
                    'payment 2', 150)
            self.assertEqual([p], self.state_db.find_payment(session, acc,
                    date(2012,1,1), date(2012,1,31)))
            self.assertEqual([], self.state_db.find_payment(session, acc,
                    date(2012,2,2), date(2012,3,1)))
            payments = self.state_db.find_payment(session, acc, date(2012,1,16),
                    date(2012,3,1))
            self.assertEqual(1, len(payments))
            q = payments[0]
            self.assertEqual((acc, date(2012,2,1), 'payment 2', 150),
                    (q.customer.account, q.date_applied, q.description,
                    q.credit))
            self.assertEqual(sorted([p, q]),
                    sorted(self.state_db.payments(session, acc)))

            # update feb 1: move it to mar 1
            self.state_db.update_payment(session, q.id, date(2012,3,1),
                        'new description', 200)
            payments = self.state_db.find_payment(session, acc, date(2012,1,16),
                    date(2012,3,2))
            self.assertEqual(1, len(payments))
            q = payments[0]
            self.assertEqual((acc, date(2012,3,1), 'new description', 200),
                    (q.customer.account, q.date_applied, q.description,
                    q.credit))

            # delete jan 15
            self.state_db.delete_payment(session, p.id)
            self.assertEqual([q], self.state_db.find_payment(session, acc,
                    date(2012,1,1), date(2012,4,1)))


    def test_get_last_reebill(self):
        with DBSession(self.state_db) as session:
            customer = session.query(Customer).one()

            self.assertEqual(None, self.state_db.get_last_reebill(session,
                    '99999'))

            utilbill = UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat', period_start=date(2000,1,1),
                    period_end=date(2000,2,1))
            reebill = ReeBill(customer, 1, 0, utilbills=[utilbill])
            session.add(utilbill)
            session.add(reebill)

            self.assertEqual(reebill, self.state_db.get_last_reebill(session,
                    '99999'))
            self.assertEqual(None, self.state_db.get_last_reebill(session,
                    '99999', issued_only=True))

    def test_get_last_real_utilbill(self):
        with DBSession(self.state_db) as session:
            customer = session.query(Customer).one()

            self.assertRaises(NoSuchBillException,
                    self.state_db.get_last_real_utilbill, session, '99999',
                    date(2001,1,1))

            # one bill
            gas_bill_1 = UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat', period_start=date(2000,1,1),
                    period_end=date(2000,2,1))
            session.add(gas_bill_1)

            self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                    session, '99999', date(2000,3,1)))
            self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                    session, '99999', date(2000,2,1)))
            self.assertRaises(NoSuchBillException,
                    self.state_db.get_last_real_utilbill, session, '99999',
                    date(2000,1,31))

            # two bills
            electric_bill = UtilBill(customer, 0, 'electric', 'pepco',
                    'whatever', period_start=date(2000,1,2),
                    period_end=date(2000,2,2))
            self.assertEqual(electric_bill,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000, 3, 1)))
            self.assertEqual(electric_bill,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000, 2, 2)))
            self.assertEqual(gas_bill_1,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000, 2, 1)))
            self.assertRaises(NoSuchBillException,
                    self.state_db.get_last_real_utilbill, session, '99999',
                    date(2000,1,31))

            # electric bill is ignored if service "gas" is specified
            self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                    session, '99999', date(2000,2,2), service='gas'))
            self.assertEqual(gas_bill_1, self.state_db.get_last_real_utilbill(
                    session, '99999', date(2000,2,1), service='gas'))
            self.assertRaises(NoSuchBillException,
                    self.state_db.get_last_real_utilbill, session, '99999',
                    date(2000,1,31), service='gas')

            # filter by utility and rate class
            self.assertEqual(gas_bill_1,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000,3,1), utility='washgas'))
            self.assertEqual(gas_bill_1,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000,3,1), rate_class='DC Non Residential Non Heat'))
            self.assertEqual(electric_bill,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000,3,1), utility='pepco', rate_class='whatever'))
            self.assertEqual(electric_bill,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000,3,1), rate_class='whatever'))
            self.assertEqual(electric_bill,
                    self.state_db.get_last_real_utilbill(session, '99999',
                    date(2000,3,1), utility='pepco', rate_class='whatever'))
            self.assertRaises(NoSuchBillException,
                    self.state_db.get_last_real_utilbill, session, '99999',
                    date(2000,1,31), utility='washgas', rate_class='whatever')

            # hypothetical utility bills are always ignored
            gas_bill_1.state = UtilBill.Hypothetical
            electric_bill.state = UtilBill.Hypothetical
            self.assertRaises(NoSuchBillException,
                    self.state_db.get_last_real_utilbill, session, '99999',
                    date(2000,3,1))


if __name__ == '__main__':
    unittest.main()
