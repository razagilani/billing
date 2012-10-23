#!/usr/bin/python
import unittest
import pymongo
import sqlalchemy
import copy
from datetime import date, datetime, timedelta
from billing import dateutils
from billing.processing import mongo
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
import MySQLdb
from billing.test import example_data
from billing.processing.mongo import NoSuchBillException, IssuedBillError
from billing.processing.session_contextmanager import DBSession

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillTest(unittest.TestCase):
    '''Tests for MongoReebill methods.'''

    def setUp(self):
        # this method runs before every test.
        # clear SQLAlchemy mappers so StateDB can be instantiated again
        sqlalchemy.orm.clear_mappers()

        # customer database ("test" database has already been created with
        # empty customer table)
        self.state_db = StateDB(**{
            'user':'dev',
            'password':'dev',
            'host':'localhost',
            'database':'test'
        })

        self.dao = mongo.ReebillDAO(self.state_db, **{
            'billpath': '/db-dev/skyline/bills/',
            'database': 'test',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'test_reebills',
            'host': 'localhost',
            'port': 27017
        })
        
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
        session = self.state_db.session()
        # name, account, discount rate, late charge rate
        customer = Customer('Test Customer', '99999', .12, .34)
        session.add(customer)
        session.commit()

    def tearDown(self):
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
    
    def test_utilbill_periods(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            # a reebill
            b = example_data.get_reebill(acc, 1)
            self.dao.save_reebill(b)
            self.state_db.new_rebill(session, acc, 1)

            # function to check that the utility bill matches the reebill's
            # reference to it
            def check():
                # reebill should be loadable
                reebill = self.dao.load_reebill(acc, 1, version=0)
                # there should be one utilbill document
                all_utilbills = self.dao.load_utilbills()
                self.assertEquals(1, len(all_utilbills))
                # all its _id fields dates should match the reebill's reference
                # to it
                self.assertEquals(reebill._utilbills[0]['_id'],
                        reebill.reebill_dict['utilbills'][0]['id'])
                
            # this must work because nothing has been changed yet
            check()

            # change utilbill period
            b.set_utilbill_period_for_service(b.services[0], (date(2100,1,1),
                    date(2100,2,1)))
            check()
            self.dao.save_reebill(b)
            check()

            # NOTE account, utility name, service can't be changed, but if they
            # become changeable, do the same test for them

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
