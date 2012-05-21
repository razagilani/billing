#!/usr/bin/python
import sys
import unittest
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
from billing.processing.process import Process
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
from billing.processing.billupload import BillUpload
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
        print 'setUp'

        # this method runs before every test.
        # clear SQLAlchemy mappers so StateDB can be instantiated again
        sqlalchemy.orm.clear_mappers()

        # everything needed to create a Process object
        config_file = StringIO('''[runtime]
integrate_skyline_backend = true
[billimages]
bill_image_directory = /tmp/billimages
show_reebill_images = true
[billdb]
billpath = /db-dev/skyline/bills/
database = skyline
utilitybillpath = /db-dev/skyline/utilitybills/
collection = reebills
host = localhost
port = 27017
''')
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
        self.billupload = BillUpload(self.config, logging.getLogger('test'))
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

        #self.process = Process(self.config, self.state_db, self.reebill_dao,
                #self.rate_structure_dao, self.billupload, self.splinter,
                #self.monguru)

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
        try:
            session = self.state_db.session()
            process = Process(self.config, self.state_db, self.reebill_dao,
                    self.rate_structure_dao, self.billupload, self.splinter,
                    self.monguru)
 
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
                    self.rate_structure_dao, self.billupload, self.splinter,
                    self.monguru)

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
        process = Process(self.config, self.state_db, self.reebill_dao,
                self.rate_structure_dao, self.billupload, self.splinter,
                self.monguru)
        process.bindrs(bill1, None)

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
        print 'test_upload_utility_bill'
        with DBSession(self.state_db) as session:
            account, service = '99999', 'gas'
            process = Process(self.config, self.state_db, self.reebill_dao,
                    self.rate_structure_dao, self.billupload, self.splinter,
                    self.monguru)

            # one utility bill
            file1 = StringIO("Let's pretend this is a PDF")
            process.upload_utility_bill(session, account, service,
                    date(2012,1,1), date(2012,2,1), file1, 'january.pdf')
            bills = self.state_db.list_utilbills(session,
                    account)[0].filter(UtilBill.service==service).all()
            self.assertEqual(1, len(bills))
            self.assertEqual(UtilBill.Complete, bills[0].state)
            self.assertEqual(date(2012,1,1), bills[0].period_start)
            self.assertEqual(date(2012,2,1), bills[0].period_end)

            # second contiguous bill
            file2 = StringIO("Let's pretend this is a PDF")
            process.upload_utility_bill(session, account, service,
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
            process.upload_utility_bill(session, account, service,
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
            process.upload_utility_bill(session, account, service,
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

            session.commit()

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
