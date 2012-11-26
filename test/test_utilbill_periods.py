import unittest
import re
from datetime import date, datetime, timedelta

import example_data
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing import mongo
from billing.processing.session_contextmanager import DBSession
from billing.processing.process import Process, IssuedBillError
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
from decimal import Decimal
import MySQLdb

class UtilbillPeriodTest(TestCaseWithSetup):
    def setUp(self):
        super(UtilbillPeriodTest, self).setUp()
        session = self.state_db.session()
        session.add(Customer('Test1', 1, 0.5, 0.05))
        session.add(Customer('Test2', 2, 0.5, 0.05))
        session.add(Customer('Test3', 3, 0.5, 0.05))
        session.add(Customer('Test4', 4, 0.5, 0.05))
        session.commit()

    def test_single_unattached(self):
        # Add ten, nice, sequential gas bills
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = self.state_db.get_customer(session, account)
        self.assertEqual(customer.name, 'Test1')

        # Add ten utilbills "associated" to reebills
        reebills = [ReeBill(customer, x) for x in xrange(1, 11)]
        for r in reebills:
            r.issued = 1
        utilbills = [UtilBill(customer, 0, 'gas', dt+timedelta(days=30*x),\
                dt+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]
        for x in xrange(10):
            session.add(reebills[x])
            session.add(utilbills[x])

        # Add one utilbill that comes after the last utilbill from the above loop
        target_utilbill = UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30*10),\
                period_end=dt+timedelta(days=30*11),\
                reebill=None)
        session.add(target_utilbill)

        session.commit()
        session = self.state_db.session()

        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertListEqual(services, [ub.service for ub in utilbills])
        self.assertEqual(len(utilbills), 1)
        self.assertIsNotNone(utilbills[0])
        self.assertIsNone(utilbills[0].reebill)
        self.assertEqual(utilbills[0], target_utilbill)

    def test_multiple_unattached(self):
        # Add ten, nice, sequential gas bills
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = self.state_db.get_customer(session, account)
        self.assertEqual(customer.name, 'Test1')

        # Add ten utilbills "associated" to reebills
        reebills = [ReeBill(customer, x) for x in xrange(1, 11)]
        for r in reebills:
            r.issued = 1
        utilbills = [UtilBill(customer, 0, 'gas', dt+timedelta(days=30*x),\
                dt+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]
        for x in xrange(10):
            session.add(reebills[x])
            session.add(utilbills[x])

        # Add multiple utilbills that come after the last utilbill from the above loop
        target_utilbill = UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30*10),\
                period_end=dt+timedelta(days=30*11),\
                reebill=None)
        session.add(target_utilbill)
        session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30*11),\
                period_end=dt+timedelta(days=30*12),\
                reebill=None))
        session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30*12),\
                period_end=dt+timedelta(days=30*13),\
                reebill=None))

        session.commit()
        session = self.state_db.session()

        # Same tests
        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertListEqual(services, [ub.service for ub in utilbills])
        self.assertEqual(len(utilbills), 1)
        self.assertIsNotNone(utilbills[0])
        self.assertIsNone(utilbills[0].reebill)
        self.assertEqual(utilbills[0], target_utilbill)

    def test_legacy_unattached(self):
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = self.state_db.get_customer(session, account)
        self.assertEqual(customer.name, 'Test1')

        # 7 reebills, 10 utilbills
        reebills = [None, None, None] + [ReeBill(customer, x+1) for x in xrange(1, 8)]
        for r in reebills:
            if r is not None:
                r.issued = 1
        utilbills = [UtilBill(customer, 0, 'gas', dt+timedelta(days=30*x),\
                dt+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]

        # None entries in reebills won't go into the database, so they are stripped here
        reebills = reebills[3:]

        # Add ten utilbills "associated" to reebills, but the first three have no reebill association
        for r in reebills:
            session.add(r)
        for ub in utilbills:
            session.add(ub)

        # Add an unattached utilbill that comes after the last utilbill from the above loop
        target_utilbill = UtilBill(customer=customer, state=0, service='gas',\
                period_start=datetime.utcnow()+timedelta(days=30*10),\
                period_end=datetime.utcnow()+timedelta(days=30*11),\
                reebill=None)
        session.add(target_utilbill)

        session.commit()
        session = self.state_db.session()

        # Same tests
        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertListEqual(services, [ub.service for ub in utilbills])
        self.assertEqual(len(utilbills), 1)
        self.assertIsNotNone(utilbills[0])
        self.assertIsNone(utilbills[0].reebill)
        self.assertEqual(utilbills[0], target_utilbill)

    def test_multiple_services(self):
        account = 1
        services = ['gas', 'electric']
        dt_gas = date.today()
        dt_elec = date.today() + timedelta(days=9)
        session = self.state_db.session()
        customer = self.state_db.get_customer(session, account)
        self.assertEqual(customer.name, 'Test1')

        reebills = [ReeBill(customer, x+1) for x in xrange(1, 11)]
        for r in reebills:
            r.issued = 1
        gas_utilbills = [UtilBill(customer, 0, 'gas', dt_gas+timedelta(days=30*x),\
                dt_gas+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]
        elec_utilbills = [UtilBill(customer, 0, 'electric', dt_elec+timedelta(days=30*x),\
                dt_elec+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]

        # Add twenty utilbills "associated" to reebills, ten of gas and ten of electric
        # The gas and electric bills are on different time periods
        for x in xrange(10):
            session.add(reebills[x])
            session.add(gas_utilbills[x])
            session.add(elec_utilbills[x])

        target_gas_utilbill = UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt_gas+timedelta(days=30*10),\
                period_end=dt_gas+timedelta(days=30*11),\
                reebill=None)
        session.add(target_gas_utilbill)

        target_elec_utilbill = UtilBill(customer=customer, state=0, service='electric',\
                period_start=dt_elec+timedelta(days=30*10),\
                period_end=dt_elec+timedelta(days=30*11),\
                reebill=None)
        session.add(target_elec_utilbill)

        session.commit()
        session = self.state_db.session()

        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertListEqual(services, [ub.service for ub in utilbills])
        self.assertEqual(len(utilbills), 2)
        self.assertIsNotNone(utilbills[0])
        self.assertIsNotNone(utilbills[1])
        self.assertIsNone(utilbills[0].reebill)
        self.assertIsNone(utilbills[1].reebill)
        ub_dict = {ub.service: ub for ub in utilbills}
        self.assertEqual(ub_dict['gas'], target_gas_utilbill)
        self.assertEqual(ub_dict['electric'], target_elec_utilbill)

    def test_first_utilbill(self):
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = self.state_db.get_customer(session, account)
        self.assertEqual(customer.name, 'Test1')

        target_utilbill = UtilBill(customer=customer, state=0, service='gas',\
            period_start=dt, period_end=dt+timedelta(days=30), reebill=None)
        session.add(target_utilbill)

        session.commit()
        session = self.state_db.session()

        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertListEqual(services, [ub.service for ub in utilbills])
        self.assertEqual(len(utilbills), 1)
        self.assertIsNotNone(utilbills[0])
        self.assertIsNone(utilbills[0].reebill)
        self.assertEqual(utilbills[0], target_utilbill)


    def test_reebill_roll_selections(self):
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

            # Set hypo_utilbill to Utility Estimated, save it, and then we should be able to roll on it
            hypo_utilbill.state = UtilBill.UtilityEstimated;
            target_utilbill = session.merge(hypo_utilbill)

            reebill_2 = self.process.roll_bill(session, reebill_1)
            self.assertEqual(reebill_2.period_begin, target_utilbill.period_start)
            self.assertEqual(reebill_2.period_end, target_utilbill.period_end)

            self.process.issue(session, account, reebill_2.sequence)
            reebill_2 = self.reebill_dao.load_reebill(account, reebill_2.sequence)

            # Shift later_utilbill a few days into the future so that there is a time gap
            # after the last attached utilbill
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
            from nose.tools import set_trace
            set_trace()
            self.assertEqual(reebill_3.period_begin, target_utilbill.period_start)
            self.assertEqual(reebill_3.period_end, target_utilbill.period_end)



            # TODO: Test multiple services            
