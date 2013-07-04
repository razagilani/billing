#!/usr/bin/python
import unittest
from datetime import date, datetime
import MySQLdb
import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
from billing.processing import state
from billing.processing.state import Customer, UtilBill
from billing.processing import mongo
from billing.util import dateutils
from billing.processing.session_contextmanager import DBSession
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
    def setUp(self):
        # clear out database
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from reebill")
        c.execute("delete from customer")
        mysql_connection.commit()

        # insert one customer (not relying on StateDB)
        c = mysql_connection.cursor()
        c.execute('''insert into customer
                (name, account, discountrate, latechargerate) values
                ('Test Customer', 99999, .12, .34)''')
        mysql_connection.commit()

        sqlalchemy.orm.clear_mappers()
        self.state_db = state.StateDB(**{
            'user':'dev',
            'password':'dev',
            'host':'localhost',
            'database':'test'
        })
        self.reebill_dao = mongo.ReebillDAO(self.state_db, **billdb_config)

    def tearDown(self):
        '''This gets run even if a test fails.'''
        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from reebill")
        c.execute("delete from customer")
        mysql_connection.commit()

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

            # 2 Complete bills
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,1,1), date(2012,2,1), 0, today)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,6,15), date(2012,7,15), 0, today)

            # Hypothetical bills before, between, and after the Complete bills
            # (including some overlaps with Complete bills and each other)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2011,9,1), date(2011,10,1), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2011,10,1), date(2011,11,15), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2011,11,15), date(2012,1,15), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,1,30), date(2012,3,1), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,3,1), date(2012,4,1), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,6,1), date(2012,7,1), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,7,20), date(2012,8,20), 0, today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,7,20), date(2012,9,1), 0, today,
                    state=UtilBill.Hypothetical)

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

    def test_delete_reebill(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            # un-issued bill version 0: row is actually deleted from the table
            self.state_db.new_reebill(session, account, 1)
            assert self.state_db.max_version(session, account, 1) == 0
            assert not self.state_db.is_issued(session, account, 1)
            self.state_db.delete_reebill(session, account, 1)
            self.assertEqual([], self.state_db.listSequences(session, account))

            # issued bill can't be deleted
            self.state_db.new_reebill(session, account, 1)
            self.state_db.issue(session, account, 1)
            self.assertRaises(Exception, self.state_db.delete_reebill, session, account, 1)

            # make a new version, which is not issued; that can be deleted by
            # decrementing max_version
            self.state_db.increment_version(session, account, 1)
            assert self.state_db.max_version(session, account, 1) == 1
            assert not self.state_db.is_issued(session, account, 1)
            self.state_db.delete_reebill(session, account, 1)
            self.assertEqual([1], self.state_db.listSequences(session, account))
            self.assertEqual(0, self.state_db.max_version(session, account, 1))

            # remaining version 0 can't be deleted
            self.assertRaises(Exception, self.state_db.delete_reebill, session, account, 1)

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

    def utilbill_period_single_unattached(self):
        # Add ten, nice, sequential gas bills
        account = '99999'
        services = ['gas']
        dt = date.today()
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            # Add ten utilbills "associated" to reebills
            reebills = [ReeBill(customer, x) for x in xrange(1, 11)]
            for r in reebills:
                r.issued = 1
            utilbills = [UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat', dt+timedelta(days=30*x),
                    dt+timedelta(days=30*(x+1)), reebill=reebills[x])
                    for x in xrange(0, 10)]
            for x in xrange(10):
                session.add(reebills[x])
                session.add(utilbills[x])

            # Add one utilbill that comes after the last utilbill from the above loop
            target_utilbill = UtilBill(customer, 0, 'gas', 'washgas'
                    'DC Non Residential Non Heat',
                    period_start=dt+timedelta(days=30*10),
                    period_end=dt+timedelta(days=30*11), reebill=None)
            session.add(target_utilbill)

            utilbills = self.state_db.choose_next_utilbills(session, account, services)
            self.assertListEqual(services, [ub.service for ub in utilbills])
            self.assertEqual(len(utilbills), 1)
            self.assertIsNotNone(utilbills[0])
            self.assertIsNone(utilbills[0].reebill)
            self.assertEqual(utilbills[0], target_utilbill)

    def utilbill_period_multiple_unattached(self):
        # Add ten, nice, sequential gas bills
        account = '99999'
        services = ['gas']
        dt = date.today()
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            # Add ten utilbills "associated" to reebills
            reebills = [ReeBill(customer, x) for x in xrange(1, 11)]
            for r in reebills:
                r.issued = 1
            utilbills = [UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    dt+timedelta(days=30*x),\ dt+timedelta(days=30*(x+1)),
                    reebill=reebills[x]) for x in xrange(0, 10)]
            for x in xrange(10):
                session.add(reebills[x])
                session.add(utilbills[x])

            # Add multiple utilbills that come after the last utilbill from the above loop
            target_utilbill = UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    period_start=dt+timedelta(days=30*10),
                    period_end=dt+timedelta(days=30*11), reebill=None)
            session.add(target_utilbill)
            session.add(UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    period_start=dt+timedelta(days=30*11),
                    period_end=dt+timedelta(days=30*12), reebill=None))
            session.add(UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    period_start=dt+timedelta(days=30*12),
                    period_end=dt+timedelta(days=30*13), reebill=None))

            # Same tests
            utilbills = self.state_db.choose_next_utilbills(session, account, services) self.assertListEqual(services, [ub.service for ub in utilbills])
            self.assertEqual(len(utilbills), 1)
            self.assertIsNotNone(utilbills[0])
            self.assertIsNone(utilbills[0].reebill)
            self.assertEqual(utilbills[0], target_utilbill)

    def utilbill_period_legacy_unattached(self):
        account = '99999'
        services = ['gas']
        dt = date.today()
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            # 7 reebills, 10 utilbills
            reebills = [None, None, None] + [ReeBill(customer, x+1) for x in xrange(1, 8)]
            for r in reebills:
                if r is not None:
                    r.issued = 1
            utilbills = [UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat', dt+timedelta(days=30*x),
                    dt+timedelta(days=30*(x+1)),
                    reebill=reebills[x]) for x in xrange(0, 10)]

            # None entries in reebills won't go into the database, so they are stripped here
            reebills = reebills[3:]

            # Add ten utilbills "associated" to reebills, but the first three have no reebill association
            for r in reebills:
                session.add(r)
            for ub in utilbills:
                session.add(ub)

            # Add an unattached utilbill that comes after the last utilbill from the above loop
            target_utilbill = UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    period_start=dt+timedelta(days=30*10),
                    period_end=dt+timedelta(days=30*11), reebill=None)
            session.add(target_utilbill)

            # Same tests
            utilbills = self.state_db.choose_next_utilbills(session, account, services)
            self.assertListEqual(services, [ub.service for ub in utilbills])
            self.assertEqual(len(utilbills), 1)
            self.assertIsNotNone(utilbills[0])
            self.assertIsNone(utilbills[0].reebill)
            self.assertEqual(utilbills[0], target_utilbill)

    def utilbill_period_multiple_services(self):
        account = '99999'
        services = ['gas', 'electric']
        dt_gas = date.today()
        dt_elec = date.today() + timedelta(days=9)
        
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            reebills = [ReeBill(customer, x+1) for x in xrange(1, 11)]
            for r in reebills:
                r.issued = 1
            gas_utilbills = [UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    dt_gas+timedelta(days=30*x),\ dt_gas+timedelta(days=30*(x+1)),
                    reebill=reebills[x]) for x in xrange(0, 10)]
            elec_utilbills = [UtilBill(customer, 0, 'electric', 'pepco',
                    'DC Non Residential Non Heat',
                    dt_elec+timedelta(days=30*x),\
                    dt_elec+timedelta(days=30*(x+1)), reebill=reebills[x])
                    for x in xrange(0, 10)]

            # Add twenty utilbills "associated" to reebills, ten of gas and ten of electric
            # The gas and electric bills are on different time periods
            for x in xrange(10):
                session.add(reebills[x])
                session.add(gas_utilbills[x])
                session.add(elec_utilbills[x])

            target_gas_utilbill = UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    period_start=dt_gas+timedelta(days=30*10),
                    period_end=dt_gas+timedelta(days=30*11), reebill=None)
            session.add(target_gas_utilbill)

            target_elec_utilbill = UtilBill(customer, 0, 'electric', 'pepco',
                    'DC Non Residential Non Heat',
                    period_start=dt_elec+timedelta(days=30*10),
                    period_end=dt_elec+timedelta(days=30*11), reebill=None)
            session.add(target_elec_utilbill)

            utilbills = self.state_db.choose_next_utilbills(session, account,
                    services)
            self.assertListEqual(services, [ub.service for ub in utilbills])
            self.assertEqual(len(utilbills), 2)
            self.assertIsNotNone(utilbills[0])
            self.assertIsNotNone(utilbills[1])
            self.assertIsNone(utilbills[0].reebill)
            self.assertIsNone(utilbills[1].reebill)
            ub_dict = {ub.service: ub for ub in utilbills}
            self.assertEqual(ub_dict['gas'], target_gas_utilbill)
            self.assertEqual(ub_dict['electric'], target_elec_utilbill)

    def utilbill_period_first_utilbill(self):
        account = '99999'
        services = ['gas']
        dt = date.today()
        
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            target_utilbill = UtilBill(customer, 0, 'gas', 'washgas',
                    'DC Non Residential Non Heat',
                    period_start=dt, period_end=dt+timedelta(days=30),
                    reebill=None)
            session.add(target_utilbill)

            utilbills = self.state_db.choose_next_utilbills(session, account, services)
            self.assertListEqual(services, [ub.service for ub in utilbills])
            self.assertEqual(len(utilbills), 1)
            self.assertIsNotNone(utilbills[0])
            self.assertIsNone(utilbills[0].reebill)
            self.assertEqual(utilbills[0], target_utilbill)

if __name__ == '__main__':
    unittest.main()
