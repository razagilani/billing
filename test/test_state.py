#!/usr/bin/python
import unittest
from datetime import date, datetime
import MySQLdb
import sqlalchemy
from billing.processing import state
from billing.processing.db_objects import Customer, UtilBill
from billing import mongo
from billing import dateutils
from billing.session_contextmanager import DBSession

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}

class StateTest(unittest.TestCase):
    def setUp(self):
        sqlalchemy.orm.clear_mappers()
        self.state_db = state.StateDB(**{
            'user':'dev',
            'password':'dev',
            'host':'localhost',
            'database':'test'
        })
        self.reebill_dao = mongo.ReebillDAO(billdb_config)

        # insert one customer (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute('''insert into customer
                (name, account, discountrate, latechargerate) values
                ('Test Customer', 99999, .12, .34)''')
        mysql_connection.commit()

    def tearDown(self):
        '''This gets run even if a test fails.'''
        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
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
                    service, date(2012,1,1), date(2012,2,1), today)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,6,15), date(2012,7,15), today)

            # Hypothetical bills before, between, and after the Complete bills
            # (including some overlaps with Complete bills and each other)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2011,9,1), date(2011,10,1), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2011,10,1), date(2011,11,15), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2011,11,15), date(2012,1,15), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,1,30), date(2012,3,1), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,3,1), date(2012,4,1), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,6,1), date(2012,7,1), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,7,20), date(2012,8,20), today,
                    state=UtilBill.Hypothetical)
            self.state_db.record_utilbill_in_database(session, account,
                    service, date(2012,7,20), date(2012,9,1), today,
                    state=UtilBill.Hypothetical)

            self.state_db.trim_hypothetical_utilbills(session, account,
                    service)

        with DBSession(self.state_db) as session:
            # the survivors should be the ones with at least one period date in
            # the inner interval (end of earliest non-hypothetical bill to
            # start of latest)
            bills = self.state_db.list_utilbills(session, account)[0]\
                    .filter(UtilBill.state==UtilBill.Hypothetical).all()
            self.assertEqual(3, len(bills))
            self.assertEqual((date(2012,1,30), date(2012,3,1)),
                    (bills[0].period_start, bills[0].period_end))
            self.assertEqual((date(2012,3,1), date(2012,4,1)),
                    (bills[1].period_start, bills[1].period_end))
            self.assertEqual((date(2012,6,1), date(2012,7,1)),
                    (bills[2].period_start, bills[2].period_end))
        

if __name__ == '__main__':
    unittest.main()
