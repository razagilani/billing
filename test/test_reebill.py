#!/usr/bin/python
import unittest
import pymongo
import sqlalchemy
import copy
from datetime import date, datetime, timedelta
from billing.util import dateutils
from billing.processing import mongo
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
import MySQLdb
from billing.test import example_data
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.mongo import NoSuchBillException, IssuedBillError
from billing.processing.session_contextmanager import DBSession

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillTest(TestCaseWithSetup):
    '''Tests for MongoReebill methods.'''
    
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
