import unittest
from datetime import date, datetime, timedelta

import example_data as data
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
        customer = session.query(Customer).filter(Customer.account == account).one()
        self.assertEqual(customer.name, 'Test1')

        # Add ten utilbills "associated" to reebills
        reebills = [ReeBill(customer, x) for x in xrange(1, 11)]
        utilbills = [UtilBill(customer, 0, 'gas', dt+timedelta(days=30*x),\
                dt+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]
        for x in xrange(10):
            session.add(reebills[x])
            session.add(utilbills[x])

        # Add one utilbill that comes after the last utilbill from the above loop
        session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30*10),\
                period_end=dt+timedelta(days=30*11),\
                reebill=None))

        session.commit()
        session = self.state_db.session()

        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertNotIn('electric', utilbills)
        self.assertEqual(len(utilbills.keys()), 1)
        self.assertIsNotNone(utilbills['gas']['utilbill'])
        self.assertIsNotNone(utilbills['gas']['time_gap'])
        self.assertLessEqual(utilbills['gas']['time_gap'], timedelta(days=1))
        self.assertEqual(utilbills['gas']['utilbill'].reebill, None)

        ubids_to_attach = self.process.choose_next_utilbills(session, utilbills, services)
        self.assertListEqual(ubids_to_attach, [utilbills['gas']['utilbill'].id])

    def test_multiple_unattached(self):
        # Add ten, nice, sequential gas bills
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = session.query(Customer).filter(Customer.account == account).one()
        self.assertEqual(customer.name, 'Test1')

        # Add ten utilbills "associated" to reebills
        reebills = [ReeBill(customer, x) for x in xrange(1, 11)]
        utilbills = [UtilBill(customer, 0, 'gas', dt+timedelta(days=30*x),\
                dt+timedelta(days=30*(x+1)), reebill=reebills[x]) for x in xrange(0, 10)]
        for x in xrange(10):
            session.add(reebills[x])
            session.add(utilbills[x])

        # Add multiple utilbills that come after the last utilbill from the above loop
        session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30*10),\
                period_end=dt+timedelta(days=30*11),\
                reebill=None))
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
        self.assertNotIn('electric', utilbills)
        self.assertEqual(len(utilbills.keys()), 1)
        self.assertIsNotNone(utilbills['gas']['utilbill'])
        self.assertIsNotNone(utilbills['gas']['time_gap'])
        self.assertLessEqual(utilbills['gas']['time_gap'], timedelta(days=1))
        self.assertIsNone(utilbills['gas']['utilbill'].reebill)
        self.assertAlmostEqual(utilbills['gas']['utilbill'].period_start, dt+timedelta(days=30*10), delta=timedelta(days=1))

        ubids_to_attach = self.process.choose_next_utilbills(session, utilbills, services)
        self.assertListEqual(ubids_to_attach, [utilbills['gas']['utilbill'].id])

    def test_legacy_unattached(self):
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = session.query(Customer).filter(Customer.account == account).one()
        self.assertEqual(customer.name, 'Test1')

        # 7 reebills, 10 utilbills
        reebills = [None, None, None] + [ReeBill(customer, x+1) for x in xrange(1, 8)]
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
        session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=datetime.utcnow()+timedelta(days=30*10),\
                period_end=datetime.utcnow()+timedelta(days=30*11),\
                reebill=None))

        session.commit()
        session = self.state_db.session()

        # Same tests
        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertNotIn('electric', utilbills)
        self.assertEqual(len(utilbills.keys()), 1)
        self.assertIsNotNone(utilbills['gas']['utilbill'])
        self.assertIsNotNone(utilbills['gas']['time_gap'])
        self.assertLessEqual(utilbills['gas']['time_gap'], timedelta(days=1))
        self.assertIsNone(utilbills['gas']['utilbill'].reebill)
        self.assertAlmostEqual(utilbills['gas']['utilbill'].period_start, dt+timedelta(days=30*10), delta=timedelta(days=1))

        ubids_to_attach = self.process.choose_next_utilbills(session, utilbills, services)
        self.assertListEqual(ubids_to_attach, [utilbills['gas']['utilbill'].id])

    def test_multiple_services(self):
        account = 1
        services = ['gas', 'electric']
        dt_gas = date.today()
        dt_elec = date.today() + timedelta(days=9)
        session = self.state_db.session()
        customer = session.query(Customer).filter(Customer.account == account).one()
        self.assertEqual(customer.name, 'Test1')

        reebills = [ReeBill(customer, x+1) for x in xrange(1, 11)]
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

        session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt_gas+timedelta(days=30*10),\
                period_end=dt_gas+timedelta(days=30*11),\
                reebill=None))
        session.add(UtilBill(customer=customer, state=0, service='electric',\
                period_start=dt_elec+timedelta(days=30*10),\
                period_end=dt_elec+timedelta(days=30*11),\
                reebill=None))

        session.commit()
        session = self.state_db.session()

        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertIn('gas', utilbills)
        self.assertIn('electric', utilbills)
        self.assertEqual(len(utilbills.keys()), 2)
        self.assertIsNotNone(utilbills['gas']['utilbill'])
        self.assertEqual(utilbills['gas']['utilbill'].reebill, None)
        self.assertIsNotNone(utilbills['electric']['utilbill'])
        self.assertEqual(utilbills['electric']['utilbill'].reebill, None)
        self.assertIsNotNone(utilbills['gas']['time_gap'])
        self.assertIsNotNone(utilbills['electric']['time_gap'])
        self.assertLessEqual(utilbills['gas']['time_gap'], timedelta(days=1))
        self.assertLessEqual(utilbills['electric']['time_gap'], timedelta(days=1))
        self.assertAlmostEqual(utilbills['gas']['utilbill'].period_start, dt_gas+timedelta(days=30*10), delta=timedelta(days=1))
        self.assertAlmostEqual(utilbills['electric']['utilbill'].period_start, dt_elec+timedelta(days=30*10), delta=timedelta(days=1))

        ubids_to_attach = self.process.choose_next_utilbills(session, utilbills, services)
        self.assertListEqual(ubids_to_attach, [utilbills['gas']['utilbill'].id, utilbills['electric']['utilbill'].id])

    def test_first_utilbill(self):
        account = 1
        services = ['gas']
        dt = date.today()
        session = self.state_db.session()
        customer = session.query(Customer).filter(Customer.account == account).one()
        self.assertEqual(customer.name, 'Test1')

        session.add(UtilBill(customer=customer, state=0, service='gas',\
            period_start=dt, period_end=dt+timedelta(days=30), reebill=None))

        session.commit()
        session = self.state_db.session()

        utilbills = self.state_db.choose_next_utilbills(session, account, services)
        self.assertIn('gas', utilbills)
        self.assertNotIn('electric', utilbills)
        self.assertIsNotNone(utilbills['gas']['utilbill'])
        self.assertIsNone(utilbills['gas']['time_gap'])
        self.assertAlmostEqual(utilbills['gas']['utilbill'].period_start, dt, delta=timedelta(days=1))
        
        ubids_to_attach = self.process.choose_next_utilbills(session, utilbills, services)
        self.assertEqual(len(ubids_to_attach), 1)

    def test_reebill_roll_selections(self):
        account = '99999'
        dt = date.today()

        with DBSession(self.state_db) as session:
            customer = session.query(Customer).filter(Customer.account == account).one()
            reebill = ReeBill(customer, 1)
            #session.add(ReeBill(customer, 1))
            session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt, period_end=dt+timedelta(days=30), reebill=reebill))
            session.add(UtilBill(customer=customer, state=0, service='gas',\
                period_start=dt+timedelta(days=30), period_end=dt+timedelta(days=60), reebill=None))
            b1 = data.get_reebill(account, 1)
            self.rate_structure_dao.save_rs(data.get_cprs_dict(account, 1))
            b2 = self.process.roll_bill(session, b1)
            
            self.assertEqual(b2.period_begin, dt+timedelta(days=30))
            self.assertEqual(b2.period_end, dt+timedelta(days=60))
