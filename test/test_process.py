#!/usr/bin/python
import sys
import unittest
from StringIO import StringIO
import ConfigParser
import pymongo
import sqlalchemy
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from datetime import date, datetime, timedelta
from billing import dateutils, mongo
from billing.dateutils import estimate_month, month_offset
from billing.processing import rate_structure
from billing.processing.process import Process
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
from decimal import Decimal
from billing.dictutils import deep_map
import MySQLdb
from billing.mongo_utils import python_convert
from billing.test import example_data

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ProcessTest(unittest.TestCase):
    # apparenty this is what you need to do if you override the __init__ method
    # of a TestCase
    #def __init__(self, methodName='runTest', param=None):
        #print '__init__'
        #super(ProcessTest, self).__init__(methodName)

    def setUp(self):
        # this method runs before every test.
        # clear SQLAlchemy mappers so StateDB can be instantiated again
        sqlalchemy.orm.clear_mappers()

        # everything needed to create a Process object
        config_file = StringIO('''[runtime]\nintegrate_skyline_backend = true''')
        self.config = ConfigParser.RawConfigParser()
        self.config.readfp(config_file)
        self.reebill_dao = mongo.ReebillDAO({
            'billpath': '/db-dev/skyline/bills/',
            'database': 'test',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'test_reebills',
            'host': 'localhost',
            'port': 27017
        })
        self.rate_structure_dao = rate_structure.RateStructureDAO({
            'database': 'test',
            'collection': 'ratestructure',
            'host': 'localhost',
            'port': 27017
        })
        self.splinter = Splinter('http://duino-drop.appspot.com/', 'tyrell',
                'dev')
        self.monguru = Monguru('tyrell', 'dev')

        # temporary hack to get a bill that's always the same
        # this bill came straight out of mongo (except for .date() applied to
        # datetimes)
        ISODate = lambda s: datetime.strptime(s, dateutils.ISO_8601_DATETIME)
        true, false = True, False

        # customer database ("test" database has already been created with
        # empty customer table)
        statedb_config = {
            'host': 'localhost',
            'database': 'test',
            'user': 'dev',
            'password': 'dev'
        }

        ## clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
        c.execute("delete from customer")
        # (note that status_days_since, status_unbilled are views and you
        # neither can nor need to delete from them)
        mysql_connection.commit()

        # insert one customer
        self.state_db = StateDB(**statedb_config)
        session = self.state_db.session()
        # name, account, discount rate, late charge rate
        customer = Customer('Test Customer', '99999', .12, .34)
        session.add(customer)
        session.commit()

    def tearDown(self):
        print 'tearDown'
        '''This gets run even if a test fails.'''
        # clear out mongo test database
        mongo_connection = pymongo.Connection('localhost', 27017)
        mongo_connection.drop_database('test')

        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
        c.execute("delete from customer")
        mysql_connection.commit()

    def test_get_late_charge(self):
        print 'test_get_late_charge'
        '''Tests computation of late charges (without rolling bills).'''
        try:
            session = self.state_db.session()
            process = Process(self.config, self.state_db, self.reebill_dao,
                    self.rate_structure_dao, self.splinter, self.monguru)
 
            bill1 = example_data.get_reebill('99999', 1)
            bill1.balance_forward = Decimal('100.')
            self.assertEqual(0, process.get_late_charge(session, bill1,
                date(2011,12,31)))
            self.assertEqual(0, process.get_late_charge(session, bill1,
                date(2012,1,1)))
            self.assertEqual(0, process.get_late_charge(session, bill1,
                date(2012,1,2)))
            self.assertEqual(0, process.get_late_charge(session, bill1,
                date(2012,2,1)))
            self.assertEqual(0, process.get_late_charge(session, bill1,
                date(2012,2,2)))
 
            # issue bill 1, so a later bill can have a late charge based on the
            # customer's failure to pay bill1 by its due date. i.e. 30 days
            # after issue date. (it must be saved in both mongo and mysql to be
            # issued.)
            self.reebill_dao.save_reebill(bill1)
            self.state_db.new_rebill(session, bill1.account, bill1.sequence)
            process.issue(session, bill1.account, bill1.sequence,
                    issue_date=date(2012,1,1))
            # since process.issue() only modifies databases, bill1 must be
            # re-loaded from mongo to reflect its new issue date
            bill1 = self.reebill_dao.load_reebill(bill1.account, bill1.sequence)
            assert bill1.due_date == date(2012,1,31)
 
            # after bill1 is created, it must be "summed" to get it into a
            # usable state (in particular, it needs a late charge). that
            # requires a sequence 0 template bill. put one into mongo and then
            # sum bill1.
            bill0 = example_data.get_reebill('99999', 0)
            process.sum_bill(session, bill0, bill1)
 
            # but sum_bill() destroys bill1's balance_due, so reset it to
            # the right value, and save it in mongo
            bill1.balance_due = Decimal('100.')
            self.reebill_dao.save_reebill(bill1)
 
            # create second bill (not by rolling, because process.roll_bill()
            # is currently a huge untested mess, and get_late_charge() should
            # be tested in isolation). note that bill1's late charge is set in
            # mongo by process.issue().
            bill2 = example_data.get_reebill('99999', 2)
            bill2.balance_due = Decimal('200.')
            # bill2's late_charge_rate is copied from MySQL during rolling, but
            # since bill2 is not created by rolling, it must be set explicitly.
            bill2.late_charge_rate = Decimal('0.34')

            # bill2's late charge should be 0 before bill1's due date, and
            # after the due date, it's balance * (1 + late charge rate), i.e.
            # 100 * (1 + .34)
            self.assertEqual(0, process.get_late_charge(session, bill2,
                date(2011,12,31)))
            self.assertEqual(0, process.get_late_charge(session, bill2,
                date(2012,1,2)))
            self.assertEqual(0, process.get_late_charge(session, bill2,
                date(2012,1,31)))
            self.assertEqual(134, process.get_late_charge(session, bill2,
                date(2012,2,1)))
            self.assertEqual(134, process.get_late_charge(session, bill2,
                date(2012,2,2)))
            self.assertEqual(134, process.get_late_charge(session, bill2,
                date(2013,1,1)))
 
            # in order to get late charge of a 3rd bill, bill2 must be put into
            # mysql and "summed"
            self.state_db.new_rebill(session, bill2.account, bill2.sequence)
            process.sum_bill(session, bill1, bill2)
 
            # create a 3rd bill without issuing bill2. bill3 should have None
            # as its late charge for all dates
            bill3 = example_data.get_reebill('99999', 3)
            bill3.balance_due = Decimal('300.')
            self.assertEqual(None, process.get_late_charge(session, bill3,
                date(2011,12,31)))
            self.assertEqual(None, process.get_late_charge(session, bill3,
                date(2013,1,1)))
 
            session.commit()
        except:
            if 'session' in locals():
                session.rollback()
            raise

    @unittest.skip('''Creating a second StateDB object, even if it's for
            another database, fails with a SQLAlchemy error about multiple
            mappers. SQLAlchemy does provide a way to get around this.''')
    def test_sequences_for_approximate_month(self):
        print 'test_sequences_for_approximate_month'
        # use real databases instead of the fake ones
        state_db = StateDB(
            host='localhost',
            database='skyline_dev',
            user='dev',
            password='dev'
        )
        reebill_dao = mongo.ReebillDAO({
            'billpath': '/db-dev/skyline/bills/',
            'database': 'skyline',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'reebills',
            'host': 'localhost',
            'port': 27017
        })
        process = Process(self.config, self.state_db, reebill_dao,
                self.rate_structure_dao, self.splinter, self.monguru)
        session = self.state_db.session()
        for account in self.state_db.listAccounts(session):
            for sequence in self.state_db.listSequences(session, account):
                reebill = reebill_dao.load_reebill(account, sequence)

                # get real approximate month for this bill
                year, month = estimate_month(reebill.period_begin,
                        reebill.period_end)

                # make sure it's contained in the result of
                # sequences_for_approximate_month(), and make sure that result
                # never contains any sequence whose bill's approximate month is
                # not this month
                sequences_this_month = process\
                        .sequences_for_approximate_month(session, account,
                        year, month)
                self.assertIn(sequence, sequences_this_month)
                reebills = [reebill_dao.load_reebill(account, seq) for seq in
                        sequences_this_month]
                months = [estimate_month(r.period_begin,
                    r.period_end) for r in reebills]
                self.assertTrue(all([m == (year, month) for m in months]))

        # test months before last sequence
        self.assertEquals([], process.sequences_for_approximate_month(session,
            '10001', 2009, 10))
        self.assertEquals([], process.sequences_for_approximate_month(session,
            '10001', 2009, 10))
        self.assertEquals([], process.sequences_for_approximate_month(session,
            '10002', 2010, 1))

        # test 3 months after last sequence for each account
        for account in self.state_db.listAccounts(session):
            last_seq = self.state_db.last_sequence(session, account)
            if last_seq == 0: continue
            last = reebill_dao.load_reebill(account, last_seq)
            last_year, last_month = estimate_month(last.period_begin,
                    last.period_end)
            next_year, next_month = month_offset(last_year, last_month, 1)
            next2_year, next2_month = month_offset(last_year, last_month, 2)
            next3_year, next3_month = month_offset(last_year, last_month, 3)
            self.assertEquals([last_seq + 1],
                    process.sequences_for_approximate_month(session, account,
                    next_year, next_month))
            self.assertEquals([last_seq + 2],
                    process.sequences_for_approximate_month(session, account,
                    next2_year, next2_month))
            self.assertEquals([last_seq + 3],
                    process.sequences_for_approximate_month(session, account,
                    next3_year, next3_month))

        session.commit()

    def test_service_suspension(self):
        print 'test_service_suspension'
        try:
            session = self.state_db.session()
            process = Process(self.config, self.state_db, self.reebill_dao,
                    self.rate_structure_dao, self.splinter, self.monguru)

            # generic reebill
            bill1 = example_data.get_reebill('99999', 1)
            bill1.account = '99999'
            bill1.sequence = 1

            # make it have 2 services, 1 suspended
            # (create electric bill by duplicating gas bill)
            electric_bill = example_data.get_utilbill_dict()
            electric_bill['service'] = 'electric'
            bill1.dictionary['utilbills'].append(electric_bill)
            bill1.suspend_service('electric')
            self.assertEquals(['electric'], bill1.suspended_services)

            # save reebill in MySQL and Mongo
            self.state_db.new_rebill(session, bill1.account, bill1.sequence)
            self.reebill_dao.save_reebill(bill1)

            # save utilbills in MySQL
            self.state_db.record_utilbill_in_database(session, bill1.account,
                    bill1.dictionary['utilbills'][0]['service'],
                    bill1.dictionary['utilbills'][0]['period_begin'],
                    bill1.dictionary['utilbills'][0]['period_end'], date.today())
            self.state_db.record_utilbill_in_database(session, bill1.account,
                    bill1.dictionary['utilbills'][1]['service'],
                    bill1.dictionary['utilbills'][1]['period_begin'],
                    bill1.dictionary['utilbills'][1]['period_end'], date.today())

            process.attach_utilbills(session, bill1.account, bill1.sequence)

            # only the gas bill should be attached
            customer = session.query(Customer).filter(Customer.account==bill1.account).all()
            reebill = session.query(ReeBill).filter(ReeBill.customer_id == Customer.id)\
                    .filter(ReeBill.sequence==bill1.sequence).one()
            attached_utilbills = session.query(UtilBill).filter(UtilBill.reebill==reebill).all()
            self.assertEquals(1, len(attached_utilbills))
            self.assertEquals('gas', attached_utilbills[0].service.lower())

            session.commit()
        except:
            if 'session' in locals():
                session.rollback()
            raise

    def test_bind_rate_structure(self):
        print 'test_bind_rate_structure'

        # make a reebill
        account, sequence = '99999', 1
        bill1 = example_data.get_reebill(account, sequence)
        service = bill1.services[0]
        utility_name = bill1.utility_name_for_service(service)
        rate_structure_name = bill1.rate_structure_name_for_service(service)

        # make rate structure documents and save them in db
        urs_dict = example_data.get_urs_dict()
        cprs_dict = example_data.get_cprs_dict(account, sequence)
        self.rate_structure_dao.save_urs(utility_name, rate_structure_name,
                bill1.period_begin, bill1.period_end, urs_dict)
        self.rate_structure_dao.save_cprs(account, sequence, 0, utility_name,
                rate_structure_name, cprs_dict)
        #rs = self.rate_structure_dao.load_probable_rs(bill1, service)
        rs = self.rate_structure_dao.load_rate_structure(bill1, service)

        process = Process(self.config, self.state_db, self.reebill_dao,
                self.rate_structure_dao, self.splinter, self.monguru)
        process.bindrs(bill1, None)

if __name__ == '__main__':
    unittest.main(failfast=True)
