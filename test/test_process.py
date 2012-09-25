#!/usr/bin/python
import sys
import os
import unittest
import operator
from StringIO import StringIO
import ConfigParser
import logging
import pymongo
import sqlalchemy
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from datetime import date, datetime, timedelta
from billing import dateutils, mongo
from billing.session_contextmanager import DBSession
from billing.dateutils import estimate_month, month_offset
from billing.processing import rate_structure
from billing.processing.process import Process, IssuedBillError
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
from billing.processing.billupload import BillUpload
from decimal import Decimal
from billing.dictutils import deep_map
import MySQLdb
from billing.mongo_utils import python_convert
from billing.test import example_data
from billing.test.fake_skyliner import FakeSplinter, FakeMonguru
from billing.nexus_util import NexusUtil
from billing.mongo import NoSuchBillException
from billing.processing import fetch_bill_data as fbd
from billing.exceptions import NotIssuable

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint
pformat = pprint.PrettyPrinter(indent=1).pformat

class ProcessTest(unittest.TestCase):
    # apparenty this is what you need to do if you override the __init__ method
    # of a TestCase
    #def __init__(self, methodName='runTest', param=None):
        #print '__init__'
        #super(ProcessTest, self).__init__(methodName)

    def setUp(self):
        print 'setUp'

        # this method runs before every test.
        # clear SQLAlchemy mappers so StateDB can be instantiated again
        sqlalchemy.orm.clear_mappers()

        # everything needed to create a Process object
        config_file = StringIO('''[runtime]
integrate_skyline_backend = true
[billimages]
bill_image_directory = /tmp/test/billimages
show_reebill_images = true
[billdb]
billpath = /tmp/test/db-test/skyline/bills/
database = test
utilitybillpath = /tmp/test/db-test/skyline/utilitybills/
utility_bill_trash_directory = /tmp/test/db-test/skyline/utilitybills-deleted
collection = reebills
host = localhost
port = 27017
''')
        self.config = ConfigParser.RawConfigParser()
        self.config.readfp(config_file)
        self.billupload = BillUpload(self.config, logging.getLogger('test'))
        self.rate_structure_dao = rate_structure.RateStructureDAO(**{
            'database': 'test',
            'collection': 'ratestructure',
            'host': 'localhost',
            'port': 27017
        })
        self.splinter = FakeSplinter(deterministic=True)
        
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

        # clear out tables in mysql test database (not relying on StateDB)
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

        self.reebill_dao = mongo.ReebillDAO(self.state_db, **{
            'billpath': '/db-dev/skyline/bills/',
            'database': 'test',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'test_reebills',
            'host': 'localhost',
            'port': 27017
        })

        self.nexus_util = NexusUtil('nexus')
        self.process = Process(self.state_db, self.reebill_dao,
                self.rate_structure_dao, self.billupload, self.nexus_util,
                self.splinter)

    def tearDown(self):
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
        acc = '99999'
        with DBSession(self.state_db) as session:
            # sequence 0 template
            self.reebill_dao.save_reebill(example_data.get_reebill(acc, 0))

            # bill 1: no late charge
            bill1 = example_data.get_reebill(acc, 1)
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
 
            # save bill1 in Mongo and MySQL, and its rate structure docs in
            # Mongo
            self.reebill_dao.save_reebill(bill1)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 1))
            self.state_db.new_rebill(session, bill1.account, bill1.sequence)

            # issue bill 1, so a later bill can have a late charge based on the
            # customer's failure to pay bill1 by its due date, i.e. 30 days
            # after bill1's issue date.
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
            bill0 = example_data.get_reebill(acc, 0)
            self.process.compute_bill(session, bill0, bill1)
 
            # but compute_bill() destroys bill1's balance_due, so reset it to
            # the right value, and save it in mongo
            bill1.balance_due = Decimal('100.')
            self.reebill_dao.save_reebill(bill1, force=True)

            # create second bill (not by rolling, because process.roll_bill()
            # is currently a huge mess, and get_late_charge() should be
            # insulated from that). note that bill1's late charge is set in
            # mongo by process.issue().
            bill2 = example_data.get_reebill(acc, 2)
            bill2.balance_due = Decimal('200.')
            # bill2's late_charge_rate is copied from MySQL during rolling, but
            # since bill2 is not created by rolling, it must be set explicitly.
            bill2.late_charge_rate = Decimal('0.34')

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
 
            # in order to get late charge of a 3rd bill, bill2 must be put into
            # mysql and computed (requires a rate structure)
            self.state_db.new_rebill(session, bill2.account, bill2.sequence)
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 2))
            self.process.compute_bill(session, bill1, bill2)
 
            # create a 3rd bill without issuing bill2. bill3 should have None
            # as its late charge for all dates
            bill3 = example_data.get_reebill(acc, 3)
            bill3.balance_due = Decimal('300.')
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
            self.process.issue(session, acc, 1, issue_date=date(2013,1,15))
            self.process.new_version(session, acc, 1)
            bill1_2 = self.reebill_dao.load_reebill(acc, 1, version=2)
            bill1_2.balance_due = 300
            self.reebill_dao.save_reebill(bill1_2)
            self.process.issue(session, acc, 1, issue_date=date(2013,3,15))
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

            # generic reebill
            bill1 = example_data.get_reebill('99999', 1)
            bill1.account = '99999'
            bill1.sequence = 1

            # make it have 2 services, 1 suspended
            # (create electric bill by duplicating gas bill)
            electric_bill = example_data.get_utilbill_dict('99999')
            electric_bill['_id']['service'] = 'electric'
            self.reebill_dao._save_utilbill(electric_bill)
            # TODO it's bad to directly modify reebill_dict
            bill1.reebill_dict['utilbills'].append({
                'service': 'electric',
                'utility': electric_bill['_id']['utility'],
                'start': electric_bill['_id']['start'],
                'end': electric_bill['_id']['end'],
            })
            bill1._utilbills.append(electric_bill)
            bill1.suspend_service('electric')
            self.assertEquals(['electric'], bill1.suspended_services)

            # save reebill in MySQL and Mongo
            self.state_db.new_rebill(session, bill1.account, bill1.sequence)
            self.reebill_dao.save_reebill(bill1)

            # save utilbills in MySQL
            self.state_db.record_utilbill_in_database(session, bill1.account,
                    bill1._utilbills[0]['_id']['service'],
                    bill1._utilbills[0]['_id']['start'],
                    bill1._utilbills[0]['_id']['end'], date.today())
            self.state_db.record_utilbill_in_database(session, bill1.account,
                    bill1._utilbills[1]['_id']['service'],
                    bill1._utilbills[1]['_id']['start'],
                    bill1._utilbills[1]['_id']['end'], date.today())

            self.process.attach_utilbills(session, bill1.account, bill1.sequence)

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
        assert len(bill1.services) == 1
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

        # compute charges in the bill using the rate structure created from the
        # above documents
        self.process.bindrs(bill1, None)

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
        print 'test_upload_utility_bill'
        with DBSession(self.state_db) as session:
            account, service = '99999', 'gas'
            #self.process = Process(self.config, self.state_db, self.reebill_dao,
                    #self.rate_structure_dao, self.billupload, self.splinter,
                    #self.monguru)

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
        print 'test_delete_utility_bill'
        account, service, = '99999', 'gas'
        start, end = date(2012,1,1), date(2012,2,1)

        with DBSession(self.state_db) as session:
            # create utility bill, and make sure it exists in db and filesystem
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

            # rate structures (needed to create new version)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999',
                1))

            # unassociated: deletion should succeed (row removed from database,
            # file moved to trash directory)
            new_path = self.process.delete_utility_bill(session, utilbill_id)
            self.assertEqual(0, self.state_db.list_utilbills(session, account)[1])
            self.assertFalse(os.access(bill_file_path, os.F_OK))
            self.assertRaises(IOError, self.billupload.get_utilbill_file_path,
                    account, start, end)
            self.assertTrue(os.access(new_path, os.F_OK))

            # re-upload the bill
            self.process.upload_utility_bill(session, account, service, start, end,
                    StringIO("test"), 'january.pdf')
            assert self.state_db.list_utilbills(session, account)[1] == 1
            bill_file_path = self.billupload.get_utilbill_file_path(account,
                    start, end)
            assert os.access(bill_file_path, os.F_OK)
            utilbill_id = session.query(UtilBill)\
                    .filter(UtilBill.customer_id == customer.id)\
                    .filter(UtilBill.period_start == start)\
                    .filter(UtilBill.period_end == end).one().id

            # associated with reebill that has not been issued: should fail
            # (association is currently done purely by date range)
            mongo_reebill = example_data.get_reebill(account, 1)
            mongo_reebill.set_utilbill_period_for_service(service, (start, end))
            mongo_reebill.period_begin = start
            mongo_reebill.period_end = end
            self.reebill_dao.save_reebill(mongo_reebill)
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill_id)

            # attached to reebill: should fail (this reebill is not created by
            # rolling, the way it's usually done, and only exists in MySQL)
            reebill = self.state_db.new_rebill(session, account, 1)
            utilbill = self.state_db.list_utilbills(session, account)[0].one()
            self.process.attach_utilbills(session, account, 1)
            assert utilbill.reebill == reebill
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill_id)

            # deletion should fail if any version of a reebill has an
            # association with the utility bill. create a new version of the
            # reebill that does not have this utilbill.
            self.reebill_dao.save_reebill(example_data.get_reebill(account, 0))
            self.process.issue(session, account, 1)
            self.process.new_version(session, account, 1)
            mongo_reebill.version = 1
            mongo_reebill.set_utilbill_period_for_service(service, (start -
                    timedelta(days=365), end - timedelta(days=365)))
            mongo_reebill.period_begin = start - timedelta(days=365)
            mongo_reebill.period_end = end - timedelta(days=365)
            self.reebill_dao.save_reebill(mongo_reebill)
            self.assertRaises(ValueError, self.process.delete_utility_bill,
                    session, utilbill_id)
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
        zero = example_data.get_reebill('99999', 0, version=0)
        one = example_data.get_reebill('99999', 1, version=0)
        self.reebill_dao.save_reebill(zero)
        self.reebill_dao.save_reebill(one)
        self.rate_structure_dao.save_rs(example_data.get_urs_dict())
        self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
        self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 1))

        # TODO creating new version of 1 should fail until it's issued

        # issue reebill 1
        with DBSession(self.state_db) as session:
            self.state_db.new_rebill(session, '99999', 1)
            self.process.issue(session, '99999', 1, issue_date=date(2012,1,1))
            session.commit()

        # create new version of 1
        with DBSession(self.state_db) as session:
            new_bill = self.process.new_version(session, '99999', 1)
            session.commit()
        self.assertEqual('99999', new_bill.account)
        self.assertEqual(1, new_bill.sequence)
        self.assertEqual(1, new_bill.version)
        self.assertEqual(1, self.state_db.max_version(session, '99999', 1))
        # new version of CPRS(s) should also be created, so rate structure
        # should be loadable
        for s in new_bill.services:
            self.assertNotEqual(None,
                    self.rate_structure_dao.load_cprs('99999', 1,
                    new_bill.version, new_bill.utility_name_for_service(s),
                    new_bill.rate_structure_name_for_service(s)))
            self.assertNotEqual(None,
                    self.rate_structure_dao.load_rate_structure(new_bill, s))

    def test_correction_issuing(self):
        '''Tests get_unissued_corrections(), get_total_adjustment(), and
        issue_corrections().'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # reebills 1-4, 1-3 issued
            zero = example_data.get_reebill(acc, 0)
            one = example_data.get_reebill(acc, 1)
            two = example_data.get_reebill(acc, 2)
            three = example_data.get_reebill(acc, 3)
            four = example_data.get_reebill(acc, 4)
            zero.ree_charges = 100
            one.ree_charges = 100
            two.ree_charges = 100
            three.ree_charges = 100
            four.ree_charges = 100
            self.reebill_dao.save_reebill(zero)
            self.reebill_dao.save_reebill(one)
            self.reebill_dao.save_reebill(two)
            self.reebill_dao.save_reebill(three)
            self.reebill_dao.save_reebill(four)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 1))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 2))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 3))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 4))
            self.state_db.new_rebill(session, acc, 1)
            self.state_db.new_rebill(session, acc, 2)
            self.state_db.new_rebill(session, acc, 3)
            self.state_db.new_rebill(session, acc, 4)
            self.process.issue(session, acc, 1)
            self.process.issue(session, acc, 2)
            self.process.issue(session, acc, 3)

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
            # 2 reebills, 1 issued 40 days ago and unpaid (so it's 10 days late)
            zero = example_data.get_reebill(acc, 0) # template
            one = example_data.get_reebill(acc, 1)
            two0 = example_data.get_reebill(acc, 2)
            one.balance_due = 100
            two0.balance_due = 100
            self.reebill_dao.save_reebill(zero)
            self.reebill_dao.save_reebill(one)
            self.reebill_dao.save_reebill(two0)
            self.state_db.new_rebill(session, acc, 1)
            self.state_db.new_rebill(session, acc, 2)
            self.process.issue(session, acc, 1,
                    issue_date=datetime.utcnow().date() - timedelta(40))

            # save rate structures for the bills
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 1))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict('99999', 2))

            # bind & compute 2nd reebill
            # (it needs energy data only so its correction will have the same
            # energy in it; only the late charge will differ)
            two0 = self.reebill_dao.load_reebill(acc, 2)
            two0.late_charge_rate = .5
            fbd.fetch_oltp_data(self.splinter, self.nexus_util.olap_id(acc),
                    two0)

            # if given a late_charge_rate > 0, 2nd reebill should have a late charge
            self.process.compute_bill(session, one, two0)
            self.assertEqual(50, two0.late_charges)

            # save and issue 2nd reebill so a new version can be created
            self.reebill_dao.save_reebill(two0)
            self.process.issue(session, acc, two0.sequence)

            # add a payment of $80 30 days ago (10 days after 1st reebill was
            # issued). the late fee above is now wrong; it should be 50% of $20
            # instead of 50% of the entire $100.
            self.state_db.create_payment(session, acc, datetime.utcnow().date()
                    - timedelta(30), 'backdated payment', 80)

            # now a new version of the 2nd reebill should have a different late
            # charge: $10 instead of $50.
            self.process.new_version(session, acc, 2)
            two1 = self.reebill_dao.load_reebill(acc, 2)
            self.assertEqual(10, two1.late_charges)

            # that difference should show up as an error
            corrections = self.process.get_unissued_corrections(session, acc)
            assert len(corrections) == 1
            self.assertEquals((2, 1, -40), corrections[0])

    def test_roll(self):
        '''Tests Process.roll_bill, which modifies a MongoReebill to convert it
        into its sequence successor, and copies the CPRS in Mongo. (The bill
        itself is not saved in any database.)'''
        account = '99999'
        with DBSession(self.state_db) as session:
            b1 = example_data.get_reebill(account, 1)
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(account, 1))
            b2 = self.process.roll_bill(session, b1)

    def test_issue(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            # two bills
            one = example_data.get_reebill(acc, 1)
            two = example_data.get_reebill(acc, 2)
            self.reebill_dao.save_reebill(one)
            self.reebill_dao.save_reebill(two)
            self.state_db.new_rebill(session, acc, 1)
            self.state_db.new_rebill(session, acc, 2)

            # neither should be issued yet
            self.assertEquals(False, self.state_db.is_issued(session, acc, 1))
            self.assertEquals(None, one.issue_date)
            self.assertEquals(None, one.due_date)
            self.assertEquals(False, self.state_db.is_issued(session, acc, 2))
            self.assertEquals(None, two.issue_date)
            self.assertEquals(None, two.due_date)

            # two should not be issuable until one is issued
            self.assertRaises(NotIssuable, self.process.issue, session, acc, 2)

            # issue one
            self.process.issue(session, acc, 1)
            # re-load from mongo to see updated issue date and due date
            one = self.reebill_dao.load_reebill(acc, 1)
            self.assertEquals(True, self.state_db.is_issued(session, acc, 1))
            self.assertEquals(datetime.utcnow().date(), one.issue_date)
            self.assertEquals(one.issue_date + timedelta(30), one.due_date)

            # issue two
            self.process.issue(session, acc, 2)
            # re-load from mongo to see updated issue date and due date
            two = self.reebill_dao.load_reebill(acc, 2)
            self.assertEquals(True, self.state_db.is_issued(session, acc, 2))
            self.assertEquals(datetime.utcnow().date(), two.issue_date)
            self.assertEquals(two.issue_date + timedelta(30), two.due_date)

    def test_delete_reebill(self):
        account = '99999'
        with DBSession(self.state_db) as session:
            # create sequence 0 template in mongo (will be needed below)
            self.reebill_dao.save_reebill(example_data.get_reebill(account, 0))

            # create sequence 1 version 0, for January 2012, not issued
            self.state_db.new_rebill(session, account, 1)
            b = example_data.get_reebill(account, 1, version=0)
            b.set_utilbill_period_for_service('gas', (date(2012,1,1),
                    date(2012,2,1)))
            b.period_begin = date(2012,1,1) # must set reebill period separately from utilbill period
            b.period_end = date(2012,2,1)
            self.reebill_dao.save_reebill(b)

            # delete it
            self.process.delete_reebill(session, account, 1)
            self.assertEqual([], self.state_db.listSequences(session, account))
            self.assertRaises(NoSuchBillException, self.reebill_dao.load_reebill,
                    account, 1, version=0)

            # re-create it, attach it to a utility bill, and issue: can't be
            # deleted
            self.state_db.new_rebill(session, account, 1)
            b = example_data.get_reebill(account, 1, version=0)
            b.set_utilbill_period_for_service('gas', (date(2012,1,1),
                    date(2012,2,1)))
            b.period_begin = date(2012,1,1) # must set reebill period separately from utilbill period
            b.period_end = date(2012,2,1)
            self.reebill_dao.save_reebill(b)
            assert self.state_db.listSequences(session, account) == [1]
            self.process.upload_utility_bill(session, account, 'gas', date(2012,1,1),
                    date(2012,1,1), StringIO(), 'utilbill.pdf')
            #self.state_db.record_utilbill_in_database(session, account, 'gas',
                    #date(2012,1,1), date(2012,2,1), datetime.utcnow().date())
            self.process.attach_utilbills(session, account, 1)
            self.process.issue(session, account, 1)
            utilbills = self.state_db.utilbills_for_reebill(session, account, 1)
            print utilbills
            assert len(utilbills) == 1; u = utilbills[0]
            assert (u.customer.account, u.reebill.sequence) == (account, 1)
            self.reebill_dao.load_reebill(account, 1, version=0)
            self.assertRaises(IssuedBillError, self.process.delete_reebill,
                    session, account, 1)

            # create a new verison and delete it, returning to just version 0
            # (versioning requires a cprs)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
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
            self.assertEquals(account, u.reebill.customer.account)
            self.assertEquals(1, u.reebill.sequence)

    def test_adjustment(self):
        '''Test that adjustment from a correction is applied to (only) the
        earliest unissued bill.'''
        acc = '99999'

        with DBSession(self.state_db) as session:
            # save reebills and rate structures in mongo
            self.reebill_dao.save_reebill(example_data.get_reebill(acc, 0))
            one = example_data.get_reebill(acc, 1)
            self.reebill_dao.save_reebill(one)
            self.reebill_dao.save_reebill(example_data.get_reebill(acc, 2))
            self.reebill_dao.save_reebill(example_data.get_reebill(acc, 3))
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 1))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 2))
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 3))

            # save reebills in mysql
            self.state_db.new_rebill(session, acc, 1)
            self.state_db.new_rebill(session, acc, 2)
            self.state_db.new_rebill(session, acc, 3)

            # load out of mongo
            one = self.reebill_dao.load_reebill(acc, 1)
            two = self.reebill_dao.load_reebill(acc, 2)
            three = self.reebill_dao.load_reebill(acc, 3)

            # issue reebill #1 and correct it with an adjustment of 100
            self.process.issue(session, acc, 1)
            one_corrected = self.process.new_version(session, acc, 1)
            one_corrected.ree_charges = one.ree_charges + 100
            # this change must be saved in Mongo, because compute_bill() ->
            # get_unissued_corrections() loads the original and corrected bills
            # from Mongo and compares them to calculate the adjustment
            self.reebill_dao.save_reebill(one_corrected)

            self.process.compute_bill(session, one, two)
            self.process.compute_bill(session, two, three)

            # only 'two' should get an adjustment ('one' is a correction, so it
            # can't have adjustments, and 'three' is not the earliest unissued
            # bill)
            self.assertEquals(0, one.total_adjustment)
            self.assertEquals(100, two.total_adjustment)
            self.assertEquals(0, three.total_adjustment)


    def test_bind_and_compute_consistency(self):
        '''Tests that repeated binding and computing of a reebill do not
        cause it to change (a bug we have seen).'''
        acc = '99999'
        with DBSession(self.state_db) as session:
            # setup: sequence-0 template, rate structure documents
            zero = example_data.get_reebill(acc, 0)
            self.reebill_dao.save_reebill(zero)
            self.state_db.new_rebill(session, acc, 1)
            self.rate_structure_dao.save_rs(example_data.get_urs_dict())
            self.rate_structure_dao.save_rs(example_data.get_uprs_dict())
            self.rate_structure_dao.save_rs(example_data.get_cprs_dict(acc, 1))

            for use_olap in (True, False):
                b = example_data.get_reebill(acc, 1, version=0)
                self.reebill_dao.save_reebill(b)
                olap_id = 'FakeSplinter ignores olap id'

                # bind & compute once to start. this change should be
                # idempotent.
                fbd.fetch_oltp_data(self.splinter, olap_id, b, use_olap=use_olap)
                self.process.compute_bill(session, zero, b)

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
                self.process.compute_bill(session, zero, b)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                check()
                self.process.compute_bill(session, zero, b)
                check()
                self.process.compute_bill(session, zero, b)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                check()
                self.process.compute_bill(session, zero, b)
                check()
                fbd.fetch_oltp_data(self.splinter, olap_id, b)
                check()
                self.process.compute_bill(session, zero, b)
                check()

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
