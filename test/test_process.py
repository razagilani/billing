import sys
import os
import unittest
import operator
from StringIO import StringIO
import ConfigParser
import logging
import pymongo
from bson import ObjectId
import sqlalchemy
from sqlalchemy.sql import desc
import re
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner.sky_handlers import cross_range
from datetime import date, datetime, timedelta
from billing.processing import mongo
from billing.processing.session_contextmanager import DBSession
from billing.util.dateutils import estimate_month, month_offset, date_to_datetime
from billing.processing import rate_structure2
from billing.processing.rate_structure2 import RateStructure, RateStructureItem
from billing.processing.process import Process, IssuedBillError
from billing.processing.state import StateDB, ReeBill, Customer, UtilBill
from billing.processing.billupload import BillUpload
from billing.util.dictutils import deep_map
import MySQLdb
from billing.util.mongo_utils import python_convert
from billing.test.setup_teardown import TestCaseWithSetup
from billing.test import example_data
from skyliner.mock_skyliner import MockSplinter, MockMonguru, hour_of_energy
from billing.util.nexus_util import NexusUtil
from billing.processing.mongo import NoSuchBillException
from billing.processing.exceptions import BillStateError, NotUniqueException, NoRateStructureError
from billing.processing import fetch_bill_data as fbd
from billing.test import utils

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint
pformat = pprint.PrettyPrinter(indent=1).pformat

