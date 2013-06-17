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
from billing.processing.mongo import MongoReebill, NoSuchBillException, IssuedBillError
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
            self.reebill_dao.save_reebill(b)
            self.state_db.new_reebill(session, acc, 1)

            # function to check that the utility bill matches the reebill's
            # reference to it
            def check():
                # reebill should be loadable
                reebill = self.reebill_dao.load_reebill(acc, 1, version=0)
                # there should be one utilbill document
                all_utilbills = self.reebill_dao.load_utilbills()
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
            self.reebill_dao.save_reebill(b)
            check()

            # NOTE account, utility name, service can't be changed, but if they
            # become changeable, do the same test for them

    def test_get_reebill_doc_for_utilbills(self):
        reebill = MongoReebill.get_reebill_doc_for_utilbills('99999', 0.5, 0.1,
                [example_data.get_utilbill_dict('99999', utility='washgas',
                service='gas', start=date(2013,1,1), end=date(2013,2,1))])
        self.assertEquals('99999', reebill.account)
        self.assertEquals(1, reebill.sequence)
        self.assertEquals(0, reebill.version)
        self.assertEquals(0, reebill.ree_charges)
        self.assertEquals(0, reebill.ree_value)
        self.assertEquals(0.5, reebill.discount_rate)
        self.assertEquals(0.1, reebill.late_charge_rate)
        self.assertEquals(0, reebill.late_charges)
        self.assertEquals(1, len(reebill._utilbills)) # TODO test content
        self.assertEquals(None, reebill.issue_date)
        self.assertEquals(0, reebill.payment_received)
        self.assertEquals(0, reebill.actual_total)
        self.assertEquals(None, reebill.due_date)
        self.assertEquals(0, reebill.total_adjustment)
        self.assertEquals(0, reebill.ree_savings)
        self.assertEquals(0, reebill.ree_savings)
        self.assertEquals(0, reebill.balance_due)
        self.assertEquals(0, reebill.prior_balance)
        self.assertEquals(0, reebill.balance_forward)
        self.assertEquals(0, reebill.hypothetical_total)

        # note that address schema as returned by MongoReebill is very
        # different from the utility bill schema that it came from
        self.assertEquals({
            "ba_city" : "Silver Spring",
            "ba_state" : "MD",
            "ba_addressee" : "Managing Member Monroe Towers",
            "ba_postal_code" : "20910",
            "ba_street1" : "3501 13TH ST NW LLC"
        }, reebill.billing_address)
        self.assertEquals({
            "sa_addressee" : "Monroe Towers",
            "sa_state" : "DC",
            "sa_city" : "Washington",
            "sa_street1" : "3501 13TH ST NW #WH",
            "sa_postal_code" : "20010"
        }, reebill.service_address)

        # NOTE "statistics" is not tested because it will go away

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
