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
import re
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner.sky_handlers import cross_range
from datetime import date, datetime, timedelta
from billing.processing import mongo
from billing.processing.session_contextmanager import DBSession
from billing.util.dateutils import estimate_month, month_offset, date_to_datetime
from billing.processing import rate_structure
from billing.processing.process import Process, IssuedBillError
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
from billing.processing.billupload import BillUpload
from decimal import Decimal
from billing.util.dictutils import deep_map
import MySQLdb
from billing.util.mongo_utils import python_convert
from billing.test.setup_teardown import TestCaseWithSetup
from billing.test import example_data
from skyliner.mock_skyliner import MockSplinter, MockMonguru, hour_of_energy
from billing.util.nexus_util import NexusUtil
from billing.processing.mongo import NoSuchBillException
from billing.processing.exceptions import BillStateError
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
        # set up template customer
        with DBSession(self.state_db) as session:
            #self.process.new_account(session, 'Template Account', '99999', 0.5,
                    #0.1)
            self.reebill_dao.save_reebill(example_data.get_reebill('99999', 1,
                    start=date(2012,1,1), end=date(2012,2,1)))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 1))
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict('99999', 1))
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.state_db.new_reebill(session, '99999', 1)
            # store template account's reebill (includes utility bill) to check
            # for modification
            template_reebill = self.reebill_dao.load_reebill('99999', 1)

        # create new account "10000" based on template account "99999"
        with DBSession(self.state_db) as session:
            self.process.create_new_account(session, '100000', 'New Account',
                    0.6, 0.2, '99999')

            # MySQL customer
            customer = self.state_db.get_customer(session, '100000')
            self.assertEquals('100000', customer.account)
            self.assertEquals(Decimal('0.6'), customer.discountrate)
            self.assertEquals(Decimal('0.2'), customer.latechargerate)

            # MySQL reebill: none exist in MySQL until #1 is rolled
            self.assertEquals([], self.state_db.listSequences(session, '100000'))

            # Mongo reebill (sequence 0)
            mongo_reebill = self.reebill_dao.load_reebill('100000', 0)
            self.assertEquals('100000', mongo_reebill.account)
            self.assertEquals(0, mongo_reebill.sequence)
            self.assertEquals(0, mongo_reebill.version)
            self.assertEquals(0, mongo_reebill.prior_balance)
            self.assertEquals(0, mongo_reebill.payment_received)
            self.assertEquals(0, mongo_reebill.balance_forward)
            self.assertEquals(0, mongo_reebill.total_renewable_energy())
            self.assertEquals(0, mongo_reebill.ree_charges)
            self.assertEquals(0, mongo_reebill.ree_value)
            self.assertEquals(0, mongo_reebill.ree_savings)
            self.assertEquals(0, mongo_reebill.balance_due)
            # some bills lack late_charges key, which is supposed to be
            # distinct from late_charges: None, and late_charges: 0
            try:
                self.assertEquals(0, mongo_reebill.late_charges)
            except KeyError as ke:
                if ke.message != 'late_charges':
                    raise
            self.assertEquals(0, mongo_reebill.total)
            self.assertEquals(0, mongo_reebill.total_adjustment)
            self.assertEquals(0, mongo_reebill.manual_adjustment)
            self.assertEquals(None, mongo_reebill.issue_date)
            self.assertEquals([], mongo_reebill.bill_recipients)
            self.assertEquals(Decimal('0.6'), mongo_reebill.discount_rate)
            self.assertEquals(Decimal('0.2'), mongo_reebill.late_charge_rate)

            # Mongo utility bill: nothing to check? (existence tested by load_reebill)

            # TODO Mongo rate structure documents

            # check that template account's utility bill and reebill was not modified
            template_reebill_again = self.reebill_dao.load_reebill('99999', 1)
            self.assertEquals(template_reebill.reebill_dict, template_reebill_again.reebill_dict)
            self.assertEquals(template_reebill._utilbills, template_reebill_again._utilbills)
            for utilbill in mongo_reebill._utilbills:
                self.assertNotIn(utilbill['_id'], [u['_id'] for u in
                        template_reebill._utilbills])


    def test_get_late_charge(self):
        print 'test_get_late_charge'
        '''Tests computation of late charges (without rolling bills).'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # set customer late charge rate
            self.state_db.get_customer(session, acc).latechargerate = .34

            # create bill 0 (template) and its utility bill and rate structure
            self.reebill_dao.save_reebill(example_data.get_reebill(acc, 0,
                    start=date(2011,12,31), end=date(2012,1,1)))
            bill0 = self.reebill_dao.load_reebill(acc, 0)
            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), 100,
                    datetime.utcnow().date())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 0))

            # create bill 1, with no late charge (and its rate structures)
            bill1 = self.process.roll_bill(session, bill0)
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
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc, 1))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 1))

            # issue bill 1, so a later bill can have a late charge based on the
            # customer's failure to pay bill1 by its due date, i.e. 30 days
            # after the issue date.
            self.process.issue(session, bill1.account, bill1.sequence,
                    issue_date=date(2012,1,1))
            # since process.issue() only modifies databases, bill1 must be
            # re-loaded from mongo to reflect its new issue date
            bill1 = self.reebill_dao.load_reebill(bill1.account, bill1.sequence)
            assert bill1.issue_date == date(2012,1,1)
            assert bill1.due_date == date(2012,1,31)
 
            # after bill1 is created, it must be computed to get it into a
            # usable state (in particular, it needs a late charge). that
            # requires a sequence 0 template bill.
            self.process.compute_bill(session, bill0, bill1)
 
            # but compute_bill() destroys bill1's balance_due, so reset it to
            # the right value, and save it in mongo
            bill1.balance_due = Decimal('100.')
            self.reebill_dao.save_reebill(bill1, force=True)

            # create bill 2
            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,2,1), date(2012,3,1), 100,
                    datetime.utcnow().date())
            bill2 = self.process.roll_bill(session, bill1)
            bill2.balance_due = Decimal('200.')

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
            self.process.compute_bill(session, bill1, bill2)
 
            # create a 3rd bill without issuing bill2. bill3 should have None
            # as its late charge for all dates
            bill3 = example_data.get_reebill(acc, 3)
            bill3.balance_due = Decimal('300.')
            self.assertEqual(None, self.process.get_late_charge(session, bill3,
                    date(2011,12,31)))
            self.assertEqual(None, self.process.get_late_charge(session, bill3,
                    date(2013,1,1)))


            # this should be unnecessary now that meter read date is filled in
            # using utility bill period end date
            ## update the meter like the user normally would
            ## This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            #meter = bill1.meters_for_service('gas')[0]
            #bill1.set_meter_read_date('gas', meter['identifier'], date(2012,2,1), date(2012,1,1))
            #self.reebill_dao.save_reebill(bill1, force=True)

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
        account = '99999'
        try:
            session = self.state_db.session()
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(account, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(account, 0))

            self.state_db.record_utilbill_in_database(session, account,
                    'gas', date(2012,1,1), date(2012,2,1), 100, date.today())
            self.state_db.record_utilbill_in_database(session, account,
                    'electric', date(2012,1,10), date(2012,2,10), 100, date.today())
            #self.reebill_dao._save_utilbill(example_data.get_utilbill_dict(account, date(2012,1,1), date(2012,2,1), service='gas'))
            #self.reebill_dao._save_utilbill(example_data.get_utilbill_dict(account, date(2012,1,10), date(2012,2,10), service='electric'))

            # generic reebill
            bill0 = example_data.get_reebill(account, 0)

            # make it have 2 services, 1 suspended
            # (create electric bill by duplicating gas bill)
            electric_bill = example_data.get_utilbill_dict(account, service='electric')
            #self.reebill_dao._save_utilbill(electric_bill)
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
        assert len(bill1.services) == 1
        service = bill1.services[0]
        utility_name = bill1.utility_name_for_service(service)
        rate_structure_name = bill1.rate_structure_name_for_service(service)

        # make rate structure documents and save them in db
        urs_dict = example_data.get_urs_dict()
        cprs_dict = example_data.get_cprs_dict(account, sequence)
        self.rate_structure_dao.save_urs(utility_name, rate_structure_name,
                urs_dict)
        self.rate_structure_dao.save_cprs(account, sequence, 0, utility_name,
                rate_structure_name, cprs_dict)

        # compute charges in the bill using the rate structure created from the
        # above documents
        self.process.bind_rate_structure(bill1)

        # ##############################################################
        # check that each actual (utility) charge was computed correctly:
        actual_chargegroups = bill1.actual_chargegroups_for_service(service)
        assert actual_chargegroups.keys() == ['All Charges']
        actual_charges = actual_chargegroups['All Charges']
        actual_registers = bill1.actual_registers(service)
        total_regster = [r for r in actual_registers if r['register_binding'] == 'REG_TOTAL'][0]

        # system charge: $11.2 in CPRS overrides $26.3 in URS
        system_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'SYSTEM_CHARGE'][0]
        self.assertEquals(11.2, system_charge['total'])

        # right-of-way fee
        row_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'RIGHT_OF_WAY'][0]
        self.assertAlmostEqual(0.03059 * float(total_regster['quantity']),
                row_charge['total'], places=2) # TODO OK to be so inaccurate?
        
        # sustainable energy trust fund
        setf_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'SETF'][0]
        self.assertAlmostEqual(0.01399 * float(total_regster['quantity']),
                setf_charge['total'], places=1) # TODO OK to be so inaccurate?

        # energy assistance trust fund
        eatf_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'EATF'][0]
        self.assertAlmostEqual(0.006 * float(total_regster['quantity']),
                eatf_charge['total'], places=2)

        # delivery tax
        delivery_tax = [c for c in actual_charges if c['rsi_binding'] ==
                'DELIVERY_TAX'][0]
        self.assertAlmostEqual(0.07777 * float(total_regster['quantity']),
                delivery_tax['total'], places=2)

        # peak usage charge
        peak_usage_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'PUC'][0]
        self.assertEquals(23.14, peak_usage_charge['total'])

        # distribution charge
        distribution_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'DISTRIBUTION_CHARGE'][0]
        self.assertAlmostEqual(.2935 * float(total_regster['quantity']),
                distribution_charge['total'], places=2)
        
        # purchased gas charge
        purchased_gas_charge = [c for c in actual_charges if c['rsi_binding'] ==
                'PGC'][0]
        self.assertAlmostEqual(.7653 * float(total_regster['quantity']),
                purchased_gas_charge['total'], places=2)

        # sales tax: depends on all of the above
        sales_tax = [c for c in actual_charges if c['rsi_binding'] ==
                'SALES_TAX'][0]
        self.assertAlmostEqual(0.06 * float(system_charge['total'] +
                distribution_charge['total'] + purchased_gas_charge['total'] +
                row_charge['total'] + peak_usage_charge['total'] +
                setf_charge['total'] + eatf_charge['total'] +
                delivery_tax['total']),
                sales_tax['total'],
                places=2)


        # ##############################################################
        # check that each hypothetical charge was computed correctly:
        hypothetical_chargegroups = bill1.hypothetical_chargegroups_for_service(service)
        assert hypothetical_chargegroups.keys() == ['All Charges']
        hypothetical_charges = hypothetical_chargegroups['All Charges']
        shadow_registers = bill1.shadow_registers(service)
        total_shadow_regster = [r for r in shadow_registers if r['register_binding'] == 'REG_TOTAL'][0]
        hypothetical_quantity = float(total_shadow_regster['quantity'] + total_regster['quantity'])

        # system charge: $11.2 in CPRS overrides $26.3 in URS
        system_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'SYSTEM_CHARGE'][0]
        self.assertEquals(11.2, system_charge['total'])

        # right-of-way fee
        row_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'RIGHT_OF_WAY'][0]
        self.assertAlmostEqual(0.03059 * hypothetical_quantity,
                row_charge['total'], places=2) # TODO OK to be so inaccurate?
        
        # sustainable energy trust fund
        setf_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'SETF'][0]
        self.assertAlmostEqual(0.01399 * hypothetical_quantity,
                setf_charge['total'], places=1) # TODO OK to be so inaccurate?

        # energy assistance trust fund
        eatf_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'EATF'][0]
        self.assertAlmostEqual(0.006 * hypothetical_quantity,
                eatf_charge['total'], places=2)

        # delivery tax
        delivery_tax = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'DELIVERY_TAX'][0]
        self.assertAlmostEqual(0.07777 * hypothetical_quantity,
                delivery_tax['total'], places=2)

        # peak usage charge
        peak_usage_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'PUC'][0]
        self.assertEquals(23.14, peak_usage_charge['total'])

        # distribution charge
        distribution_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'DISTRIBUTION_CHARGE'][0]
        self.assertAlmostEqual(.2935 * hypothetical_quantity,
                distribution_charge['total'], places=1)
        
        # purchased gas charge
        purchased_gas_charge = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'PGC'][0]
        self.assertAlmostEqual(.7653 * hypothetical_quantity,
                purchased_gas_charge['total'], places=2)

        # sales tax: depends on all of the above
        sales_tax = [c for c in hypothetical_charges if c['rsi_binding'] ==
                'SALES_TAX'][0]
        self.assertAlmostEqual(0.06 * float(system_charge['total'] +
                distribution_charge['total'] + purchased_gas_charge['total'] +
                row_charge['total'] + peak_usage_charge['total'] +
                setf_charge['total'] + eatf_charge['total'] +
                delivery_tax['total']),
                sales_tax['total'],
                places=2)


    def test_upload_utility_bill(self):
        '''Tests saving of utility bills in database (which also belongs partly
        to StateDB); does not test saving of utility bill files (which belongs
        to BillUpload).'''
        # TODO include test of saving of utility bill files here
        print 'test_upload_utility_bill'
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

            # second contiguous bill
            file2 = StringIO("Let's pretend this is a PDF")
            self.process.upload_utility_bill(session, account, service,
                    date(2012,2,1), date(2012,3,1), file2, 'february.pdf')
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

            # 3rd bill without a file ("skyline estimated")
            self.process.upload_utility_bill(session, account, service,
                    date(2012,3,1), date(2012,4,1), None, None)
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

            # 4th bill without a gap between it and th 3rd bill: hypothetical
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

    def test_delete_utility_bill(self):
        account, service, = '99999', 'gas'
        start, end = date(2012,1,1), date(2012,2,1)

        with DBSession(self.state_db) as session:
            # create utility bill in MySQL and filesystem (and make sure it
            # exists in both places)
            self.process.upload_utility_bill(session, account, service, start, end,
                    StringIO("test"), 'january.pdf')
            assert self.state_db.list_utilbills(session, account)[1] == 1
            bill_file_path = self.billupload.get_utilbill_file_path(account,
                    start, end)
            assert os.access(bill_file_path, os.F_OK)
            customer = session.query(Customer)\
                    .filter(Customer.account == account).one()
            utilbill_id = session.query(UtilBill)\
                    .filter(UtilBill.customer_id == customer.id)\
                    .filter(UtilBill.period_start == start)\
                    .filter(UtilBill.period_end == end).one().id

            # with no reebills, deletion should succeed: row removed from
            # MySQL, document removed from Mongo (only template should be
            # left), file moved to trash directory
            new_path = self.process.delete_utility_bill(session, utilbill_id)
            self.assertEqual(0, self.state_db.list_utilbills(session, account)[1])
            self.assertEquals([self.reebill_dao.load_utilbill_template(session, account)],
                    self.reebill_dao.load_utilbills())
            self.assertFalse(os.access(bill_file_path, os.F_OK))
            self.assertRaises(IOError, self.billupload.get_utilbill_file_path,
                    account, start, end)
            self.assertTrue(os.access(new_path, os.F_OK))

            # re-upload the bill
            self.process.upload_utility_bill(session, account, service, start,
                    end, StringIO("test"), 'january.pdf')
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
            assert utilbill.reebills == [first_reebill]
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill.id)

            # deletion should fail if any version of a reebill has an
            # association with the utility bill. so issue the reebill and
            # create a new version of the reebill that does not have this
            # utility bill.
            self.process.issue(session, account, 1)
            self.process.new_version(session, account, 1)
            mongo_reebill.version = 1
            mongo_reebill.set_utilbill_period_for_service(service, (start -
                    timedelta(days=365), end - timedelta(days=365)))
            self.reebill_dao.save_reebill(mongo_reebill)
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill.id)
            session.commit()

            # test deletion of a Skyline-estimated utility bill (no file)
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,1,1), date(2013,2,1), None, 'no file name')
            self.process.delete_utility_bill(session,
                    self.state_db.get_utilbill(session, account, 'gas',
                    date(2013,1,1), date(2013,2,1)).id)

            # test deletion of utility bill with non-standard file extension
            self.process.upload_utility_bill(session, account, 'gas',
                    date(2013,2,1), date(2013,3,1), StringIO("a bill"),
                    'billfile.abcdef')
            the_path = self.billupload.get_utilbill_file_path(account,
                    date(2013,2,1), date(2013,3,1))
            assert os.access(the_path, os.F_OK)
            self.process.delete_utility_bill(session,
                    self.state_db.get_utilbill(session, account, 'gas',
                    date(2013,2,1), date(2013,3,1)).id)
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
                    date(2013,2,1), date(2013,3,1)).id)
            self.assertFalse(os.access(the_path, os.F_OK))

    def test_new_version(self):
        # put reebill documents for sequence 0 and 1 in mongo (0 is needed to
        # recompute 1), and rate structures for 1
        acc = '99999'
        zero = example_data.get_reebill(acc, 0, version=0,
                start=date(2011,12,1), end=date(2012,1,1))
        self.reebill_dao.save_reebill(zero)

        #self.reebill_dao.save_reebill(one)
        self.rate_structure_dao.save_rs(example_data.get_urs_dict())
        self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc, 0))
        self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 0))

        # TODO creating new version of 1 should fail until it's issued

        # issue reebill 1
        with DBSession(self.state_db) as session:
            #self.state_db.new_reebill(session, acc, 1)
            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), 100,
                    datetime.utcnow().date())
            #self.process.attach_utilbills(session, acc, 1)
            one = self.process.roll_bill(session, zero)

            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = one.meters_for_service('gas')[0]
            one.set_meter_read_date('gas', meter['identifier'], date(2012,2,1), date(2012,1,1))
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, 1, issue_date=date(2012,1,15))

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
        self.reebill_dao._save_utilbill(editable_utilbill)
        # find the expected total energy (produced by MockSplinter) if this
        # period is used. it is extremely unlikely to exactly match the total
        # energy that would be produced for a different period(especially
        # because the length is different).
        correct_energy_amount_therms = sum([hour_of_energy(h) for h in
                cross_range(datetime(2012,1,15), datetime(2012,3,15))]) / 1e5

        # create new version of 1
        with DBSession(self.state_db) as session:
            new_bill = self.process.new_version(session, acc, 1)

        # basic facts about new version
        self.assertEqual(acc, new_bill.account)
        self.assertEqual(1, new_bill.sequence)
        self.assertEqual(1, new_bill.version)
        self.assertEqual(1, self.state_db.max_version(session, acc, 1))

        # the editable utility bill with the new meter read period should be used
        self.assertEqual((date(2012,1,15), date(2012,3,15)),
                new_bill.meter_read_dates_for_service('gas'))

        # new version of CPRS(s) should also be created, so rate structure
        # should be loadable
        for s in new_bill.services:
            self.assertNotEqual(None, self.rate_structure_dao.load_cprs(acc, 1,
                    new_bill.version, new_bill.utility_name_for_service(s),
                    new_bill.rate_structure_name_for_service(s)))
            self.assertNotEqual(None,
                    self.rate_structure_dao.load_rate_structure(new_bill, s))

        # if the total REE is 'correct_energy_amount_therms' (within
        # floating-point error), the correct meter read period was used.
        self.assertAlmostEqual(correct_energy_amount_therms,
                float(new_bill.total_renewable_energy()))

    def test_correction_issuing(self):
        '''Tests get_unissued_corrections(), get_total_adjustment(), and
        issue_corrections().'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # reebills 1-4, 1-3 issued
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict('99999', 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 0))
            base_date = date(2012,1,1)
            dates = [base_date + timedelta(days=30*x) for x in xrange(5)]
            for n in xrange(4):
                self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    dates[n], dates[n+1], 100,
                    datetime.utcnow().date())
                #self.reebill_dao._save_utilbill(example_data.get_utilbill_dict(acc, dates[n], dates[n+1]))
            
            zero = example_data.get_reebill(acc, 0)
            zero.ree_charges = 100
            self.reebill_dao.save_reebill(zero)

            one = self.process.roll_bill(session, zero)
            one.ree_charges = 100
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = one.meters_for_service('gas')[0]
            one.set_meter_read_date('gas', meter['identifier'], one.period_end, one.period_begin)
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, one.sequence)
            one = self.reebill_dao.load_reebill(acc, one.sequence)

            two = self.process.roll_bill(session, one)
            two.ree_charges = 100
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = two.meters_for_service('gas')[0]
            two.set_meter_read_date('gas', meter['identifier'], two.period_end, two.period_begin)
            self.reebill_dao.save_reebill(two)
            self.process.issue(session, acc, two.sequence)
            two = self.reebill_dao.load_reebill(acc, two.sequence)

            three = self.process.roll_bill(session, two)
            three.ree_charges = 100
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = three.meters_for_service('gas')[0]
            three.set_meter_read_date('gas', meter['identifier'], three.period_end, three.period_begin)
            self.reebill_dao.save_reebill(three)
            self.process.issue(session, acc, three.sequence)
            three = self.reebill_dao.load_reebill(acc, three.sequence)

            four = self.process.roll_bill(session, three)
            four.ree_charges = 100
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = four.meters_for_service('gas')[0]
            four.set_meter_read_date('gas', meter['identifier'], four.period_end, four.period_begin)
            self.reebill_dao.save_reebill(four)

            # no unissued corrections yet
            self.assertEquals([],
                    self.process.get_unissued_corrections(session, acc))
            self.assertIs(Decimal,
                    type(self.process.get_total_adjustment(session, acc)))
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
            self.assertIs(Decimal,
                    type(self.process.get_total_adjustment(session, acc)))
            self.assertEqual(15, self.process.get_total_adjustment(session, acc))

            # try to apply corrections to an issued bill
            self.assertRaises(ValueError, self.process.issue_corrections,
                    session, acc, 2)
            # try to apply corrections to a correction
            self.assertRaises(ValueError, self.process.issue_corrections,
                    session, acc, 3)

            # get original balance of reebill 4 before applying corrections
            four = self.reebill_dao.load_reebill(acc, 4)
            self.process.compute_bill(session, three, four)
            four_original_balance = four.balance_due

            # apply corrections to un-issued reebill 4. reebill 4 should be
            # updated, and the corrections (1 & 3) should be issued
            self.process.issue_corrections(session, acc, 4)
            four = self.reebill_dao.load_reebill(acc, 4)
            self.process.compute_bill(session, three, four)
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
            # save rate structures for the bills
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 0))
            #self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 2))

            #utilbill = example_data.get_utilbill_dict(acc, start=date(2012,1,1), end=date(2012,2,1))
            #self.reebill_dao._save_utilbill(utilbill)
            #utilbill = example_data.get_utilbill_dict(acc, start=date(2012,2,1), end=date(2012,3,1))
            #self.reebill_dao._save_utilbill(utilbill)

            # 2 reebills, 1 issued 40 days ago and unpaid (so it's 10 days late)
            zero = example_data.get_reebill(acc, 0, start=date(2011,12,31),
                    end=date(2012,1,1)) # template
            self.reebill_dao.save_reebill(zero)

            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), 100,
                    datetime.utcnow().date())
            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,2,1), date(2012,3,1), 100,
                    datetime.utcnow().date())

            #one = example_data.get_reebill(acc, 1, start=date(2012,1,1),
            #        end=date(2012,2,1))
            #two0 = example_data.get_reebill(acc, 2, start=date(2012,2,1),
            #        end=date(2012,3,1))
            one = self.process.roll_bill(session, zero)
            one.balance_due = 100
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = one.meters_for_service('gas')[0]
            one.set_meter_read_date('gas', meter['identifier'], date(2012,2,1), date(2012,1,1))
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, one.sequence, issue_date=datetime.utcnow().date() - timedelta(40))
            one = self.reebill_dao.load_reebill(acc, one.sequence)

            two = self.process.roll_bill(session, one)
            two.balance_due = 100
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = two.meters_for_service('gas')[0]
            two.set_meter_read_date('gas', meter['identifier'], date(2012,3,1), date(2012,2,1))
            self.reebill_dao.save_reebill(two)
            #self.process.issue(session, acc, two.sequence)
            #self.state_db.new_reebill(session, acc, 1)
            #self.state_db.new_reebill(session, acc, 2)
            
            #self.process.attach_utilbills(session, acc, 1)

            # bind & compute 2nd reebill
            # (it needs energy data only so its correction will have the same
            # energy in it; only the late charge will differ)
            two = self.reebill_dao.load_reebill(acc, 2)
            two.late_charge_rate = .5
            fbd.fetch_oltp_data(self.splinter, self.nexus_util.olap_id(acc),
                    two)

            # if given a late_charge_rate > 0, 2nd reebill should have a late charge
            self.process.compute_bill(session, one, two)
            self.assertEqual(50, two.late_charges)

            # save and issue 2nd reebill so a new version can be created
            self.reebill_dao.save_reebill(two)
            #self.process.attach_utilbills(session, acc, two.sequence)
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
            self.assertEquals((2, 1, Decimal(-40)), corrections[0])

    def test_roll(self):
        '''Tests Process.roll_bill, which modifies a MongoReebill to convert it
        into its sequence successor, and copies the CPRS in Mongo. (The bill
        itself is not saved in any database.)'''
        account = '99999'
        dt = date.today()
        month = timedelta(days=30)
        re_no_utilbill = re.compile('No new [a-z]+ utility bill found')
        re_no_final_utilbill = re.compile('The next [a-z]+ utility bill exists but has not been fully estimated or received')
        re_time_gap = re.compile('There is a gap of [0-9]+ days before the next [a-z]+ utility bill found')

        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)
            reebill_0 = example_data.get_reebill(account, 0, dt-month, dt)
            self.reebill_dao.save_reebill(reebill_0, freeze_utilbills=True)
            # Set up example rate structure
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(account, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(account, 0))

            # There are no utility bills yet, so rolling should fail.
            with self.assertRaises(Exception) as context:
                self.process.roll_bill(session, reebill_0)
            self.assertTrue(re.match(re_no_utilbill, str(context.exception)))

            target_utilbill = UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt, period_end=dt+month, reebill=None)
            session.add(target_utilbill)

            # Make sure the reebill period reflects the correct utilbill
            reebill_1 = self.process.roll_bill(session, reebill_0)
            self.assertEqual(reebill_1.period_begin, target_utilbill.period_start)
            self.assertEqual(reebill_1.period_end, target_utilbill.period_end)

            # bill should be computable after rolling
            self.process.compute_bill(session, reebill_0, reebill_1) 

            self.process.issue(session, account, reebill_1.sequence)
            reebill_1 = self.reebill_dao.load_reebill(account, reebill_1.sequence)

            # Add two utilbills: one hypothetical followed by one final one
            hypo_utilbill = UtilBill(customer=customer, state=3, service='gas',\
                period_start=dt+month, period_end=dt+(month*2), reebill=None)
            later_utilbill = UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+(month*2), period_end=dt+(month*3), reebill=None)

            session.add_all([hypo_utilbill, later_utilbill])

            # The next utility bill isn't estimated or final, so rolling should fail
            with self.assertRaises(Exception) as context:
                self.process.roll_bill(session, reebill_1)
            self.assertTrue(re.match(re_no_final_utilbill, str(context.exception)))

            # Set hypo_utilbill to Utility Estimated, save it, and then we
            # should be able to roll on it
            hypo_utilbill.state = UtilBill.UtilityEstimated;
            target_utilbill = session.merge(hypo_utilbill)

            reebill_2 = self.process.roll_bill(session, reebill_1)
            self.assertEqual(reebill_2.period_begin, target_utilbill.period_start)
            self.assertEqual(reebill_2.period_end, target_utilbill.period_end)
            self.process.compute_bill(session, reebill_1, reebill_2) 

            self.process.issue(session, account, reebill_2.sequence)
            reebill_2 = self.reebill_dao.load_reebill(account, reebill_2.sequence)

            # Shift later_utilbill a few days into the future so that there is
            # a time gap after the last attached utilbill
            later_utilbill.period_start += timedelta(days=5)
            later_utilbill.period_end += timedelta(days=5)
            later_utilbill = session.merge(later_utilbill)

            with self.assertRaises(Exception) as context:
                self.process.roll_bill(session, reebill_2)
            self.assertTrue(re.match(re_time_gap, str(context.exception)))

            # Shift it back to a 1 day (therefore acceptable) gap, which should make it work
            later_utilbill.period_start -= timedelta(days=4)
            later_utilbill.period_end -= timedelta(days=4)
            target_utilbill = session.merge(later_utilbill)

            self.process.roll_bill(session, reebill_2)

            reebill_3 = self.reebill_dao.load_reebill(account, 3)
            self.assertEqual(reebill_3.period_begin, target_utilbill.period_start)
            self.assertEqual(reebill_3.period_end, target_utilbill.period_end)
            self.process.compute_bill(session, reebill_2, reebill_3) 

            # TODO: Test multiple services

            # MySQL reebill
            customer = self.state_db.get_customer(session, '99999')
            mysql_reebill = self.state_db.get_reebill(session, '99999', 3)
            self.assertEquals(3, mysql_reebill.sequence)
            self.assertEquals(customer.id, mysql_reebill.customer_id)
            self.assertEquals(False, mysql_reebill.issued)
            self.assertEquals(0, mysql_reebill.version)
            self.assertEquals(0,
                    session.query(sqlalchemy.func.max(ReeBill.version))\
                    .filter(ReeBill.customer==customer)\
                    .filter(ReeBill.sequence==3).one()[0])

            # TODO ...

    def test_roll_rs_prediction(self):
        '''Basic test of rate structure prediction when rolling bills.'''
        acc_a, acc_b, acc_c = 'aaaaa', 'bbbbb', 'ccccc'

        with DBSession(self.state_db) as session:
            # create customers A, B, and C, and reebills #0 for each (which include utility bills)
            session.add(Customer('Customer A', acc_a, .12, .34))
            session.add(Customer('Customer B', acc_b, .12, .34))
            session.add(Customer('Customer C', acc_c, .12, .34))
            reebill_a_0 = example_data.get_reebill(acc_a, 0, start=date(2012,12,1), end=date(2013,1,1))
            reebill_b_0 = example_data.get_reebill(acc_b, 0, start=date(2012,12,1), end=date(2013,1,1))
            reebill_c_0 = example_data.get_reebill(acc_c, 0, start=date(2012,12,1), end=date(2013,1,1))
            self.reebill_dao.save_reebill(reebill_a_0, freeze_utilbills=True)
            self.reebill_dao.save_reebill(reebill_b_0, freeze_utilbills=True)
            self.reebill_dao.save_reebill(reebill_c_0, freeze_utilbills=True)

            # save default rate structure documents all 3 accounts
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc_a, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc_a, 0))
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc_b, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc_b, 0))
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc_c, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc_c, 0))

            # create utility bills and reebill #1 for all 3 accounts
            # (note that period dates are not exactly aligned)
            utilbill_a_1 = UtilBill(
                    customer=self.state_db.get_customer(session, acc_a),
                    state=0, service='gas',
                    period_start=date(2013,1,1),
                    period_end=date(2013,2,1))
            utilbill_b_1 = UtilBill(
                    customer=self.state_db.get_customer(session, acc_b),
                    state=0, service='gas',
                    period_start=date(2013,1,1),
                    period_end=date(2013,2,5))
            utilbill_c_1 = UtilBill(
                    customer=self.state_db.get_customer(session, acc_c),
                    state=0, service='gas',
                    period_start=date(2013,1,1),
                    period_end=date(2013,2,3))
            session.add(utilbill_a_1)
            session.add(utilbill_b_1)
            session.add(utilbill_c_1)
            reebill_a_1 = self.process.roll_bill(session, reebill_a_0)
            reebill_b_1 = self.process.roll_bill(session, reebill_b_0)
            reebill_c_1 = self.process.roll_bill(session, reebill_c_0)

            # UPRSs of all 3 reebills will be empty, because sequence-0
            # rebills' utility bills' UPRSs are ignored when generating
            # predicted UPRSs. so, insert some RSIs into them. A gets only one
            # RSI, SYSTEM_CHARGE, while B and C get two others,
            # DISTRIBUTION_CHARGE and PGC.
            uprs_a = example_data.get_uprs_dict(acc_a, 1)
            uprs_b = example_data.get_uprs_dict(acc_b, 1)
            uprs_c = example_data.get_uprs_dict(acc_c, 1)
            uprs_a['rates'] = [
                {
                    "rsi_binding" : "SYSTEM_CHARGE",
                    "description" : "System Charge",
                    "quantity" : 1,
                    "rate_units" : "dollars",
                    "processingnote" : "",
                    "rate" : 11.2,
                    "quantity_units" : "",
                    "total" : 11.2,
                    "uuid" : "c9733cca-2c16-11e1-8c7f-002421e88ffb"
                },
            ]
            uprs_b['rates'] = uprs_c['rates'] = [
                {
                    "rsi_binding" : "DISTRIBUTION_CHARGE",
                    "description" : "Distribution charge for all therms",
                    "quantity" : 750.10197727,
                    "rate_units" : "dollars",
                    "processingnote" : "",
                    "rate" : 0.2935,
                    "quantity_units" : "therms",
                    "total" : 220.16,
                    "uuid" : "c9733ed2-2c16-11e1-8c7f-002421e88ffb"
                },
                {
                    "rsi_binding" : "PGC",
                    "description" : "Purchased Gas Charge",
                    "quantity" : 750.10197727,
                    "rate_units" : "dollars",
                    "processingnote" : "",
                    "rate" : 0.7653,
                    "quantity_units" : "therms",
                    "total" : 574.05,
                    "uuid" : "c97340da-2c16-11e1-8c7f-002421e88ffb"
                },
            ]
            self.rate_structure_dao.save_rs(uprs_a)
            self.rate_structure_dao.save_rs(uprs_b)
            self.rate_structure_dao.save_rs(uprs_c)

            # create reebill #2 for A
            utilbill_a_2 = UtilBill(
                    customer=self.state_db.get_customer(session, acc_a),
                    state=0, service='gas',
                    period_start=date(2013,2,1),
                    period_end=date(2013,3,1))
            session.add(utilbill_a_2)
            reebill_a_2 = self.process.roll_bill(session, reebill_a_1)

            # the UPRS of A's reebill #2 should match B and C, i.e. it should
            # contain DISTRIBUTION and PGC and exclude SYSTEM_CHARGE, because
            # together the other two have greater weight than A's reebill #1
            uprs_a_2 = self.rate_structure_dao.load_uprs(acc_a, 2, 0,
                    reebill_a_2.utility_name_for_service('gas'),
                    reebill_a_2.rate_structure_name_for_service('gas'))
            self.assertEqual(set(['DISTRIBUTION_CHARGE', 'PGC']),
                    set(rsi['rsi_binding'] for rsi in uprs_a_2['rates']))

            # make sure A's reebill #2 is computable after rolling (even though
            # RSIs have changed, meaning some of the original charges may not
            # have corresponding RSIs and had to be removed)
            self.process.compute_bill(session, reebill_a_1, reebill_a_2) 

            # now, modify A-2's UPRS so it differs from both A-1 and B/C-1. if
            # a new bill is rolled, the UPRS it gets depends on whether it's
            # closer to B/C-1 or to A-2.
            uprs_a_2['rates'] = [{
                "rsi_binding" : "RIGHT_OF_WAY",
                "description" : "DC Rights-of-Way Fee",
                "quantity" : 750.10197727,
                "rate_units" : "dollars",
                "processingnote" : "",
                "rate" : 0.03059,
                "quantity_units" : "therms",
                "total" : 22.95,
                "uuid" : "c97344f4-2c16-11e1-8c7f-002421e88ffb"
            },]
            self.rate_structure_dao.save_rs(uprs_a_2)

            # roll B-2 with period 2-5 to 3-5, closer to A-2 than B-1 and C-1.
            # the latter are more numerous, but A-1 should outweigh them
            # because weight decreases quickly with distance.
            session.add(UtilBill(
                    customer=self.state_db.get_customer(session, acc_b),
                    state=0, service='gas',
                    period_start=date(2013,2,5),
                    period_end=date(2013,3,5)))
            reebill_b_2 = self.process.roll_bill(session, reebill_b_1)
            uprs_b_2 = self.rate_structure_dao.load_uprs(acc_b, 2, 0,
                    reebill_b_2.utility_name_for_service('gas'),
                    reebill_b_2.rate_structure_name_for_service('gas'))
            self.assertEqual(set(['RIGHT_OF_WAY']),
                    set(rsi['rsi_binding'] for rsi in uprs_a_2['rates']))
            # TODO why is this test looking at uprs_a_2 instead of uprs_b_2? is
            # that a typo or is there a reason behind it?

            # https://www.pivotaltracker.com/story/show/47134189
            ## B-2 and its utility bill should not contain any charges that
            ## don't correspond to the rate structure.
            #actual_charge_names = [c['rsi_binding'] for c in reebill_b_2\
                    #._get_utilbill_for_service('gas')['chargegroups']
                    #['All Charges']]
            #hyp_charge_names = [c['rsi_binding'] for c in reebill_b_2\
                    #._get_handle_for_service('gas')\
                    #['hypothetical_chargegroups']['All Charges']]


    def test_issue(self):
        '''Tests attach_utilbills and issue.'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # two reebills, with utilbills, in mongo & mysql
            template = example_data.get_reebill(acc, 0)
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 0))
            self.state_db.record_utilbill_in_database(session, acc,
                    template.services[0], date(2012,1,1), date(2012,2,1),
                    100, date.today())
            self.state_db.record_utilbill_in_database(session, acc,
                    template.services[0], date(2012,2,1), date(2012,3,1),
                    100, date.today())
            utilbills = session.query(UtilBill).all()

            one = self.process.roll_bill(session, template)

            # neither reebill should be issued yet
            self.assertEquals(False, self.state_db.is_issued(session, acc, 1))
            self.assertEquals(None, one.issue_date)
            self.assertEquals(None, one.due_date)

            # two should not be attachable or issuable until one is issued
            self.assertRaises(BillStateError, self.process.attach_utilbills,
                    session, one, [utilbills[0]])
            self.assertRaises(BillStateError, self.process.issue, session, acc, 2)

            # attach & issue one
            #self.assertRaises(BillStateError, self.process.attach_utilbills, one)
            self.process.issue(session, acc, 1)

            # re-load from mongo to see updated issue date and due date
            one = self.reebill_dao.load_reebill(acc, 1)
            self.assertEquals(True, self.state_db.is_issued(session, acc, 1))
            self.assertEquals(datetime.utcnow().date(), one.issue_date)
            self.assertEquals(one.issue_date + timedelta(30), one.due_date)
            self.assertIsInstance(one.bill_recipients, list)
            self.assertEquals(len(one.bill_recipients), 0)
            self.assertIsInstance(one.last_recipients, list)
            self.assertEquals(len(one.last_recipients), 0)

            two = self.process.roll_bill(session, one)
            two.bill_recipients = ['test1@reebill.us', 'test2@reebill.us']
            self.reebill_dao.save_reebill(two)
            
            # attach & issue two
            self.assertRaises(BillStateError, self.process.attach_utilbills,
                    session, two, [utilbills[1]])
            self.process.issue(session, acc, 2)
            # re-load from mongo to see updated issue date and due date
            two = self.reebill_dao.load_reebill(acc, 2)
            self.assertEquals(True, self.state_db.is_issued(session, acc, 2))
            self.assertEquals(datetime.utcnow().date(), two.issue_date)
            self.assertEquals(two.issue_date + timedelta(30), two.due_date)
            self.assertIsInstance(two.bill_recipients, list)
            self.assertEquals(len(two.bill_recipients), 2)
            self.assertEquals(True, all(map(isinstance, two.bill_recipients,
                    [unicode]*len(two.bill_recipients))))

    def test_delete_reebill(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            # create sequence 0 template in mongo (will be needed below)
            template = example_data.get_reebill(account, 0)
            self.reebill_dao.save_reebill(template)
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(account, 0))

            customer = self.state_db.get_customer(session, account)
            session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=date(2012,1,1), period_end=date(2012,2,1), reebill=None))

            # create sequence 1 version 0, for January 2012, not issued
            b = self.process.roll_bill(session, template)

            # delete it
            self.process.delete_reebill(session, account, 1)
            self.assertEqual([], self.state_db.listSequences(session, account))
            self.assertRaises(NoSuchBillException, self.reebill_dao.load_reebill,
                    account, 1, version=0)


            # re-create it, attach it to a utility bill, and issue: can't be
            # deleted
            b = self.process.roll_bill(session, template)
            assert self.state_db.listSequences(session, account) == [1]
            
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = b.meters_for_service('gas')[0]
            b.set_meter_read_date('gas', meter['identifier'], date(2012,2,1), date(2012,1,1))
            self.reebill_dao.save_reebill(b)

            self.process.issue(session, account, 1)
            utilbills = self.state_db.utilbills_for_reebill(session, account, 1)
            
            assert len(utilbills) == 1
            u = utilbills[0]
            assert (u.customer.account, u.reebills[0].sequence) == (account, 1)
            b = self.reebill_dao.load_reebill(account, 1, version=0)
            self.assertRaises(IssuedBillError, self.process.delete_reebill,
                    session, account, 1)

            # create a new verison and delete it, returning to just version 0
            # (versioning requires a cprs)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(account, 1))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(account,
                    1))
            

            self.process.new_version(session, account, 1)
            assert self.state_db.max_version(session, account, 1) == 1
            assert not self.state_db.is_issued(session, account, 1)
            self.process.delete_reebill(session, account, 1)
            assert self.state_db.max_version(session, account, 1) == 0
            assert self.state_db.is_issued(session, account, 1)

            # original version should still be attached to utility bill
            # TODO this will have to change. see
            # https://www.pivotaltracker.com/story/show/31629749
            utilbills = self.state_db.list_utilbills(session, account)[0].all()
            assert len(utilbills) == 1; u = utilbills[0]
            self.assertEquals(account, u.reebills[0].customer.account)
            self.assertEquals(1, u.reebills[0].sequence)

    def test_adjustment(self):
        '''Test that adjustment from a correction is applied to (only) the
        earliest unissued bill.'''
        acc = '99999'

        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, acc)
            
            # save utility bills and rate structures in mongo and MySQL
            utilbill_ids, uprs_ids, cprs_ids = [], [], []
            for i in range(3):
                start, end = date(2012,1+i,1), date(2012,i+2,2)
                self.rate_structure_dao.save_rs(example_data.get_urs_dict())
                utilbill = example_data.get_utilbill_dict(acc, start=start,
                        end=end, utility='washgas', service='gas')
                uprs = example_data.get_uprs_dict()
                cprs = example_data.get_uprs_dict()
                utilbill = example_data.get_utilbill_dict(acc, start=start,
                        end=end, utility='washgas', service='gas')
                self.reebill_dao._save_utilbill(utilbill)
                self.rate_structure_dao.save_rs(uprs)
                self.rate_structure_dao.save_rs(cprs)
                utilbill_ids.append(str(utilbill['_id']))
                uprs_ids.append(str(uprs['_id']))
                cprs_ids.append(str(cprs['_id']))

                session.add(UtilBill(customer, UtilBill.Complete, 'gas',
                        str(utilbill['_id']), str(uprs['_id']),
                        str(cprs['_id']), period_start=start,
                        period_end=end, total_charges=100,
                        date_received=datetime.utcnow().date()))
            
            # create reebills #0 and #1
            zero = example_data.get_reebill(acc, 0)
            self.reebill_dao.save_reebill(zero)
            one = self.process.roll_bill(session, zero)

            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = one.meters_for_service('gas')[0]
            one.set_meter_read_date('gas', meter['identifier'], date(2012,2,1), date(2012,1,1))
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, one.sequence)
            one = self.reebill_dao.load_reebill(acc, one.sequence)

            two = self.process.roll_bill(session, one)
            # update the meter like the user normally would
            # This is required for process.new_version => fetch_bill_data.fetch_oltp_data
            meter = two.meters_for_service('gas')[0]
            two.set_meter_read_date('gas', meter['identifier'], date(2012,2,1), date(2012,1,1))
            self.reebill_dao.save_reebill(two)
            self.process.issue(session, acc, two.sequence)
            two = self.reebill_dao.load_reebill(acc, two.sequence)

            # issue reebill #1 and correct it with an adjustment of 100
            #self.process.issue(session, acc, 1)
            one_corrected = self.process.new_version(session, acc, 1)
            one_corrected.ree_charges = one.ree_charges + 100
            # this change must be saved in Mongo, because compute_bill() ->
            # get_unissued_corrections() loads the original and corrected bills
            # from Mongo and compares them to calculate the adjustment
            self.reebill_dao.save_reebill(one_corrected)

            self.process.compute_bill(session, one, two)
            #self.process.compute_bill(session, two, three)

            # only 'two' should get an adjustment ('one' is a correction, so it
            # can't have adjustments, and 'three' is not the earliest unissued
            # bill)
            self.assertEquals(0, one.total_adjustment)
            self.assertEquals(100, two.total_adjustment)


    def test_payment_application(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            # save reebills and rate structures in mongo
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 0))

            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,1,1), date(2012,2,1), 100,
                    datetime.utcnow().date())
            self.state_db.record_utilbill_in_database(session, acc, 'gas',
                    date(2012,2,1), date(2012,3,1), 100,
                    datetime.utcnow().date())
            
            zero = example_data.get_reebill(acc, 0)
            self.reebill_dao.save_reebill(zero)

            # create and issue #1
            one = self.process.roll_bill(session, zero)
            self.reebill_dao.save_reebill(one)
            self.process.issue(session, acc, 1, issue_date=date(2012,1,15))

            # create reebill #2
            two = self.process.roll_bill(session, one)

            # payment on jan. 20 gets applied to #2
            self.state_db.create_payment(session, acc, date(2012,1,20), 'A payment', 123.45)
            self.process.compute_bill(session, one, two)
            self.reebill_dao.save_reebill(two)
            self.assertEqual(Decimal('123.45'), two.payment_received)

            # make a correction on reebill #1: payment does not get applied to
            # #1 and does get applied to #2
            self.process.new_version(session, acc, 1)
            one = self.reebill_dao.load_reebill(acc, 1, version=1)
            self.process.compute_bill(session, zero, one)
            self.process.compute_bill(session, one, two)
            self.assertEqual(Decimal(0), one.payment_received)
            self.assertEqual(Decimal('123.45'), two.payment_received)


    def test_bind_and_compute_consistency(self):
        '''Tests that repeated binding and computing of a reebill do not
        cause it to change (a bug we have seen).'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # setup: reebill #1 to serve as predecessor for computing below
            # (must be saved in mongo only so ReebillDAO.get_first_bill_date_for_account works)
            one = example_data.get_reebill(acc, 1, version=0,
                    start=date(2012,1,1), end=date(2012,2,1))
            self.reebill_dao.save_reebill(one)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(acc, 1))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 1))

            for use_olap in (True, False):
                b = example_data.get_reebill(acc, 1, version=0,
                        start=date(2012,2,1), end=date(2012,3,1))
                # NOTE no need to save 'b' in mongo
                olap_id = 'MockSplinter ignores olap id'

                # bind & compute once to start. this change should be
                # idempotent.
                fbd.fetch_oltp_data(self.splinter, olap_id, b, use_olap=use_olap)
                self.process.compute_bill(session, one, b)

                # save original values
                # (more fields could be added here)
                hypo = b.hypothetical_total
                actual = b.actual_total
                ree = b.total_renewable_energy
                ree_value = b.ree_value
                ree_charges = b.ree_charges
                total = b.total
                balance_due = b.balance_due

                # this function checks that current values match the orignals
                def check():
                    # in approximate "causal" order
                    self.assertEqual(ree, b.total_renewable_energy)
                    self.assertEqual(actual, b.actual_total)
                    self.assertEqual(hypo, b.hypothetical_total)
                    self.assertEqual(ree_value, b.ree_value)
                    self.assertEqual(ree_charges, b.ree_charges)
                    self.assertEqual(total, b.total)
                    self.assertEqual(balance_due, b.balance_due)

                # this better succeed, since nothing was done
                check()

                # bind and compute repeatedly
                self.process.compute_bill(session, one, b)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                check()
                self.process.compute_bill(session, one, b)
                check()
                self.process.compute_bill(session, one, b)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                check()
                self.process.compute_bill(session, one, b)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                check()
                self.process.compute_bill(session, one, b)
                check()

    def test_choose_next_utilbills_bug(self):
        '''Regression test for
        https://www.pivotaltracker.com/story/show/48430769.'''
        account = '99999'
        with DBSession(self.state_db) as session:
            customer = self.state_db.get_customer(session, account)

            # add 2 utility bills to MySQL
            u1 = UtilBill(customer=customer, state=0, service='gas',
                    period_start=date(2013,1,1), period_end=date(2013,2,1),
                    reebill=None)
            u2 = UtilBill(customer=customer, state=0, service='gas',
                    period_start=date(2013,2,1), period_end=date(2013,3,1),
                    reebill=None)
            session.add(u1)
            session.add(u2)

            # save RS documents and reebill template to enable rolling
            self.rate_structure_dao.save_rs(example_data.get_urs_dict(account, 0))
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict(account, 0))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(account, 0))
            r0 = example_data.get_reebill(account, 0, start=date(2012,12,1),
                    end=date(2013,1,1))
        
            # add a reebill attached to 'u2' (billing start date 2013-02-01)
            self.reebill_dao.save_reebill(r0)
            r1 = self.process.roll_bill(session, r0, date(2013,2,1))

        # only u1 should be attached to the reebill
        self.assertEqual([], u1.reebills)
        self.assertNotEqual([], u2.reebills)

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

            # utility bill MySQL row and Mongo document should be created, with
            # an _id matching the MySQL row
            all_utilbills = session.query(UtilBill).all()
            self.assertEqual(1, len(all_utilbills))
            ub = all_utilbills[0]
            utilbill_doc = self.reebill_dao.load_doc_for_statedb_utilbill( ub)
            self.assertEqual(utilbill_doc['_id'], ObjectId(ub.document_id))

            # real utility bill document should look like the template, except
            # its _id should be different, it has different dates, and it will
            # have no charges (all charges in the template get removed because
            # the UPRS and CPRS are empty)
            self.assertDocumentsEqualExceptKeys(utilbill_doc,
                    utilbill_template, '_id', 'start', 'end', 'chargegroups')
            self.assertNotEqual(utilbill_doc['_id'],
                    ObjectId(utilbill_template['_id']))
            self.assertEquals(date(2013,1,1), utilbill_doc['start'].date())
            self.assertEquals(date(2013,2,1), utilbill_doc['end'].date())
            self.assertEquals({'All Charges': []}, utilbill_doc['chargegroups'])

            # UPRS and CPRS documents should be created and be empty
            uprs = self.rate_structure_dao.load_uprs_for_statedb_utilbill(ub)
            cprs = self.rate_structure_dao.load_cprs_for_statedb_utilbill(ub)
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
            self.process.create_new_utility_bill(session, '99999', 'washgas',
                    'gas', 'DC Non Residential Non Heat', date(2013,1,1),
                    date(2013,2,1))
            utilbill = session.query(UtilBill).one()
            self.process.create_first_reebill(session, utilbill)
            
            session.query(UtilBill).one() # verify there's only one
            reebill = session.query(ReeBill).one()
            self.assertEqual([utilbill], reebill.utilbills)
            self.assertEqual([reebill], utilbill.reebills)

            # TODO check reebill document contents
            # (this is already partially handled by
            # test_reebill.ReebillTest.test_get_reebill_doc_for_utilbills, but
            # should be done here as well.)

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