class ProcessTest(TestCaseWithSetup, utils.TestCase):
    # apparenty this is what you need to do if you override the __init__ method
    # of a TestCase
    #def __init__(self, methodName='runTest', param=None):
        #print '__init__'
        #super(ProcessTest, self).__init__(methodName)

    def test_create_new_account(self):
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

        with DBSession(self.state_db) as session:
            # NOTE template account "99999" already exists.
            # store its template utility bill to check whether it was modified later
            template_account_template_utilbill = self.reebill_dao.\
                    load_utilbill_template(session, '99999')

            # create new account "88888" based on template account "99999"
            self.process.create_new_account(session, '88888', 'New Account',
                    0.6, 0.2, billing_address, service_address, '99999')

            # check MySQL customer
            customer = self.state_db.get_customer(session, '88888')
            self.assertEquals('88888', customer.account)
            self.assertEquals(0.6, customer.get_discount_rate())
            self.assertEquals(0.2, customer.get_late_charge_rate())
            template_customer = self.state_db.get_customer(session, '99999')
            self.assertNotEqual(template_customer.utilbill_template_id,
                    customer.utilbill_template_id)
            utilbill_template = self.reebill_dao.load_utilbill_template(
                    session, '88888')

            # no utility bills or reebills exist in MySQL for the new account yet
            self.assertEquals([], self.state_db.listSequences(session, '88888'))
            self.assertEquals([],
                    session.query(UtilBill).filter_by(customer=customer).all())

            # create first utility bill and reebill
            self.process.upload_utility_bill(session, '88888', 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf')
            utilbill = session.query(UtilBill).filter_by(customer=customer)\
                    .one()
            self.process.create_first_reebill(session, utilbill)
            reebill = session.query(ReeBill).one()

            # check utility bill and its document
            self.assertEqual(UtilBill.Complete, utilbill.state)
            self.assertEqual('gas', utilbill.service)
            self.assertEqual('washgas', utilbill.utility)
            self.assertEqual('DC Non Residential Non Heat',
                    utilbill.rate_class)
            self.assertEqual(date(2013,1,1), utilbill.period_start)
            self.assertEqual(date(2013,2,1), utilbill.period_end)
            self.assertEqual(0, utilbill.total_charges)
            self.assertEqual(date_to_datetime(datetime.utcnow().date()),
                    utilbill.date_received)
            self.assertEqual(False, utilbill.processed) # what does 'processed' mean anyway?
            self.assertIsNotNone(utilbill.document_id)
            self.assertIsNotNone(utilbill.uprs_document_id)
            self.assertIsNotNone(utilbill.cprs_document_id)
            utilbill_doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertNotEqual(template_account_template_utilbill['_id'],
                    utilbill_doc['_id'])
            self.assertEqual('88888', utilbill_doc['account'])
            self.assertEqual('gas', utilbill_doc['service'])
            self.assertEqual('washgas', utilbill_doc['utility'])
            self.assertEqual(date(2013,1,1), utilbill_doc['start'])
            self.assertEqual(date(2013,2,1), utilbill_doc['end'])
            self.assertEqual({'All Charges': []},
                    utilbill_doc['chargegroups'])
            self.assertEqual(0, utilbill_doc['total'])
            self.assertEqual(billing_address, utilbill_doc['billing_address'])
            self.assertEqual(service_address, utilbill_doc['service_address'])

            # check reebill and its document
            self.assertEqual(1, reebill.sequence)
            self.assertEqual(0, reebill.version)
            self.assertEqual(False, reebill.issued)
            self.assertEqual(None, reebill.issue_date)
            self.assertEqual([utilbill], reebill.utilbills)
            reebill_doc = self.reebill_dao.load_reebill('88888', 1)
            self.assertEqual('88888', reebill_doc.account)
            self.assertEqual(1, reebill_doc.sequence)
            self.assertEqual(0, reebill_doc.version)
            self.assertEqual(0, reebill_doc.ree_charges)
            # some bills lack late_charges key, which is supposed to be
            # distinct from late_charges: None, and late_charges: 0
            try:
                self.assertEquals(0, reebill_doc.late_charges)
            except KeyError as ke:
                if ke.message != 'late_charges':
                    raise
            self.assertEqual(0, reebill_doc.ree_value)
            self.assertEqual(0.6, reebill_doc.discount_rate)
            self.assertEqual(0.2, reebill_doc.late_charge_rate)
            self.assertEqual(None, reebill_doc.motd)
            self.assertEqual([utilbill_doc['_id']], [ObjectId(u['id']) for u in
                    reebill_doc.reebill_dict['utilbills']])
            self.assertEqual([utilbill_doc], reebill_doc._utilbills)
            self.assertEqual(0, reebill_doc.payment_received)
            self.assertEqual(0, reebill_doc.total_adjustment)
            self.assertEqual(0, reebill_doc.manual_adjustment)
            self.assertEqual(0, reebill_doc.ree_savings)
            # NOTE ignoring statistics because that will go away
            self.assertEqual(0, reebill_doc.balance_due)
            self.assertEqual(0, reebill_doc.prior_balance)
            self.assertEqual(0, reebill_doc.hypothetical_total)
            self.assertEqual(0, reebill_doc.balance_forward)
            self.assertEqual(billing_address, reebill_doc.billing_address)
            self.assertEqual(service_address, reebill_doc.service_address)

            # TODO check Mongo rate structure documents

            # check that template account's utility bill and reebill was not
            # modified
            template_account_template_utilbill_again = self.reebill_dao\
                    .load_utilbill_template(session, '99999')
            self.assertEquals(template_account_template_utilbill,
                    template_account_template_utilbill_again)

            # it should not be possible to create an account that already
            # exists
            self.assertRaises(ValueError, self.process.create_new_account,
                    session, '88888', 'New Account', 0.6, 0.2, billing_address,
                    service_address, '99999')

            # try creating another account when the template account has no
            # utility bills yet
            self.process.create_new_account(session, '77777', 'New Account',
                    0.6, 0.2, billing_address, service_address, '88888')
            self.process.create_new_account(session, '66666', 'New Account',
                    0.6, 0.2, billing_address, service_address, '88888')


    def test_get_docs(self):
        '''Tests Process.get_utilbill_doc and Process.get_rs_doc: retrieving
        documents for utility bills on their own or with a particular reebill
        version.'''
        with DBSession(self.state_db) as session:
            # upload some utility bills (only the first will be loaded)
            self.process.upload_utility_bill(session, '99999', 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf')
            self.process.upload_utility_bill(session, '99999', 'gas',
                    date(2013,2,1), date(2013,3,1), StringIO('January 2013'),
                    'january.pdf')
            utilbill = session.query(UtilBill).order_by(UtilBill.period_start)\
                    .first()
            assert utilbill.period_start == date(2013,1,1)

            # check invalid rate structure type names
            self.assertRaises(ValueError, self.process.get_rs_doc, session,
                    utilbill.id, 'UPRS')
            self.assertRaises(ValueError, self.process.get_rs_doc, session,
                    utilbill.id, 'CPRS')
            #self.assertRaises(ValueError, self.process.get_rs_doc, session,
                    #utilbill.id, 'urs')
            #self.assertRaises(ValueError, self.process.get_rs_doc, session,
                    #utilbill.id, 'URS')

            # documents loaded via get_utilbill_doc and get_rs_doc should be
            # the same as when loaded directly using reebill_dao
            utilbill_doc = self.process.get_utilbill_doc(session, utilbill.id)
            uprs_doc = self.process.get_rs_doc(session, utilbill.id, 'uprs')
            cprs_doc = self.process.get_rs_doc(session, utilbill.id, 'cprs')
            self.assertEqual(utilbill_doc,
                    self.reebill_dao.load_doc_for_utilbill(utilbill))
            self.assertEqual(uprs_doc,
                    self.rate_structure_dao.load_uprs_for_utilbill(utilbill))
            self.assertEqual(cprs_doc,
                    self.rate_structure_dao.load_cprs_for_utilbill(utilbill))

            # issue a reebill based on this utility bill, then modify the
            # editable utility bill so it's different from the frozen ones
            self.process.create_first_reebill(session, utilbill)
            self.process.issue(session, '99999', 1)
            utilbill_doc = self.process.get_utilbill_doc(session, utilbill.id)
            uprs_doc = self.process.get_rs_doc(session, utilbill.id, 'uprs')
            cprs_doc = self.process.get_rs_doc(session, utilbill.id, 'cprs')
            utilbill_doc['service'] = 'electricity'
            new_rsi = RateStructureItem(rsi_binding='NEW', rate='36.25',
                    quantity='1')
            uprs_doc.rates = [new_rsi]
            cprs_doc.rates = [new_rsi]
            self.reebill_dao.save_utilbill(utilbill_doc)
            uprs_doc.save()
            cprs_doc.save()

            # load frozen documents associated with the issued reebill
            frozen_utilbill_doc = self.process.get_utilbill_doc(session,
                    utilbill.id, reebill_sequence=1, reebill_version=0)
            frozen_uprs_doc = self.process.get_rs_doc(session, utilbill.id,
                    'uprs', reebill_sequence=1, reebill_version=0)
            frozen_cprs_doc = self.process.get_rs_doc(session, utilbill.id,
                    'cprs', reebill_sequence=1, reebill_version=0)
            self.assertNotEqual(frozen_utilbill_doc, utilbill_doc)
            self.assertNotEqual(frozen_uprs_doc, uprs_doc)
            self.assertNotEqual(frozen_cprs_doc, cprs_doc)
            self.assertEquals('gas', frozen_utilbill_doc['service'])
            self.assertNotIn(new_rsi, frozen_uprs_doc.rates)
            self.assertNotIn(new_rsi, frozen_cprs_doc.rates)

            # editable documents should be unchanged
            utilbill_doc = self.process.get_utilbill_doc(session, utilbill.id)
            uprs_doc = self.process.get_rs_doc(session, utilbill.id, 'uprs')
            cprs_doc = self.process.get_rs_doc(session, utilbill.id, 'cprs')
            self.assertEqual(utilbill_doc,
                    self.reebill_dao.load_doc_for_utilbill(utilbill))
            self.assertEqual(uprs_doc,
                    self.rate_structure_dao.load_uprs_for_utilbill(utilbill))
            self.assertEqual(cprs_doc,
                    self.rate_structure_dao.load_cprs_for_utilbill(utilbill))
            self.assertEquals('electricity', utilbill_doc['service'])
            self.assertIn(new_rsi, uprs_doc.rates)
            self.assertIn(new_rsi, cprs_doc.rates)

    def test_update_utilbill_metadata(self):
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, '99999', 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf', total=100)
            utilbill = session.query(UtilBill).one()
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            assert utilbill.period_start == doc['start'] == date(2013,1,1)
            assert utilbill.period_end == doc['end'] == date(2013,2,1)
            assert utilbill.service == doc['service'] == 'gas'
            assert utilbill.utility == doc['utility'] == 'washgas'
            assert utilbill.total_charges == 100
            assert utilbill.rate_class == doc['rate_class'] == 'DC Non Residential Non Heat'

            # invalid date ranges
            self.assertRaises(ValueError,
                    self.process.update_utilbill_metadata, session,
                    utilbill.id, period_start=date(2014,1,1))
            self.assertRaises(ValueError,
                    self.process.update_utilbill_metadata, session,
                    utilbill.id, period_end=date(2012,1,1))
            self.assertRaises(ValueError,
                    self.process.update_utilbill_metadata, session,
                    utilbill.id, period_end=date(2014,2,1))

            # change start date
            self.process.update_utilbill_metadata(session, utilbill.id,
                    period_start=date(2013,1,2))
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEqual(date(2013,1,2), utilbill.period_start)
            self.assertEqual(date(2013,1,2), doc['start'])
            for meter in doc['meters']:
                self.assertEqual(date(2013,1,2), meter['prior_read_date'])

            # change end date
            self.process.update_utilbill_metadata(session, utilbill.id,
                    period_end=date(2013,2,2))
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEqual(date(2013,2,2), utilbill.period_end)
            self.assertEqual(date(2013,2,2), doc['end'])
            for meter in doc['meters']:
                self.assertEqual(date(2013,2,2), meter['present_read_date'])

            # change service
            self.process.update_utilbill_metadata(session, utilbill.id,
                    service='electricity')
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEqual('electricity', utilbill.service)
            self.assertEqual('electricity', doc['service'])

            # change "total" aka "total_charges"
            self.process.update_utilbill_metadata(session, utilbill.id,
                    total_charges=200)
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEqual(200, utilbill.total_charges)
            # NOTE "total" is not in utility bill Mongo documents, only MySQL

            # change utility name
            self.process.update_utilbill_metadata(session, utilbill.id,
                    utility='BGE')
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEqual('BGE', utilbill.utility)
            self.assertEqual('BGE', doc['utility'])

            # change rate class
            self.process.update_utilbill_metadata(session, utilbill.id,
                    rate_class='something else')
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEqual('something else', utilbill.rate_class)
            self.assertEqual('something else', doc['rate_class'])

            # even when the utility bill is attached to an issued reebill, only
            # the editable document gets changed
            self.process.create_first_reebill(session, utilbill)
            reebill = session.query(ReeBill).one()
            self.process.issue(session, '99999', 1)
            self.process.update_utilbill_metadata(session, utilbill.id,
                    service='water')
            editable_doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            frozen_doc = self.reebill_dao.load_doc_for_utilbill(utilbill,
                    reebill=reebill)
            assert 'sequence' not in editable_doc and 'version' not in editable_doc
            assert frozen_doc['sequence'] == 1 and frozen_doc['version'] == 0
            self.assertNotEqual(editable_doc, frozen_doc)
            self.assertEqual('electricity', frozen_doc['service'])
            self.assertEqual('water', utilbill.service)
            self.assertEqual('water', editable_doc['service'])


    def test_get_late_charge(self):
        '''Tests computation of late charges (without rolling bills).'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # set customer late charge rate
            self.state_db.get_customer(session, acc).set_late_charge_rate(.34)

            # create utility bill and first reebill, with no late charge
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), StringIO('January 2012'),
                    'january.pdf')
            self.process.create_first_reebill(session,
                    session.query(UtilBill).one())
            bill1 = self.reebill_dao.load_reebill(acc, 1)
            self.assertEqual(0, self.process.get_late_charge(session, bill1,
                    date(2011,12,31)))
            self.assertEqual(0, self.process.get_late_charge(session, bill1,
                    date(2012,1,1)))
            self.assertEqual(0, self.process.get_late_charge(session, bill1,
                    date(2012,1,2)))
            self.assertEqual(0, self.process.get_late_charge(session, bill1,
                    date(2012,2,1)))
            self.assertEqual(0, self.process.get_late_charge(session, bill1,
                    date(2012,2,2)))

            # issue bill 1, so a later bill can have a late charge based on the
            # customer's failure to pay bill1 by its due date, i.e. 30 days
            # after the issue date.
            self.process.issue(session, bill1.account, bill1.sequence,
                    issue_date=date(2012,1,1))
            # since process.issue() only modifies databases, bill1 must be
            # re-loaded from mongo to reflect its new issue date
            self.state_db.get_reebill(session, acc, 1, version=0).issue_date \
                    == date(2012,1,1)
            bill1 = self.reebill_dao.load_reebill(bill1.account, bill1.sequence)
            assert bill1.due_date == date(2012,1,31)
 
            # after bill1 is created, it must be computed to get it into a
            # usable state (in particular, it needs a late charge).
            self.process.compute_reebill(session, bill1)
 
            # but compute_reebill() destroys bill1's balance_due, so reset it to
            # the right value, and save it in mongo
            bill1.balance_due = 100
            self.reebill_dao.save_reebill(bill1, force=True)

            # create 2nd utility bill and reebill
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2012,2,1), date(2012,3,1), StringIO('February 2012'),
                    'february.pdf')
            self.process.create_next_reebill(session, acc)
            bill2 = self.reebill_dao.load_reebill(acc, 2)
            bill2.balance_due = 200

            # bill2's late charge should be 0 before bill1's due date, and
            # after the due date, it's balance * late charge rate, i.e.
            # 100 * .34
            self.assertEqual(0, self.process.get_late_charge(session, bill2,
                    date(2011,12,31)))
            self.assertEqual(0, self.process.get_late_charge(session, bill2,
                    date(2012,1,2)))
            self.assertEqual(0, self.process.get_late_charge(session, bill2,
                    date(2012,1,31)))
            self.assertEqual(34, self.process.get_late_charge(session, bill2,
                    date(2012,2,1)))
            self.assertEqual(34, self.process.get_late_charge(session, bill2,
                    date(2012,2,2)))
            self.assertEqual(34, self.process.get_late_charge(session, bill2,
                    date(2013,1,1)))
 
            # in order to get late charge of a 3rd bill, bill2 must be computed
            self.process.compute_reebill(session, bill2)
 
            # create a 3rd bill without issuing bill2. bill3 should have None
            # as its late charge for all dates
            bill3 = example_data.get_reebill(acc, 3)
            bill3.balance_due = 300
            self.assertEqual(None, self.process.get_late_charge(session, bill3,
                    date(2011,12,31)))
            self.assertEqual(None, self.process.get_late_charge(session, bill3,
                    date(2013,1,1)))

            # late charge should be based on the version with the least total
            # of the bill from which it derives. on 2013-01-15, make a version
            # 1 of bill 1 with a lower total, and then on 2013-03-15, a version
            # 2 with a higher total, and check that the late charge comes from
            # version 1. 
            self.process.new_version(session, acc, 1)
            bill1_1 = self.reebill_dao.load_reebill(acc, 1, version=1)
            bill1_1.balance_due = 50
            self.reebill_dao.save_reebill(bill1_1)
            self.process.issue(session, acc, 1, issue_date=date(2013,3,15))
            self.process.new_version(session, acc, 1)
            bill1_2 = self.reebill_dao.load_reebill(acc, 1, version=2)
            bill1_2.balance_due = 300
            self.reebill_dao.save_reebill(bill1_2)
            self.process.issue(session, acc, 1)
            # note that the issue date on which the late charge in bill2 is
            # based is the issue date of version 0--it doesn't matter when the
            # corrections were issued.
            self.assertEqual(50 * bill2.late_charge_rate,
                    self.process.get_late_charge(session, bill2,
                    date(2013,1,1)))

            # add a payment between 2012-01-01 (when bill1 version 0 was
            # issued) and 2013-01-01 (the present), to make sure that payment
            # is deducted from the balance on which the late charge is based
            self.state_db.create_payment(session, acc, date(2012,6,5),
                    'a $10 payment in june', 10)
            self.assertEqual((50 - 10) * bill2.late_charge_rate,
                    self.process.get_late_charge(session, bill2,
                    date(2013,1,1)))

            #Pay off the bill, make sure the late charge is 0
            self.state_db.create_payment(session, acc, date(2012,6,6),
                    'a $40 payment in june', 40)
            self.assertEqual(0, self.process.get_late_charge(session, bill2,
                    date(2013,1,1)))

            #Overpay the bill, make sure the late charge is still 0
            self.state_db.create_payment(session, acc, date(2012,6,7),
                    'a $40 payment in june', 40)
            self.assertEqual(0, self.process.get_late_charge(session, bill2,
                    date(2013,1,1)))
            

    @unittest.skip('''Creating a second StateDB object, even if it's for
            another database, fails with a SQLAlchemy error about multiple
            mappers. SQLAlchemy does provide a way to get around this.''')
    def test_sequences_for_approximate_month(self):
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

    @unittest.skip(('Multiple services are not yet supported; fix this test and'
            're-enable it when they are.'))
    def test_service_suspension(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2012,1,1), date(2012,2,1), file1, 'january.pdf')
            self.process.upload_utility_bill(session, account, 'gas',
                     date(2012,1,1), date(2012,2,1), file1, 'february.pdf')

            # generic reebill
            bill0 = example_data.get_reebill(account, 0)

            # make it have 2 services, 1 suspended
            # (create electric bill by duplicating gas bill)
            electric_bill = example_data.get_utilbill_dict(account, service='electric')
            #self.reebill_dao.save_utilbill(electric_bill)
            # TODO it's bad to directly modify reebill_dict
            bill0.reebill_dict['utilbills'].append({
                'id': electric_bill['_id'],
                'service': 'electric',
                'utility': electric_bill['utility'],
                'start': electric_bill['start'],
                'end': electric_bill['end'],
            })
            bill0._utilbills.append(electric_bill)
            bill0.suspend_service('electric')
            self.reebill_dao.save_reebill(bill0)

            bill1 = self.process.roll_bill(session, bill0)

            self.assertEquals(['electric'], bill1.suspended_services)

            # only the gas bill should be attached
            customer = self.state_db.get_customer(session, account)
            reebill = session.query(ReeBill)\
                    .filter(ReeBill.customer_id == customer.id)\
                    .filter(ReeBill.sequence==bill1.sequence).one()
            attached_utilbills = session.query(UtilBill)\
                    .filter(UtilBill.reebills.contains(reebill)).all()
            self.assertEquals(1, len(attached_utilbills))
            self.assertEquals('gas', attached_utilbills[0].service.lower())

    def test_bind_rate_structure(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            # create utility bill and reebill
            self.process.upload_utility_bill(session, account, 'gas',
                     date(2012,1,1), date(2012,2,1), StringIO('January 2012'),
                     'january.pdf')
            utilbill = session.query(UtilBill).one()
            self.process.create_first_reebill(session, utilbill)

            # the UPRS for this utility bill will be empty, because there are
            # no other utility bills in the db, and the bill will have no
            # charges; all the charges in the template bill get removed because
            # the rate structure has no RSIs in it. so, add RSIs and charges
            # corresponding to them from example_data. (this is the same way
            # the user would manually add RSIs and charges when processing the
            # first bill for a given rate structure.)
            uprs = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
            uprs.rates = example_data.get_uprs().rates
            utilbill_doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            utilbill_doc['chargegroups'] = example_data.get_utilbill_dict(
                    '99999')['chargegroups']
            uprs.save()
            self.reebill_dao.save_utilbill(utilbill_doc)

            # also add some charges to the CPRS to test overriding of UPRS by CPRS
            cprs = self.rate_structure_dao.load_cprs_for_utilbill(utilbill)
            cprs.rates = example_data.get_cprs().rates
            cprs.save()

            # compute charges in the bill using the rate structure created from the
            # above documents
            reebill1 = self.reebill_dao.load_reebill(account, 1)
            reebill1.compute_charges(uprs, cprs)

            # ##############################################################
            # check that each actual (utility) charge was computed correctly:
            actual_chargegroups = reebill1.actual_chargegroups_for_service('gas')
            assert actual_chargegroups.keys() == ['All Charges']
            actual_charges = actual_chargegroups['All Charges']
            actual_registers = reebill1.actual_registers('gas')
            total_regster = [r for r in actual_registers if r['register_binding'] == 'REG_TOTAL'][0]

            # system charge: $11.2 in CPRS overrides $26.3 in URS
            system_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'SYSTEM_CHARGE'][0]
            self.assertDecimalAlmostEqual(11.2, system_charge['total'])

            # right-of-way fee
            row_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'RIGHT_OF_WAY'][0]
            self.assertDecimalAlmostEqual(0.03059 * float(total_regster['quantity']),
                    row_charge['total'], places=2) # TODO OK to be so inaccurate?
            
            # sustainable energy trust fund
            setf_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'SETF'][0]
            self.assertDecimalAlmostEqual(0.01399 * float(total_regster['quantity']),
                    setf_charge['total'], places=1) # TODO OK to be so inaccurate?

            # energy assistance trust fund
            eatf_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'EATF'][0]
            self.assertDecimalAlmostEqual(0.006 * float(total_regster['quantity']),
                    eatf_charge['total'], places=2)

            # delivery tax
            delivery_tax = [c for c in actual_charges if c['rsi_binding'] ==
                    'DELIVERY_TAX'][0]
            self.assertDecimalAlmostEqual(0.07777 * float(total_regster['quantity']),
                    delivery_tax['total'], places=2)

            # peak usage charge
            peak_usage_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'PUC'][0]
            self.assertDecimalAlmostEqual(23.14, peak_usage_charge['total'])

            # distribution charge
            distribution_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'DISTRIBUTION_CHARGE'][0]
            self.assertDecimalAlmostEqual(.2935 * float(total_regster['quantity']),
                    distribution_charge['total'], places=2)
            
            # purchased gas charge
            purchased_gas_charge = [c for c in actual_charges if c['rsi_binding'] ==
                    'PGC'][0]
            self.assertDecimalAlmostEqual(.7653 * float(total_regster['quantity']),
                    purchased_gas_charge['total'], places=2)

            # sales tax: depends on all of the above
            sales_tax = [c for c in actual_charges if c['rsi_binding'] ==
                    'SALES_TAX'][0]
            self.assertDecimalAlmostEqual(0.06 * float(system_charge['total'] +
                    distribution_charge['total'] + purchased_gas_charge['total'] +
                    row_charge['total'] + peak_usage_charge['total'] +
                    setf_charge['total'] + eatf_charge['total'] +
                    delivery_tax['total']),
                    sales_tax['total'],
                    places=2)


            # ##############################################################
            # check that each hypothetical charge was computed correctly:
            self.process.compute_reebill(session, reebill1)
            self.reebill_dao.save_reebill(reebill1)
            reebill1 = self.reebill_dao.load_reebill(account, 1)
            hypothetical_chargegroups = reebill1.hypothetical_chargegroups_for_service('gas')
            assert hypothetical_chargegroups.keys() == ['All Charges']
            hypothetical_charges = hypothetical_chargegroups['All Charges']
            shadow_registers = reebill1.shadow_registers('gas')
            total_shadow_regster = [r for r in shadow_registers if r['register_binding'] == 'REG_TOTAL'][0]
            hypothetical_quantity = float(total_shadow_regster['quantity'] + total_regster['quantity'])

            # system charge: $11.2 in CPRS overrides $26.3 in URS
            system_charge = [c for c in hypothetical_charges if
                    c['rsi_binding'] == 'SYSTEM_CHARGE'][0]
            self.assertDecimalAlmostEqual(11.2, system_charge['total'])

            # right-of-way fee
            row_charge = [c for c in hypothetical_charges if c['rsi_binding']
                    == 'RIGHT_OF_WAY'][0]
            self.assertDecimalAlmostEqual(0.03059 * hypothetical_quantity,
                    row_charge['total'], places=2) # TODO OK to be so inaccurate?
            
            # sustainable energy trust fund
            setf_charge = [c for c in hypothetical_charges if c['rsi_binding']
                    == 'SETF'][0]
            self.assertDecimalAlmostEqual(0.01399 * hypothetical_quantity,
                    setf_charge['total'], places=1) # TODO OK to be so inaccurate?

            # energy assistance trust fund
            eatf_charge = [c for c in hypothetical_charges if c['rsi_binding']
                    == 'EATF'][0]
            self.assertDecimalAlmostEqual(0.006 * hypothetical_quantity,
                    eatf_charge['total'], places=2)

            # delivery tax
            delivery_tax = [c for c in hypothetical_charges if c['rsi_binding']
                    == 'DELIVERY_TAX'][0]
            self.assertDecimalAlmostEqual(0.07777 * hypothetical_quantity,
                    delivery_tax['total'], places=2)

            # peak usage charge
            peak_usage_charge = [c for c in hypothetical_charges if
                    c['rsi_binding'] == 'PUC'][0]
            self.assertDecimalAlmostEqual(23.14, peak_usage_charge['total'])

            # distribution charge
            distribution_charge = [c for c in hypothetical_charges if
                    c['rsi_binding'] == 'DISTRIBUTION_CHARGE'][0]
            self.assertDecimalAlmostEqual(.2935 * hypothetical_quantity,
                    distribution_charge['total'], places=1)
            
            # purchased gas charge
            purchased_gas_charge = [c for c in hypothetical_charges if
                    c['rsi_binding'] == 'PGC'][0]
            self.assertDecimalAlmostEqual(.7653 * hypothetical_quantity,
                    purchased_gas_charge['total'], places=2)

            # sales tax: depends on all of the above
            sales_tax = [c for c in hypothetical_charges if c['rsi_binding'] ==
                    'SALES_TAX'][0]
            self.assertDecimalAlmostEqual(0.06 * (system_charge['total'] +
                distribution_charge['total'] + purchased_gas_charge['total'] +
                row_charge['total'] + peak_usage_charge['total'] +
                setf_charge['total'] + eatf_charge['total'] +
                delivery_tax['total']), sales_tax['total'], places=2)


    def test_upload_utility_bill(self):
        '''Tests saving of utility bills in database (which also belongs partly
        to StateDB); does not test saving of utility bill files (which belongs
        to BillUpload).'''
        # TODO include test of saving of utility bill files here
        with DBSession(self.state_db) as session:
            account, service = '99999', 'gas'

            # one utility bill
            file1 = StringIO("Let's pretend this is a PDF")
            self.process.upload_utility_bill(session, account, service,
                    date(2012,1,1), date(2012,2,1), file1, 'january.pdf')
            bills = self.state_db.list_utilbills(session,
                    account)[0].filter(UtilBill.service==service).all()
            self.assertEqual(1, len(bills))
            self.assertEqual(UtilBill.Complete, bills[0].state)
            self.assertEqual(date(2012,1,1), bills[0].period_start)
            self.assertEqual(date(2012,2,1), bills[0].period_end)
            self.assertFalse(bills[0].processed)

            # check that "metadata" of the document in Mongo match MySQL
            doc1 = self.reebill_dao.load_doc_for_utilbill(bills[0])
            self.assertEqual(account, doc1['account'])
            self.assertEqual('gas', doc1['service'])
            self.assertEqual('washgas', doc1['utility'])
            self.assertEqual('DC Non Residential Non Heat', doc1['rate_class'])
            self.assertEqual({
                "postal_code" : u"20910",
                "city" : u"Silver Spring",
                "state" : u"MD",
                "addressee" : u"Managing Member Monroe Towers",
                "street" : u"3501 13TH ST NW LLC"
            }, doc1['billing_address'])
            self.assertEqual({
                u"postal_code" : u"20010",
                u"city" : u"Washington",
                u"state" : u"DC",
                u"addressee" : u"Monroe Towers",
                u"street" : u"3501 13TH ST NW #WH"
            }, doc1['service_address'])
            self.assertEqual(date(2012,1,1), doc1['start'])
            self.assertEqual(date(2012,2,1), doc1['end'])
            self.assertEqual(1, len(doc1['meters']))
            self.assertEqual(date(2012,1,1),
                    doc1['meters'][0]['prior_read_date'])
            self.assertEqual(date(2012,2,1),
                    doc1['meters'][0]['present_read_date'])
            self.assertEqual([0], [r['quantity'] for r in
                    doc1['meters'][0]['registers']])

            # second contiguous bill (explicitly specifying utility/rate class)
            file2 = StringIO("Let's pretend this is a PDF")
            self.process.upload_utility_bill(session, account, service,
                    date(2012,2,1), date(2012,3,1), file2, 'february.pdf',
                    utility='washgas',
                    rate_class='DC Non Residential Non Heat')
            bills = self.state_db.list_utilbills(session,
                    account)[0].filter(UtilBill.service==service).all()
            bills = [a for a in reversed(bills)]
            self.assertEqual(2, len(bills))
            self.assertEqual(UtilBill.Complete, bills[0].state)
            self.assertEqual(date(2012,1,1), bills[0].period_start)
            self.assertEqual(date(2012,2,1), bills[0].period_end)
            self.assertEqual(UtilBill.Complete, bills[1].state)
            self.assertEqual(date(2012,2,1), bills[1].period_start)
            self.assertEqual(date(2012,3,1), bills[1].period_end)
            doc2 = self.reebill_dao.load_doc_for_utilbill(bills[1])
            self.assertEquals(doc1['billing_address'],
                    doc2['billing_address'])
            self.assertEquals(doc1['service_address'],
                    doc2['service_address'])

            # 3rd bill "Skyline estimated", without a file
            self.process.upload_utility_bill(session, account, service,
                    date(2012,3,1), date(2012,4,1), None, None,
                    state=UtilBill.SkylineEstimated)
            bills = self.state_db.list_utilbills(session,
                    account)[0].filter(UtilBill.service==service).all()
            bills = [a for a in reversed(bills)]
            self.assertEqual(3, len(bills))
            self.assertEqual(UtilBill.Complete, bills[0].state)
            self.assertEqual(date(2012,1,1), bills[0].period_start)
            self.assertEqual(date(2012,2,1), bills[0].period_end)
            self.assertEqual(UtilBill.Complete, bills[1].state)
            self.assertEqual(date(2012,2,1), bills[1].period_start)
            self.assertEqual(date(2012,3,1), bills[1].period_end)
            self.assertEqual(UtilBill.SkylineEstimated, bills[2].state)
            self.assertEqual(date(2012,3,1), bills[2].period_start)
            self.assertEqual(date(2012,4,1), bills[2].period_end)

            # 4th bill without a gap between it and the 3rd bill: hypothetical
            # bills should be inserted
            file4 = StringIO("File of the July bill.")
            self.process.upload_utility_bill(session, account, service,
                     date(2012,7,1), date(2012,8,1), file4, 'july.pdf')
            bills = self.state_db.list_utilbills(session,
                    account)[0].filter(UtilBill.service==service).all()
            bills = [a for a in reversed(bills)]
            self.assertEqual(UtilBill.Complete, bills[0].state)
            self.assertEqual(date(2012,1,1), bills[0].period_start)
            self.assertEqual(date(2012,2,1), bills[0].period_end)
            self.assertEqual(UtilBill.Complete, bills[1].state)
            self.assertEqual(date(2012,2,1), bills[1].period_start)
            self.assertEqual(date(2012,3,1), bills[1].period_end)
            self.assertEqual(UtilBill.SkylineEstimated, bills[2].state)
            self.assertEqual(date(2012,3,1), bills[2].period_start)
            self.assertEqual(date(2012,4,1), bills[2].period_end)

            # there should be at least 5 bills (it doesn't matter how many).
            # the hypothetical ones should be contiguous from the start of the
            # gap to the end.
            self.assertGreater(len(bills), 4)
            i = 3
            while bills[i].period_end <= date(2012,7,1):
                self.assertEqual(bills[i-1].period_end, bills[i].period_start)
                self.assertEqual(UtilBill.Hypothetical, bills[i].state)
                i += 1
            # Complete bill for July should be the last one
            self.assertEqual(len(bills)-1, i)
            self.assertEqual(date(2012,7,1), bills[i].period_start)
            self.assertEqual(date(2012,8,1), bills[i].period_end)
            self.assertEqual(UtilBill.Complete, bills[i].state)

            # change the utility and rate structure name of the last bill, to
            # ensure that that one is used as the "predecessor" to determine
            # these keys in the next bill
            last_bill = bills[-1]
            assert last_bill.period_start == date(2012,7,1)
            assert last_bill.period_end == date(2012,8,1)
            last_bill.utility = 'New Utility'
            last_bill.rate_class = 'New Rate Class'
            self.process.upload_utility_bill(session, account, service,
                    date(2012,8,1), date(2012,9,1), StringIO('whatever'),
                    'august.pdf')
            new_bill = session.query(UtilBill)\
                    .filter_by(period_start=date(2012,8,1)).one()
            self.assertEqual('New Utility', new_bill.utility)
            self.assertEqual('New Rate Class', new_bill.rate_class)

    def test_upload_new_service(self):
        '''Tests uploading first utility bill with different service, utility,
        rate_class from the template document for the account.'''
        with DBSession(self.state_db) as session:
            # account was created with the following values
            template_doc = self.reebill_dao.load_utilbill_template(session,
                    '99999')
            assert template_doc['service'] == 'gas'
            assert template_doc['utility'] == 'washgas'
            assert template_doc['rate_class'] == 'DC Non Residential Non Heat'

            self.process.upload_utility_bill(session, '99999', 'electric',
                    date(2013,1,1), date(2013,2,1), StringIO('a file'),
                    'january.pdf', utility='Pepco',
                    rate_class='Residential R Winter')

            bill = session.query(UtilBill).one()
            self.assertEqual('electric', bill.service)
            self.assertEqual('Pepco', bill.utility)
            self.assertEqual('Residential R Winter', bill.rate_class)
            doc = self.reebill_dao.load_doc_for_utilbill(bill)
            self.assertEqual('electric', doc['service'])
            self.assertEqual('Pepco', doc['utility'])
            self.assertEqual('Residential R Winter', doc['rate_class'])


    def test_delete_utility_bill(self):
        account = '99999'
        start, end = date(2012,1,1), date(2012,2,1)

        with DBSession(self.state_db) as session:
            # create utility bill in MySQL, Mongo, and filesystem (and make
            # sure it exists all 3 places)
            self.process.upload_utility_bill(session, account, 'gas',
                    start, end, StringIO("test"), 'january.pdf')
            assert self.state_db.list_utilbills(session, account)[1] == 1
            bill_file_path = self.billupload.get_utilbill_file_path(account,
                    start, end)
            assert os.access(bill_file_path, os.F_OK)
            customer = session.query(Customer)\
                    .filter(Customer.account == account).one()
            utilbill = session.query(UtilBill)\
                    .filter(UtilBill.customer_id == customer.id)\
                    .filter(UtilBill.period_start == start)\
                    .filter(UtilBill.period_end == end).one()
            self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
            self.rate_structure_dao.load_cprs_for_utilbill(utilbill)

            # with no reebills, deletion should succeed: row removed from
            # MySQL, document removed from Mongo (only template should be
            # left), UPRS and CPRS documents removed from Mongo, file moved to
            # trash directory
            new_path = self.process.delete_utility_bill(session, utilbill)
            self.assertEqual(0, self.state_db.list_utilbills(session, account)[1])
            self.assertEquals(1, len(self.reebill_dao.load_utilbills()))
            self.assertRaises(RateStructure.DoesNotExist,
                    self.rate_structure_dao.load_uprs_for_utilbill, utilbill)
            self.assertRaises(RateStructure.DoesNotExist,
                    self.rate_structure_dao.load_cprs_for_utilbill, utilbill)
            self.assertFalse(os.access(bill_file_path, os.F_OK))
            self.assertRaises(IOError, self.billupload.get_utilbill_file_path,
                    account, start, end)
            self.assertTrue(os.access(new_path, os.F_OK))

            # re-upload the bill
            self.process.upload_utility_bill(session, account, 'gas',
                    start, end, StringIO("test"), 'january-gas.pdf')
            assert self.state_db.list_utilbills(session, account)[1] == 1
            self.assertEquals(2, len(self.reebill_dao.load_utilbills()))
            bill_file_path = self.billupload.get_utilbill_file_path(account,
                    start, end)
            assert os.access(bill_file_path, os.F_OK)
            utilbill = session.query(UtilBill)\
                    .filter(UtilBill.customer_id == customer.id)\
                    .filter(UtilBill.period_start == start)\
                    .filter(UtilBill.period_end == end).one()
            
            # when utilbill is attached to reebill, deletion should fail
            self.process.create_first_reebill(session, utilbill)
            first_reebill = session.query(ReeBill).one()
            assert first_reebill.utilbills == [utilbill]
            assert utilbill.is_attached()
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill)

            # deletion should fail if any version of a reebill has an
            # association with the utility bill. so issue the reebill, add
            # another utility bill, and create a new version of the reebill
            # attached to that utility bill instead.
            self.process.issue(session, account, 1)
            self.process.new_version(session, account, 1)
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2012,2,1), date(2012,3,1), StringIO("test"),
                    'january-electric.pdf')
            other_utility_bill = self.state_db.get_utilbill(session, account,
                    'gas', date(2012,2,1), date(2012,3,1))
            new_version_reebill = self.state_db.get_reebill(session, account,
                    1, version=1)
            # TODO this may not accurately reflect the way reebills get
            # attached to different utility bills; see
            # https://www.pivotaltracker.com/story/show/51935657
            new_version_reebill._utilbills = [other_utility_bill]
            new_version_reebill_doc = self.reebill_dao.load_reebill(account, 1,
                    version=1)
            other_utility_bill_doc = self.reebill_dao.load_doc_for_utilbill(
                    utilbill)
            new_version_reebill_doc._utilbills[0]['_id'] = other_utility_bill_doc['_id']
            self.reebill_dao.save_reebill(new_version_reebill_doc)
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill)
            session.commit()

            # test deletion of a Skyline-estimated utility bill (no file)
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,3,1), date(2013,4,1), None, 'no file name',
                    state=UtilBill.SkylineEstimated)
            self.process.delete_utility_bill(session,
                    self.state_db.get_utilbill(session, account, 'gas',
                    date(2013,3,1), date(2013,4,1)))

            # test deletion of a Hypothetical utility bill (no file and no
            # Mongo document)
            self.process.upload_utility_bill(session, account, 'gas',
                     date(2013,3,1), date(2013,4,1), None, 'no file name',
                    state=UtilBill.Hypothetical)
            self.process.delete_utility_bill(session,
                    self.state_db.get_utilbill(session, account, 'gas',
                    date(2013,3,1), date(2013,4,1)))

            # test deletion of utility bill with non-standard file extension
            self.process.upload_utility_bill(session, account, 'gas',
                     date(2013,4,1), date(2013,5,1), StringIO("a bill"),
                     'billfile.abcdef')
            the_path = self.billupload.get_utilbill_file_path(account,
                    date(2013,4,1), date(2013,5,1))
            assert os.access(the_path, os.F_OK)
            self.process.delete_utility_bill(session,
                    self.state_db.get_utilbill(session, account, 'gas',
                    date(2013,4,1), date(2013,5,1)))
            self.assertFalse(os.access(os.path.splitext(the_path)[0] + 'abcdef', os.F_OK))

            # test deletion of utility bill with no file extension
            self.process.upload_utility_bill(session, account, 'gas',
                     date(2013,2,1), date(2013,3,1), StringIO("a bill"),
                     'billwithnoextension')
            the_path = self.billupload.get_utilbill_file_path(account,
                    date(2013,2,1), date(2013,3,1))
            assert os.access(the_path, os.F_OK)
            self.process.delete_utility_bill(session,
                    self.state_db.get_utilbill(session, account, 'gas',
                    date(2013,2,1), date(2013,3,1)))
            self.assertFalse(os.access(the_path, os.F_OK))

    def test_new_version(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            # create utility bill and reebill
            self.process.upload_utility_bill(session, acc, 'gas',
                     date(2012,1,1), date(2012,2,1), StringIO('january 2012'),
                     'january.pdf')
            self.process.create_first_reebill(session,
                    session.query(UtilBill).one())

            # TODO creating new version of reebill should fail until it's
            # issued

            # there should be two utility bill documents: the account's
            # template, an an editable utility bill attached to the current
            # reebill
            utilbill = session.query(UtilBill).one()
            all_utilbill_docs = self.reebill_dao.load_utilbills()
            self.assertEquals(2, len(all_utilbill_docs))
            self.assertIn(ObjectId(utilbill.customer.utilbill_template_id),
                    [d['_id'] for d in all_utilbill_docs])
            editable_utilbill_doc = next(doc for doc in all_utilbill_docs
                    if doc['_id'] == ObjectId(utilbill.document_id))
            self.assertNotIn('sequence', editable_utilbill_doc)
            self.assertNotIn('version', editable_utilbill_doc)
            self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
            self.rate_structure_dao.load_cprs_for_utilbill(utilbill)

            # reebill should be associated with the utility bill via
            # utilbill_reebill, and there is no frozen document id in the
            # utilbill_reebill table
            self.assertEquals(1, len(utilbill._utilbill_reebills))
            self.assertEquals(None, utilbill._utilbill_reebills[0].document_id)
            self.assertEquals(None,
                    utilbill._utilbill_reebills[0].uprs_document_id)
            self.assertEquals(None,
                    utilbill._utilbill_reebills[0].cprs_document_id)
            reebill = self.reebill_dao.load_reebill(acc, 1)
            self.assertEqual(1, len(reebill._utilbills))
            self.assertEqual(1, len(reebill.reebill_dict['utilbills']))
            self.assertEqual(ObjectId(utilbill.document_id),
                    reebill._utilbills[0]['_id'])
            self.assertEqual(reebill._utilbills[0]['_id'],
                    reebill.reebill_dict['utilbills'][0]['id'])

            # update the meter like the user normally would
            # "This is required for process.new_version =>
            # fetch_bill_data.fetch_oltp_data" (???)
            meter = reebill.meters_for_service('gas')[0]
            reebill.set_meter_read_date('gas', meter['identifier'], date(2012,2,1),
                    date(2012,1,1))
            self.reebill_dao.save_reebill(reebill)

            # issue reebill
            self.process.issue(session, acc, 1, issue_date=date(2012,1,15))

            # there should now be 3 utility bill documents: the template, an
            # editable document whose _id is the document_id of the utility
            # bill in MySQL, and a frozen one whose _id is the document_id in
            # the utilbill_reebill row associating the utility bill with the
            # reebill
            all_ids = [doc['_id'] for doc in self.reebill_dao.load_utilbills()]
            self.assertEquals(3, len(all_ids))
            self.assertIn(ObjectId(utilbill.customer.utilbill_template_id),
                    all_ids)
            self.assertIn(ObjectId(utilbill.document_id), all_ids)
            self.assertEquals(1, len(utilbill._utilbill_reebills))
            self.assertIn(ObjectId(utilbill._utilbill_reebills[0].document_id),
                    all_ids)

            reebill = session.query(ReeBill).one()
            reebill_doc = self.reebill_dao.load_reebill(acc, 1)
            self.assertEqual(1, len(reebill_doc._utilbills))
            self.assertEqual(1, len(reebill_doc.reebill_dict['utilbills']))
            self.assertEqual(
                    ObjectId(utilbill._utilbill_reebills[0].document_id),
                    reebill_doc._utilbills[0]['_id'])
            self.assertEqual(
                    ObjectId(utilbill._utilbill_reebills[0].document_id),
                    reebill_doc.reebill_dict['utilbills'][0]['id'])
            uprs = self.rate_structure_dao.load_uprs_for_utilbill(utilbill,
                    reebill=reebill)
            cprs = self.rate_structure_dao.load_cprs_for_utilbill(utilbill,
                    reebill=reebill)
            self.assertNotEqual(ObjectId(utilbill.uprs_document_id),
                    uprs.id)
            self.assertNotEqual(ObjectId(utilbill.cprs_document_id),
                    cprs.id)
            self.assertEqual(
                    ObjectId(utilbill._utilbill_reebills[0].uprs_document_id),
                    uprs.id)
            self.assertEqual(
                    ObjectId(utilbill._utilbill_reebills[0].cprs_document_id),
                    cprs.id)

            # modify editable utility bill document so its meter read dates are
            # different from both its period and the frozen document's meter read
            # dates. this lets us test that the new meter read dates are used,
            # rather than the period dates or the old meter read dates.
            # (regression test for bug 46127315)
            editable_utilbill = self.reebill_dao.load_utilbill(acc, 'gas',
                    'washgas', date(2012,1,1), date(2012,2,1), sequence=False,
                    version=False)
            editable_utilbill['meters'][0]['prior_read_date'] = date(2012,1,15)
            editable_utilbill['meters'][0]['present_read_date'] = date(2012,3,15)
            self.reebill_dao.save_utilbill(editable_utilbill)
            # find the expected total energy (produced by MockSplinter) if this
            # period is used. it is extremely unlikely to exactly match the total
            # energy that would be produced for a different period (especially
            # because the length is different).
            correct_energy_amount_therms = sum([hour_of_energy(h) for h in
                    cross_range(datetime(2012,1,15), datetime(2012,3,15))]) / 1e5

            # create new version of 1
            new_reebill_doc = self.process.new_version(session, acc, 1)
            new_reebill = self.state_db.get_reebill(session, acc, 1, version=1)

            # basic facts about new version
            self.assertEqual(acc, new_reebill_doc.account)
            self.assertEqual(1, new_reebill_doc.sequence)
            self.assertEqual(1, new_reebill_doc.version)
            self.assertEqual(1, self.state_db.max_version(session, acc, 1))

            # the editable utility bill with the new meter read period should be used
            self.assertEqual((date(2012,1,15), date(2012,3,15)),
                    new_reebill_doc.meter_read_dates_for_service('gas'))

            for utilbill in new_reebill.utilbills:
                # utility bill document, UPRS document, CPRS document, and combined
                # rate structure object should be the same as the "current" ones
                # belonging to the utility bill itself...
                current_utilbill = self.reebill_dao.load_doc_for_utilbill(
                        utilbill)
                current_uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                        utilbill, reebill=new_reebill)
                current_cprs = self.rate_structure_dao.load_cprs_for_utilbill(
                        utilbill, reebill=new_reebill)
                reebill_utilbill = self.reebill_dao.load_doc_for_utilbill(
                        utilbill, reebill=new_reebill)
                reebill_uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                        utilbill, reebill=new_reebill)
                reebill_cprs = self.rate_structure_dao.load_cprs_for_utilbill(
                        utilbill, reebill=new_reebill)
                self.assertEquals(current_uprs, reebill_uprs)
                self.assertEquals(current_cprs, reebill_cprs)
                #self.assertEquals(current_combined_rs, reebill_combined_rs)

                # ...and should not match the frozen ones that were in the previous
                # version (at least _ids should be different)
                original_reebill = self.state_db.get_reebill(session, acc, 1,
                        version=0)
                frozen_utilbill = self.reebill_dao.load_doc_for_utilbill(
                        utilbill, reebill=original_reebill)
                frozen_uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                        utilbill, reebill=original_reebill)
                frozen_cprs = self.rate_structure_dao.load_cprs_for_utilbill(
                        utilbill, reebill=original_reebill)
                self.assertNotEqual(frozen_utilbill, reebill_utilbill)
                self.assertNotEqual(frozen_uprs, reebill_uprs)
                self.assertNotEqual(frozen_cprs, reebill_cprs)

            # if the total REE is 'correct_energy_amount_therms' (within
            # floating-point error), the correct meter read period was used.
            self.assertAlmostEqual(correct_energy_amount_therms,
                    float(new_reebill_doc.total_renewable_energy()))

    def test_correction_issuing(self):
        '''Tests get_unissued_corrections(), get_total_adjustment(), and
        issue_corrections().'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # reebills 1-4, 1-3 issued
            base_date = date(2012,1,1)
            dates = [base_date + timedelta(days=30*x) for x in xrange(5)]
            for n in xrange(4):
                self.process.upload_utility_bill(session, acc, 'gas',
                        dates[n], dates[n+1], StringIO('a utility bill'),
                        'filename.pdf')
            
            self.process.create_first_reebill(session, session.query(UtilBill)
                    .order_by(UtilBill.period_start).first())
            one = self.reebill_dao.load_reebill(acc, 1)
            one.ree_charges = 100
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, 1)
            one = self.reebill_dao.load_reebill(acc, one.sequence)

            self.process.create_next_reebill(session, acc)
            two = self.reebill_dao.load_reebill(acc, 2)
            two.ree_charges = 100
            self.reebill_dao.save_reebill(two)
            self.process.issue(session, acc, two.sequence)
            two = self.reebill_dao.load_reebill(acc, two.sequence)

            self.process.create_next_reebill(session, acc)
            three = self.reebill_dao.load_reebill(acc, 3)
            three.ree_charges = 100
            self.reebill_dao.save_reebill(three)
            self.process.issue(session, acc, three.sequence)
            three = self.reebill_dao.load_reebill(acc, three.sequence)

            self.process.create_next_reebill(session, acc)
            four = self.reebill_dao.load_reebill(acc, 4)
            four.ree_charges = 100
            self.reebill_dao.save_reebill(four)

            # no unissued corrections yet
            self.assertEquals([],
                    self.process.get_unissued_corrections(session, acc))
            self.assertEquals(0, self.process.get_total_adjustment(session, acc))

            # try to issue nonexistent corrections
            self.assertRaises(ValueError, self.process.issue_corrections,
                    session, acc, 4)

            # make corrections on 1 and 3
            # (new_version() changes the REE, but setting ree_charges,
            # explicitly overrides that)
            self.process.new_version(session, acc, 1)
            self.process.new_version(session, acc, 3)
            one_1 = self.reebill_dao.load_reebill(acc, 1, version=1)
            three_1 = self.reebill_dao.load_reebill(acc, 3, version=1)
            one_1.ree_charges = 120
            three_1.ree_charges = 95
            self.reebill_dao.save_reebill(one_1)
            self.reebill_dao.save_reebill(three_1)

            # there should be 2 adjustments: +$20 for 1-1, and -$5 for 3-1
            self.assertEqual([(1, 1, 20), (3, 1, -5)],
                    self.process.get_unissued_corrections(session, acc))
            self.assertEqual(15, self.process.get_total_adjustment(session, acc))

            # try to apply corrections to an issued bill
            self.assertRaises(ValueError, self.process.issue_corrections,
                    session, acc, 2)
            # try to apply corrections to a correction
            self.assertRaises(ValueError, self.process.issue_corrections,
                    session, acc, 3)

            # get original balance of reebill 4 before applying corrections
            four = self.reebill_dao.load_reebill(acc, 4)
            self.process.compute_reebill(session, four)
            four_original_balance = four.balance_due

            # apply corrections to un-issued reebill 4. reebill 4 should be
            # updated, and the corrections (1 & 3) should be issued
            self.process.issue_corrections(session, acc, 4)
            four = self.reebill_dao.load_reebill(acc, 4)
            self.process.compute_reebill(session, four)
            # for some reason, adjustment is part of "balance forward"
            # https://www.pivotaltracker.com/story/show/32754231
            self.assertEqual(four.prior_balance - four.payment_received +
                    four.total_adjustment, four.balance_forward)
            self.assertEquals(four.balance_forward + four.total, four.balance_due)
            self.assertTrue(self.state_db.is_issued(session, acc, 1))
            self.assertTrue(self.state_db.is_issued(session, acc, 3))
            self.assertEqual([], self.process.get_unissued_corrections(session,
                    acc))

            session.commit()

    def test_late_charge_correction(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            # 2 utility bills
            self.process.upload_utility_bill(session, acc, 'gas',
                     date(2012,1,1), date(2012,2,1), StringIO('January 2012'),
                     'january.pdf')
            self.process.upload_utility_bill(session, acc, 'gas',
                     date(2012,2,1), date(2012,3,1), StringIO('February 2012'),
                     'february.pdf')

            # 1st reebill, with a balance of 100, issued 40 days ago and unpaid
            # (so it's 10 days late)
            self.process.create_first_reebill(session, session.query(UtilBill)
                    .order_by(UtilBill.period_start).first())
            one = self.reebill_dao.load_reebill(acc, 1)
            one.balance_due = 100
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, 1,
                    issue_date=datetime.utcnow().date() - timedelta(40))
            
            # 2nd reebill, which will get a late charge from the 1st
            self.process.create_next_reebill(session, acc)

            # "bind REE" in 2nd reebill
            # (it needs energy data only so its correction will have the same
            # energy in it as the original version; only the late charge will
            # differ)
            two = self.reebill_dao.load_reebill(acc, 2)
            fbd.fetch_oltp_data(self.splinter, self.nexus_util.olap_id(acc),
                    two)

            # if given a late_charge_rate > 0, 2nd reebill should have a late charge
            two.late_charge_rate = .5
            self.process.compute_reebill(session, two)
            self.assertEqual(50, two.late_charges)

            # save and issue 2nd reebill so a new version can be created
            self.reebill_dao.save_reebill(two)
            self.process.issue(session, acc, two.sequence)

            # add a payment of $80 30 days ago (10 days after 1st reebill was
            # issued). the late fee above is now wrong; it should be 50% of $20
            # instead of 50% of the entire $100.
            self.state_db.create_payment(session, acc, datetime.utcnow().date()
                    - timedelta(30), 'backdated payment', 80)

            # now a new version of the 2nd reebill should have a different late
            # charge: $10 instead of $50.
            self.process.new_version(session, acc, 2)
            two_1 = self.reebill_dao.load_reebill(acc, 2)
            self.assertEqual(10, two_1.late_charges)

            # that difference should show up as an error
            corrections = self.process.get_unissued_corrections(session, acc)
            assert len(corrections) == 1
            self.assertEquals((2, 1, -40), corrections[0])

    # TODO rename
    def test_roll(self):
        '''Tests creation of reebills and dependency of each reebill on its
        predecessor.'''
        account = '99999'
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            # create 2 utility bills
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,4,4), date(2013,5,2), StringIO('April 2013'),
                    'april.pdf')
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,5,2), date(2013,6,3), StringIO('May 2013'),
                    'may.pdf')

            # create reebill based on first utility bill
            self.process.create_first_reebill(session,
                    session.query(UtilBill).order_by(UtilBill.period_start)
                    .first())

            # Make sure the reebill period matches the utility bill
            reebill_1 = self.reebill_dao.load_reebill(account, 1)
            self.assertEqual(reebill_1.period_begin, date(2013,4,4))
            self.assertEqual(reebill_1.period_end, date(2013,5,2))

            # reebill should be computable
            self.process.compute_reebill(session, reebill_1) 

            self.process.issue(session, account, 1)
            reebill_1 = self.reebill_dao.load_reebill(account, 1)

            # another reebill
            self.process.create_next_reebill(session, account)
            reebills = session.query(ReeBill).order_by(ReeBill.id).all()
            utilbills = session.query(UtilBill)\
                    .order_by(UtilBill.period_start).all()
            self.assertEquals([utilbills[0]], reebills[0].utilbills)
            self.assertEquals([utilbills[1]], reebills[1].utilbills)

            # addresses should be preserved from one reebill document to the
            # next
            reebill_doc_1 = self.reebill_dao.load_reebill(account, 1)
            reebill_doc_2 = self.reebill_dao.load_reebill(account, 2)
            self.assertEquals(reebill_doc_1.billing_address,
                    reebill_doc_2.billing_address)
            self.assertEquals(reebill_doc_1.service_address,
                    reebill_doc_2.service_address)

            # add two more utility bills: a Hypothetical one, then a Complete one
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,6,3), date(2013,7,1), None, 'no file',
                    state=UtilBill.Hypothetical)
            self.process.upload_utility_bill(session, account, 'gas',
                     date(2013,7,1), date(2013,7,30), StringIO('July 2013'),
                     'july.pdf')
            hypo_utilbill, later_utilbill = session.query(UtilBill)\
                    .order_by(UtilBill.period_start).all()[2:4]
            assert hypo_utilbill.state == UtilBill.Hypothetical
            assert later_utilbill.state == UtilBill.Complete

            # The next utility bill isn't estimated or final, so
            # create_next_reebill should fail
            self.assertRaises(NoSuchBillException,
                    self.process.create_next_reebill, session, account)

            # replace 'hypo_utilbill' with a UtilityEstimated one, so it has a
            # document and a reebill can be attached to it
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,6,3), date(2013,7,1), StringIO('June 2013'),
                    'june.pdf', state=UtilBill.UtilityEstimated)
            formerly_hypo_utilbill = session.query(UtilBill)\
                    .order_by(UtilBill.period_start).all()[2]
            assert formerly_hypo_utilbill.state == UtilBill.UtilityEstimated

            self.process.create_next_reebill(session, account)
            reebill_1 = self.reebill_dao.load_reebill(account, 1)
            self.process.create_next_reebill(session, account)
            reebill_2 = self.reebill_dao.load_reebill(account, 2)
            self.process.compute_reebill(session, reebill_2) 

            self.process.issue(session, account, reebill_2.sequence)
            reebill_2 = self.reebill_dao.load_reebill(account, reebill_2.sequence)

            # Shift later_utilbill a few days into the future so that there is
            # a time gap after the last attached utilbill
            later_utilbill.period_start += timedelta(days=5)
            later_utilbill.period_end += timedelta(days=5)
            later_utilbill = session.merge(later_utilbill)

            # can't create another reebill because there are no more utility
            # bills
            with self.assertRaises(NoSuchBillException) as context:
                self.process.create_next_reebill(session, account)

            # TODO: Test multiple services


    def test_roll_rs_prediction(self):
        '''Basic test of rate structure prediction when rolling bills.'''
        # TODO this test doesn't even need reebills; just create utility bills

        acc_a, acc_b, acc_c = 'aaaaa', 'bbbbb', 'ccccc'

        with DBSession(self.state_db) as session:
            # create customers A, B, and C, their utility bill template
            # documents, and reebills #0 for each (which include utility bills)
            customer_a = Customer('Customer A', acc_a, .12, .34,
                    '00000000000000000000000a')
            customer_b = Customer('Customer B', acc_b, .12, .34,
                    '00000000000000000000000b')
            customer_c = Customer('Customer C', acc_c, .12, .34,
                    '00000000000000000000000c')
            session.add_all([customer_a, customer_b, customer_c])
            template_a = example_data.get_utilbill_dict(acc_a,
                    start=date(1900,1,1,), end=date(1900,2,1))
            template_b = example_data.get_utilbill_dict(acc_b,
                    start=date(1900,1,1,), end=date(1900,2,1))
            template_c = example_data.get_utilbill_dict(acc_c,
                    start=date(1900,1,1,), end=date(1900,2,1))
            template_a['_id'] = ObjectId('00000000000000000000000a')
            template_b['_id'] = ObjectId('00000000000000000000000b')
            template_c['_id'] = ObjectId('00000000000000000000000c')
            self.reebill_dao.save_utilbill(template_a)
            self.reebill_dao.save_utilbill(template_b)
            self.reebill_dao.save_utilbill(template_c)
            reebill_a_0 = example_data.get_reebill(acc_a, 0,
                    start=date(2012,12,1), end=date(2013,1,1))
            reebill_b_0 = example_data.get_reebill(acc_b, 0,
                    start=date(2012,12,1), end=date(2013,1,1))
            reebill_c_0 = example_data.get_reebill(acc_c, 0,
                    start=date(2012,12,1), end=date(2013,1,1))
            self.reebill_dao.save_reebill(reebill_a_0, freeze_utilbills=True)
            self.reebill_dao.save_reebill(reebill_b_0, freeze_utilbills=True)
            self.reebill_dao.save_reebill(reebill_c_0, freeze_utilbills=True)
            # new customers also need to be in nexus for 'fetch_oltp_data' to
            # work (using mock Skyliner)
            self.nexus_util._customers.extend([
                {
                    'billing': 'aaaaa',
                    'olap': 'a-1',
                    'casualname': 'Customer A',
                    'primus': '1 A St.',
                },
                {
                    'billing': 'bbbbb',
                    'olap': 'b-1',
                    'casualname': 'Customer B',
                    'primus': '1 B St.',
                },
                {
                    'billing': 'ccccc',
                    'olap': 'c-1',
                    'casualname': 'Customer C',
                    'primus': '1 C St.',
                },
            ])

            # create utility bills and reebill #1 for all 3 accounts
            # (note that period dates are not exactly aligned)
            utilbill_a = self.process.upload_utility_bill(session, acc_a, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013 A'),
                    'january-a.pdf', total=0, state=UtilBill.Complete)
            utilbill_b = self.process.upload_utility_bill(session, acc_b, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013 B'),
                    'january-b.pdf', total=0, state=UtilBill.Complete)
            utilbill_c = self.process.upload_utility_bill(session, acc_c, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013 C'),
                    'january-c.pdf', total=0, state=UtilBill.Complete)
            self.process.create_first_reebill(session, utilbill_a)
            self.process.create_first_reebill(session, utilbill_b)
            self.process.create_first_reebill(session, utilbill_c)

            # UPRSs of all 3 reebills will be empty, because sequence-0
            # rebills' utility bills' UPRSs are ignored when generating
            # predicted UPRSs. so, insert some RSIs into them. A gets only one
            # RSI, SYSTEM_CHARGE, while B and C get two others,
            # DISTRIBUTION_CHARGE and PGC.
            uprs_a = self.rate_structure_dao.load_uprs_for_utilbill(
                    session.query(UtilBill).filter_by(customer=customer_a)
                    .one())
            uprs_b = self.rate_structure_dao.load_uprs_for_utilbill(
                    session.query(UtilBill).filter_by(customer=customer_b)
                    .one())
            uprs_c = self.rate_structure_dao.load_uprs_for_utilbill(
                    session.query(UtilBill).filter_by(customer=customer_c)
                    .one())
            uprs_a.rates = [
                RateStructureItem(
                    rsi_binding='SYSTEM_CHARGE',
                    description='System Charge',
                    quantity='1',
                    #rate_units='dollars',
                    processingnote='',
                    rate='11.2',
                    uuid="c9733cca-2c16-11e1-8c7f-002421e88ffb",
                )
            ]
            uprs_b.rates = uprs_c.rates = [
                RateStructureItem(
                    rsi_binding='DISTRIBUTION_CHARGE',
                    description='Distribution charge for all therms',
                    quantity='750.10197727',
                    #rate_units='dollars',
                    processingnote='',
                    rate='0.2935',
                    quantity_units='therms',
                    total='220.16',
                    uuid='c9733ed2-2c16-11e1-8c7f-002421e88ffb'
                ),
                RateStructureItem(
                    rsi_binding='PGC',
                    description='Purchased Gas Charge',
                    quantity='750.10197727',
                    #rate_units='dollars',
                    processingnote='',
                    rate='0.7653',
                    quantity_units='therms',
                    total='574.05',
                    uuid='c97340da-2c16-11e1-8c7f-002421e88ffb'
                ),
            ]
            uprs_a.save(); uprs_b.save(); uprs_c.save()

            # create utility bill and reebill #2 for A
            utilbill_a_2 = self.process.upload_utility_bill(session, acc_a,
                    'gas', date(2013,2,1), date(2013,3,1),
                     StringIO('February 2013 A'), 'february-a.pdf', total=0,
                     state=UtilBill.Complete)
            self.process.create_next_reebill(session, acc_a)

            # initially there will be no RSIs in A's 2nd utility bill, because
            # there are no "processed" utility bills yet.
            uprs_a_2 = self.rate_structure_dao.load_uprs_for_utilbill(
                    session.query(UtilBill).filter_by(customer=customer_a,
                    period_start=date(2013,2,1)).one())
            self.assertEqual([], uprs_a_2.rates)

            # when the other bills have been marked as "procesed", they should
            # affect the new one.
            utilbill_a.processed = True
            utilbill_b.processed = True
            utilbill_c.processed = True
            self.process.regenerate_uprs(session, utilbill_a_2.id)

            # the UPRS of A's reebill #2 should now match B and C, i.e. it
            # should contain DISTRIBUTION and PGC and exclude SYSTEM_CHARGE,
            # because together the other two have greater weight than A's
            # reebill #1
            uprs_a_2 = self.rate_structure_dao.load_uprs_for_utilbill(
                    session.query(UtilBill).filter_by(customer=customer_a,
                    period_start=date(2013,2,1)).one())
            self.assertEqual(set(['DISTRIBUTION_CHARGE', 'PGC']),
                    set(rsi.rsi_binding for rsi in uprs_a_2.rates))

            # make sure A's reebill #2 is computable after rolling (even though
            # RSIs have changed, meaning some of the original charges may not
            # have corresponding RSIs and had to be removed)
            reebill_a_1 = self.reebill_dao.load_reebill(acc_a, 1)
            reebill_a_2 = self.reebill_dao.load_reebill(acc_a, 2)
            self.process.compute_reebill(session, reebill_a_2) 

            # now, modify A-2's UPRS so it differs from both A-1 and B/C-1. if
            # a new bill is rolled, the UPRS it gets depends on whether it's
            # closer to B/C-1 or to A-2.
            uprs_a_2.rates = [RateStructureItem(
                rsi_binding='RIGHT_OF_WAY',
                description='DC Rights-of-Way Fee',
                quantity='750.10197727',
                #rate_units='dollars',
                processingnote='',
                rate='0.03059',
                quantity_units='therms',
                total='22.95',
                uuid='c97344f4-2c16-11e1-8c7f-002421e88ffb'
            )]
            uprs_a_2.save()

            # roll B-2 with period 2-5 to 3-5, closer to A-2 than B-1 and C-1.
            # the latter are more numerous, but A-1 should outweigh them
            # because weight decreases quickly with distance.
            self.process.upload_utility_bill(session, acc_b, 'gas',
                     date(2013,2,5), date(2013,3,5),
                     StringIO('February 2013 B'),
                    'february-b.pdf', total=0, state=UtilBill.Complete)
            self.process.create_next_reebill(session, acc_b)
            uprs_b_2 = self.rate_structure_dao.load_uprs_for_utilbill(
                    session.query(UtilBill).filter_by(customer=customer_b,
                    period_start=date(2013,2,5)).one())
            self.assertEqual(set(['RIGHT_OF_WAY']),
                    set(rsi.rsi_binding for rsi in uprs_a_2.rates))

            # https://www.pivotaltracker.com/story/show/47134189
            ## B-2 and its utility bill should not contain any charges that
            ## don't correspond to the rate structure.
            #actual_charge_names = [c['rsi_binding'] for c in reebill_b_2\
                    #._get_utilbill_for_service('gas')['chargegroups']
                    #['All Charges']]
            #hyp_charge_names = [c['rsi_binding'] for c in reebill_b_2\
                    #._get_handle_for_service('gas')\
                    #['hypothetical_chargegroups']['All Charges']]

    def test_rs_prediction_processed(self):
        '''Tests that rate structure prediction includes all and only utility
        bills that are "processed". '''

    def test_issue(self):
        '''Tests issuing of reebills.'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # two utilbills, with reebills
            self.process.upload_utility_bill(session, acc, 'gas',
                     date(2012,1,1), date(2012,2,1), StringIO('january 2012'),
                     'january.pdf')
            self.process.upload_utility_bill(session, acc, 'gas',
                     date(2012,2,1), date(2012,3,1), StringIO('february 2012'),
                     'february.pdf')
            self.process.create_first_reebill(session, session.query(UtilBill)
                    .order_by(UtilBill.period_start).first())
            self.process.create_next_reebill(session, acc)
            one = self.state_db.get_reebill(session, acc, 1)
            one_doc = self.reebill_dao.load_reebill(acc, 1)
            two = self.state_db.get_reebill(session, acc, 2)
            two_doc = self.reebill_dao.load_reebill(acc, 2)
            utilbills = session.query(UtilBill).order_by(UtilBill.period_start).all()

            # neither reebill should be issued yet
            self.assertEquals(False, self.state_db.is_issued(session, acc, 1))
            self.assertEquals(None, one.issue_date)
            self.assertEquals(None, one_doc.due_date)

            # two should not be issuable until one_doc is issued
            self.assertRaises(BillStateError, self.process.issue, session, acc, 2)

            # issue one
            self.process.issue(session, acc, 1)

            # re-load from mongo to see updated issue date and due date
            one_doc = self.reebill_dao.load_reebill(acc, 1)
            self.assertEquals(True, one.issued)
            self.assertEquals(True, self.state_db.is_issued(session, acc, 1))
            self.assertEquals(datetime.utcnow().date(), one.issue_date)
            self.assertEquals(one.issue_date + timedelta(30), one_doc.due_date)
            self.assertIsInstance(one_doc.bill_recipients, list)
            self.assertEquals(len(one_doc.bill_recipients), 0)
            self.assertIsInstance(one_doc.last_recipients, list)
            self.assertEquals(len(one_doc.last_recipients), 0)

            two_doc.bill_recipients = ['test1@reebill.us', 'test2@reebill.us']
            self.reebill_dao.save_reebill(two_doc)
            
            # issue two
            self.process.issue(session, acc, 2)

            # re-load from mongo to see updated issue date and due date
            two_doc = self.reebill_dao.load_reebill(acc, 2)
            self.assertEquals(True, self.state_db.is_issued(session, acc, 2))
            self.assertEquals(datetime.utcnow().date(), two.issue_date)
            self.assertEquals(two.issue_date + timedelta(30), two_doc.due_date)
            self.assertIsInstance(two_doc.bill_recipients, list)
            self.assertEquals(len(two_doc.bill_recipients), 2)
            self.assertEquals(True, all(map(isinstance, two_doc.bill_recipients,
                    [unicode]*len(two_doc.bill_recipients))))

    def test_delete_reebill(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            # create utility bill and first reebill, for January 2012
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2012,1,1), date(2012,2,1), StringIO('january 2012'),
                    'january.pdf')
            utilbill = session.query(UtilBill).one()
            self.process.create_first_reebill(session, utilbill)
            reebill = session.query(ReeBill).one()

            # delete the reebill: should succeed, because it's not issued
            self.process.delete_reebill(session, reebill)
            self.assertRaises(NoSuchBillException,
                    self.reebill_dao.load_reebill, account, 1, version=0)
            self.assertEquals([], session.query(ReeBill).all())
            self.assertEquals([utilbill], session.query(UtilBill).all())

            # re-create it
            self.process.create_first_reebill(session, utilbill)
            reebill = session.query(ReeBill).one()
            self.assertEquals([1], self.state_db.listSequences(session,
                    account))
            self.assertEquals([utilbill], reebill.utilbills)
            
            # issue it: it should not be deletable
            self.process.issue(session, account, 1)
            self.assertEqual(1, reebill.issued)
            self.assertEqual([utilbill], reebill.utilbills)
            self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)
            b = self.reebill_dao.load_reebill(account, 1, version=0)
            self.assertRaises(IssuedBillError, self.process.delete_reebill,
                    session, reebill)

            # create a new verison and delete it, returning to just version 0
            # (versioning requires a cprs)
            self.process.new_version(session, account, 1)
            reebill_v1 = session.query(ReeBill).filter_by(version=1).one()
            self.assertEqual(1, self.state_db.max_version(session, account, 1))
            self.assertFalse(self.state_db.is_issued(session, account, 1))
            self.process.delete_reebill(session, reebill_v1)
            self.assertEqual(0, self.state_db.max_version(session, account, 1))
            self.assertTrue(self.state_db.is_issued(session, account, 1))

            # original version should still be attached to utility bill
            # TODO this will have to change. see
            # https://www.pivotaltracker.com/story/show/31629749
            utilbills = self.state_db.list_utilbills(session, account)[0].all()
            self.assertEqual([utilbill], reebill.utilbills)
            self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)


    def test_adjustment(self):
        '''Tests that adjustment from a correction is applied to (only) the
        earliest unissued bill.'''
        acc = '99999'

        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, acc)
            
            # create 3 utility bills: Jan, Feb, Mar
            utilbill_ids, uprs_ids, cprs_ids = [], [], []
            for i in range(3):
                self.process.upload_utility_bill(session, acc, 'gas',
                        date(2012, i+1, 1), date(2012, i+2, 1),
                        StringIO('a utility bill'), 'filename.pdf')
            
            # create 1st reebill and issue it
            self.process.create_first_reebill(session, session.query(UtilBill)
                    .order_by(UtilBill.period_start).first())
            self.process.issue(session, acc, 1)

            # create 2nd reebill
            self.process.create_next_reebill(session, acc)

            # make a correction on reebill #1, producing an adjustment of 100
            one = self.reebill_dao.load_reebill(acc, 1)
            one_corrected = self.process.new_version(session, acc, 1)
            one_corrected.ree_charges = one.ree_charges + 100
            # this change must be saved in Mongo, because compute_reebill() ->
            # get_unissued_corrections() loads the original and corrected bills
            # from Mongo and compares them to calculate the adjustment
            self.reebill_dao.save_reebill(one_corrected)

            two = self.reebill_dao.load_reebill(acc, 2)
            self.process.compute_reebill(session, two)

            # only 'two' should get an adjustment; 'one' is a correction, so it
            # can't have adjustments
            self.assertEquals(0, one.total_adjustment)
            self.assertEquals(100, two.total_adjustment)


    def test_payment_application(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), StringIO('january 2012'),
                    'january.pdf')
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2012,2,1), date(2012,3,1), StringIO('february 2012'),
                    'february.pdf')

            # create and issue reebill #1
            self.process.create_first_reebill(session, session.query(UtilBill)
                    .order_by(UtilBill.period_start).first())
            one_doc = self.reebill_dao.load_reebill(acc, 1)
            self.process.issue(session, acc, 1, issue_date=date(2012,1,15))

            # create reebill reebill #2
            self.process.create_next_reebill(session, acc)
            two_doc = self.reebill_dao.load_reebill(acc, 2)

            # payment on jan. 20 gets applied to #2
            self.state_db.create_payment(session, acc, date(2012,1,20), 'A payment', 123.45)
            self.process.compute_reebill(session, two_doc)
            self.reebill_dao.save_reebill(two_doc)
            self.assertEqual(123.45, two_doc.payment_received)

            # make a correction on reebill #1: payment does not get applied to
            # #1 and does get applied to #2
            self.process.new_version(session, acc, 1)
            one_doc = self.reebill_dao.load_reebill(acc, 1, version=1)
            self.process.compute_reebill(session, one_doc)
            self.process.compute_reebill(session, two_doc)
            self.assertEqual(0, one_doc.payment_received)
            self.assertEqual(123.45, two_doc.payment_received)


    def test_bind_and_compute_consistency(self):
        '''Tests that repeated binding and computing of a reebill do not
        cause it to change (a bug we have seen).'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # create utility bill for January
            # the UPRS for this utility bill will be empty, because there are
            # no other utility bills in the db, and the bill will have no
            # charges; all the charges in the template bill get removed because
            # the rate structure has no RSIs in it. so, add RSIs and charges
            # corresponding to them from example_data. (this is the same way
            # the user would manually add RSIs and charges when processing the
            # first bill for a given rate structure.)
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), StringIO('January 2012'),
                    'january.pdf')
            utilbill_jan = session.query(UtilBill).one()
            uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                    utilbill_jan)
            uprs.rates = example_data.get_uprs().rates
            utilbill_jan_doc = self.reebill_dao.load_doc_for_utilbill(
                    utilbill_jan)
            utilbill_jan_doc['chargegroups'] = example_data.get_utilbill_dict(
                    '99999')['chargegroups']
            uprs.save()
            self.reebill_dao.save_utilbill(utilbill_jan_doc)


            # create utility bill for February. thie UPRS and charges will be
            # the same as the one for January.
            self.process.upload_utility_bill(session, acc, 'gas',
                     date(2012,2,1), date(2012,3,1), StringIO('February 2012'),
                     'february.pdf')
            utilbill_feb = session.query(UtilBill)\
                    .order_by(desc(UtilBill.period_start)).first()

            # create a reebill for each utility bill. #2 will be computed
            # repeatedly and #1 will serve as its predecessor when computing
            # below.
            self.process.create_first_reebill(session, utilbill_jan)
            reebill1 = self.reebill_dao.load_reebill(acc, 1)
            self.process.create_next_reebill(session, acc)

            for use_olap in True, False:
                reebill2 = self.reebill_dao.load_reebill(acc, 2)
                # NOTE changes to 'reebill2' do not persist in db

                # bind & compute once to start. this change should be
                # idempotent.
                olap_id = 'MockSplinter ignores olap id'
                fbd.fetch_oltp_data(self.splinter, olap_id, reebill2,
                        use_olap=use_olap)
                ree1 = reebill2.total_renewable_energy()
                self.process.compute_utility_bill(session, utilbill_feb.id)
                self.process.compute_reebill(session, reebill2)

                # check that total renewable enrgy quantity has not been
                # changed by computing the bill for the first time (this
                # happened in bug #60548728)
                ree = reebill2.total_renewable_energy()
                self.assertEqual(ree1, ree)

                # save other values that will be checked repeatedly
                # (more fields could be added here)
                hypo = reebill2.hypothetical_total
                actual = reebill2.actual_total
                ree_value = reebill2.ree_value
                ree_charges = reebill2.ree_charges
                total = reebill2.total
                balance_due = reebill2.balance_due

                # this function checks that current values match the orignals
                def check():
                    # re-load reebill document from database because
                    # compute_utility_bill loads it, updates it, and saves it
                    # without affecting the document already loaded into memory
                    reebill2 = self.reebill_dao.load_reebill(acc, 2)
                    # in approximate "causal" order
                    self.assertAlmostEqual(ree,
                            reebill2.total_renewable_energy())
                    self.assertAlmostEqual(actual, reebill2.actual_total)
                    self.assertAlmostEqual(hypo, reebill2.hypothetical_total)
                    self.assertAlmostEqual(ree_value, reebill2.ree_value)
                    self.assertAlmostEqual(ree_charges, reebill2.ree_charges)
                    self.assertAlmostEqual(total, reebill2.total)
                    self.assertAlmostEqual(balance_due, reebill2.balance_due)

                # this better succeed, since nothing was done
                check()

                # bind and compute repeatedly
                self.process.compute_reebill(session, reebill2)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, reebill2,
                        use_olap=use_olap)
                check()
                self.process.compute_reebill(session, reebill2)
                check()
                self.process.compute_reebill(session, reebill2)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, reebill2,
                        use_olap=use_olap)
                fbd.fetch_oltp_data(self.splinter, olap_id, reebill2,
                        use_olap=use_olap)
                fbd.fetch_oltp_data(self.splinter, olap_id, reebill2,
                        use_olap=use_olap)
                check()
                self.process.compute_reebill(session, reebill2)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, reebill2,
                        use_olap=use_olap)
                check()
                self.process.compute_reebill(session, reebill2)
                check()

    def test_choose_next_utilbills_bug(self):
        '''Regression test for
        https://www.pivotaltracker.com/story/show/48430769.
        (I'm not sure if this test has any value now that choose_next_utilbills
        is not used and first reebill is created by specifying a particular
        utility bill rather than a date.--DK)'''
        account = '99999'
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            # add 2 utility bills
            self.process.upload_utility_bill(session, '99999', 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf')
            self.process.upload_utility_bill(session, '99999', 'gas',
                    date(2013,2,1), date(2013,3,1), StringIO('February 2013'),
                    'february.pdf')
            u1, u2 = session.query(UtilBill).order_by(UtilBill.period_start)\
                    .all()

            self.process.create_first_reebill(session, u1)
            r1 = self.reebill_dao.load_reebill(account, 1)

        # only u1 should be attached to the reebill
        reebill = session.query(ReeBill).one()
        self.assertEqual([u1], reebill.utilbills)
        self.assertEqual([reebill], [ur.reebill for ur in u1._utilbill_reebills])
        self.assertEqual([], [ur.reebill for ur in u2._utilbill_reebills])

    @unittest.skip("OTBE")
    def test_create_new_utility_bill(self):
        '''Tests the method Process.create_new_utility_bill. Since this is no
        longer used by itself, maybe it should become private and not have a
        test (but the checks of document contents should be moved into another
        test).'''
        with DBSession(self.state_db) as session:
            utilbill_template = self.reebill_dao.load_utilbill_template(session,
                    '99999')

            self.process.create_new_utility_bill(session, '99999', 'washgas',
                    'gas', 'DC Non Residential Non Heat', date(2013,1,1),
                    date(2013,2,1))

            # utility bill MySQL row and Mongo document should be created, and
            # the document's _id should match document_id in the MySQL row
            all_utilbills = session.query(UtilBill).all()
            self.assertEqual(1, len(all_utilbills))
            ub = all_utilbills[0]
            utilbill_doc = self.reebill_dao.load_doc_for_utilbill(ub)
            self.assertEqual(utilbill_doc['_id'], ObjectId(ub.document_id))

            # the utility bill document should look like the template, except
            # its _id should be different, it has different period dates, and
            # it will have no charges (all charges in the template get removed
            # because the UPRS and CPRS are empty)
            self.assertDocumentsEqualExceptKeys(utilbill_doc,
                    utilbill_template, '_id', 'start', 'end', 'chargegroups')
            self.assertNotEqual(utilbill_doc['_id'],
                    ObjectId(utilbill_template['_id']))
            self.assertEquals(date(2013,1,1), utilbill_doc['start'])
            self.assertEquals(date(2013,2,1), utilbill_doc['end'])
            self.assertEquals({'All Charges': []}, utilbill_doc['chargegroups'])

            # UPRS and CPRS documents should be created and be empty
            uprs = self.rate_structure_dao.load_uprs_for_utilbill(ub)
            cprs = self.rate_structure_dao.load_cprs_for_utilbill(ub)
            self.assertDocumentsEqualExceptKeys(uprs, {'type': 'UPRS',
                    'rates': []}, '_id')
            self.assertDocumentsEqualExceptKeys(cprs, {'type': 'CPRS',
                    'rates': []}, '_id')

            # utility bill row in MySQL should point to the UPRS and CPRS
            # documents
            self.assertEqual(uprs['_id'], ObjectId(ub.uprs_document_id))
            self.assertEqual(cprs['_id'], ObjectId(ub.cprs_document_id))

    def test_create_first_reebill(self):
        '''Tests Process.create_first_reebill which creates the first reebill
        (in MySQL and Mongo) attached to a particular utility bill, using the
        account's utility bill document template.'''
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, '99999', 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf')
            utilbill = session.query(UtilBill).one()
            self.process.create_first_reebill(session, utilbill)
            
            session.query(UtilBill).one() # verify there's only one
            reebill = session.query(ReeBill).one()
            self.assertEqual([utilbill], reebill.utilbills)
            self.assertTrue(utilbill.is_attached())
            # since there's no UtilBill.reebills, can't directly see what
            # reebills this utility bill has, but can check which reebills have
            # this utility bill, and there should be only one
            self.assertEqual([reebill], session.query(ReeBill)
                    .filter(ReeBill.utilbills.contains(utilbill)).all())

            # TODO check reebill document contents
            # (this is already partially handled by
            # test_reebill.ReebillTest.test_get_reebill_doc_for_utilbills, but
            # should be done here as well.)

            self.assertRaises(ValueError, self.process.create_first_reebill,
                    session, utilbill)

    def test_uncomputable_correction_bug(self):
        '''Regresssion test for
        https://www.pivotaltracker.com/story/show/53434901.'''
        account = '99999'

        with DBSession(self.state_db) as session:
            # create reebill and utility bill
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf')
            utilbill = session.query(UtilBill).filter_by(
                    customer=self.state_db.get_customer(session, account)).one()
            self.process.create_first_reebill(session, utilbill)
            reebill_doc = self.reebill_dao.load_reebill(account, 1)

            # bind, compute, issue
            fbd.fetch_oltp_data(self.splinter,
                    self.nexus_util.olap_id(account), reebill_doc,
                    use_olap=True)
            self.process.compute_reebill(session, reebill_doc)
            self.process.issue(session, account, 1)

            # create new version
            self.process.new_version(session, account, 1)
            self.assertEquals(1, self.state_db.max_version(session, account,
                    1))
            reebill_correction = session.query(ReeBill)\
                    .filter_by(version=1).one()

            # put it in an un-computable state by adding a charge without an RSI
            reebill_correction_doc = self.reebill_dao.load_reebill(account, 1,
                    version=1)
            reebill_correction_doc._utilbills[0]['chargegroups']\
                    ['All Charges'].append({
                        'rsi_binding': 'NO_RSI',
                        "description" : "Can't compute this",
                        "quantity" : 1,
                        "quantity_units" : "",
                        "rate" : 11.2,
                        #"rate_units" : "dollars",
                        "total" : 11.2,
                        "uuid" : "c96fc8b0-2c16-11e1-8c7f-002421e88ffc"
                    })
            with self.assertRaises(KeyError) as context:
                self.process.compute_reebill(session, reebill_correction_doc)
            self.reebill_dao.save_reebill(reebill_correction_doc)

            # delete the new version
            self.process.delete_reebill(session, reebill_correction)
            self.assertEquals(0, self.state_db.max_version(session, account,
                    1))

        # try to create a new version again: it should succeed, even though
        # there was a KeyError due to a missing RSI when computing the bill
        with DBSession(self.state_db) as session:
            self.process.new_version(session, account, 1)
        self.assertEquals(1, self.state_db.max_version(session, account, 1))

    def test_compute_utility_bill(self):
        '''Tests creation of a utility bill and updating the Mongo document
        after the MySQL row has changed.'''
        with DBSession(self.state_db) as session:
            # create reebill and utility bill
            # NOTE Process._generate_docs_for_new_utility_bill requires utility
            # and rate_class arguments to match those of the template
            self.process.upload_utility_bill(session, '99999', 'gas',
                     date(2013,5,6), date(2013,7,8), StringIO('A Water Bill'),
                     'waterbill.pdf', utility='washgas',
                     rate_class='some rate structure')
            utilbill = session.query(UtilBill).filter_by(
                    customer=self.state_db.get_customer(session,
                    '99999')).one()
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEquals('99999', doc['account'])
            self.assertEquals(date(2013,5,6), doc['start'])
            self.assertEquals(date(2013,7,8), doc['end'])
            # TODO enable these assertions when upload_utility_bill stops
            # ignoring them; currently they are set to match the template's
            # values regardless of the arguments to upload_utility_bill, and
            # Process._generate_docs_for_new_utility_bill requires them to
            # match the template.
            #self.assertEquals('water', doc['service'])
            #self.assertEquals('pepco', doc['utility'])
            #self.assertEquals('pepco', doc['rate_class'])

            # modify the MySQL utility bill
            utilbill.period_start = date(2014,1,1)
            utilbill.period_end = date(2014,2,1)
            utilbill.service = 'electricity'
            utilbill.utility = 'BGE'
            utilbill.rate_class = 'General Service - Schedule C'

            # add some RSIs to the UPRS and CPRS, and charges to match
            uprs = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
            cprs = self.rate_structure_dao.load_cprs_for_utilbill(utilbill)
            uprs.rates = [
                RateStructureItem(rsi_binding='A', description='UPRS only',
                        quantity='2', rate='3', quantity_units='kWh'),
                RateStructureItem(rsi_binding='B', description='overridden',
                        quantity='4', rate='5', quantity_units='kWh'),
            ]
            cprs.rates = [
                RateStructureItem(rsi_binding='B', description=(
                        'CPRS overrides UPRS'), quantity='6',  rate='7',
                        quantity_units='therms'),
                RateStructureItem(rsi_binding='C', description=('this one '
                        'CPRS only'), quantity='8', rate='9',
                        quantity_units='BTU')
            ]
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            doc['chargegroups'] = {'All Charges': [{'rsi_binding': rsi_binding,
                    'quantity': 0, 'rate': 0, 'total': 0}
                    for rsi_binding in ('ABC')]}
            uprs.save()
            cprs.save()
            self.reebill_dao.save_utilbill(doc)

            # compute_utility_bill should update the document to match
            self.process.compute_utility_bill(session, utilbill.id)
            doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
            self.assertEquals('99999', doc['account'])
            self.assertEquals(date(2014,1,1), doc['start'])
            self.assertEquals(date(2014,2,1), doc['end'])
            self.assertEquals('electricity', doc['service'])
            self.assertEquals('BGE', doc['utility'])
            self.assertEquals('General Service - Schedule C',
                    doc['rate_class'])

            # check charges
            # NOTE if the commented-out lines are added below the test will
            # fail, because the charges are missing those keys.
            self.assertEqual({'All Charges': [
                {
                    'rsi_binding': 'A',
                    'quantity': 2,
                    #'quantity_units': 'kWh',
                    'rate': 3,
                    'total': 6,
                    #'description': 'UPRS only',
                }, {
                    'rsi_binding': 'B',
                    'quantity': 6,
                    #'quantity_units': 'therms',
                    'rate': 7,
                    'total': 42,
                    #'description': 'CPRS overrides UPRS',
                }, {
                    'rsi_binding': 'C',
                    'quantity': 8,
                    #'quantity_units': 'BTU',
                    'rate': 9,
                    'total': 72,
                    #'description': 'CPRS only',
                },
            ]}, doc['chargegroups']);


    def test_compute_reebill(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf')
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,2,1), date(2013,3,1), StringIO('February 2013'),
                    'february.pdf')

            # create reebill and utility bill
            first_utilbill = session.query(UtilBill).filter_by(
                    customer=self.state_db.get_customer(session, account))\
                    .order_by(UtilBill.period_start).first()
            self.process.create_first_reebill(session, first_utilbill)

            # bind, compute, issue
            doc1 = self.reebill_dao.load_reebill(account, 1)
            fbd.fetch_oltp_data(self.splinter,
                    self.nexus_util.olap_id(account), doc1, use_olap=True)
            self.process.compute_reebill(session, doc1)
            self.reebill_dao.save_reebill(doc1)
            # set balance_due in the fist document to a non-0 value so that it
            # can be checked against next bill's "prior balance" below.
            # TOOD remove this when it can be made to have a non-0 balance_due
            doc1.balance_due = 1234.56
            self.reebill_dao.save_reebill(doc1)
            self.process.issue(session, account, 1, issue_date=date(2013,2,15))
            assert session.query(ReeBill).filter(ReeBill.sequence==1).one()\
                .issue_date == date(2013,2,15)

            doc1 = self.reebill_dao.load_reebill(account, 1)
            self.assertEquals(0, doc1.prior_balance)
            self.assertEquals(0, doc1.payment_received)
            self.assertEquals(0, doc1.balance_forward)
            # TODO insert real balance_due value
            self.assertEquals(1234.56, doc1.balance_due)
            # TODO check everything else...

            # add a payment so payment_received is not 0
            payment_amount = 100
            self.state_db.create_payment(session, account, date(2013,2,17),
                    'a payment for the first reebill', payment_amount)

            # 2nd reebill
            self.process.create_next_reebill(session, account)
            doc2 = self.reebill_dao.load_reebill(account, 2)
            self.process.compute_reebill(session, doc2)
            self.assertEquals(doc1.balance_due, doc2.prior_balance)
            self.assertEquals(payment_amount, doc2.payment_received)
            self.assertEquals(doc1.balance_due - payment_amount,
                    doc2.balance_forward)
            # TODO check everything else...


if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
