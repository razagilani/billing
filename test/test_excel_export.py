#!/usr/bin/env python2
from billing.processing.excel_export import Exporter
from billing.processing.state import StateDB, ReeBill, Payment
from billing.processing.mongo import ReebillDAO
from billing.processing.session_contextmanager import DBSession
from datetime import date, datetime
from billing.test import example_data
import unittest, mock

def load_reebills_for():
    return [example_data.get_reebill('10003',1,version=0)]
def load_utilbills():
    return [example_data.get_utilbill_dict('10003',start=date(2011,11,12), end=date(2011,12,14)),
            example_data.get_utilbill_dict('10003',start=date(2011,12,15), end=date(2012,1,14))]

def payments():
    mock_Payment = mock.create_autospec(Payment)
    mock_Payment.date_received = datetime(2011, 11, 30)
    mock_Payment.date_applied = date(2011, 11, 30)
    mock_Payment.credit = 400.13
    mock_Payment2 = mock.create_autospec(Payment)
    mock_Payment2.date_received = datetime(2011, 12, 1)
    mock_Payment2.date_applied = date(2011, 12, 1)
    mock_Payment2.credit = 13.37
    return [mock_Payment, mock_Payment2]
def listAccounts():
    return ['10003','10004']
# def get_reebill(self, session, account, sequence, version):
#     return MockStateReebill(None,1,0)

def createMockReebill():
    rb = mock.create_autospec(spec=ReeBill)
    rb.issued = 1
    rb.sequence = 1
    rb.version = 0
    rb.issue_date = date(2013,4,1)
    rb.balance_due = 5.01
    rb.balance_forward = 62.29
    rb.discount_rate = 0.1
    rb.total_adjustment = 0.0
    rb.manual_adjustment = 0.0
    rb.payment_received = None
    rb.prior_balance = 2.20
    rb.ree_value = 4.3
    rb.ree_savings = 2.22
    rb.late_charge = 32.20
    rb.ree_charge = 122.20
    return rb


class ExporterTest(unittest.TestCase):

    def setUp(self):
        #Set up the mock
        self.mock_StateDB = mock.create_autospec(StateDB)
        self.mock_ReebillDAO = mock.create_autospec(ReebillDAO)
        self.mock_session = mock.create_autospec(DBSession)
        self.exp = Exporter(self.mock_StateDB, self.mock_ReebillDAO)

    def test_get_reebill_details_dataset(self):
        #Set up the mock
        self.mock_StateDB.listAccounts.return_value = listAccounts()
        self.mock_StateDB.payments.return_value = payments()
        self.mock_StateDB.get_reebill.return_value = createMockReebill()
        self.mock_ReebillDAO.load_reebills_for.return_value = load_reebills_for()

        with self.mock_session(self.mock_StateDB) as session:
            dataset=self.exp.get_export_reebill_details_dataset(session, None, None)
        correct_data=[('10003', 1, 0, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2013-04-01', '2011-11-12', '2011-12-14', 17.25, 17.26, 4.3, 2.2, None, '2011-11-30', 400.13, 0.0, 62.29, 122.2, 32.2, 5.01, '', -117.9, -117.9, 188.20197727, -5.3134404563960955e-05),
                      ('10003', 1, 0, None, None, None, None, None, None, None, None, None, None, '2011-12-01', 13.37, None, None, None, None, None, None, None, None, None, None),
                      ('10004', 1, 0, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2013-04-01', '2011-11-12', '2011-12-14', 17.25, 17.26, 4.3, 2.2, None, None, None, 0.0, 62.29, 122.2, 32.2, 5.01, '', -117.9, -117.9, 188.20197727, -5.3134404563960955e-05)]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

    def test_get_energy_usage_sheet(self):
        #Setup Mock
        self.mock_ReebillDAO.load_utilbills.return_value=load_utilbills()
        dataset = self.exp.get_energy_usage_sheet(None,'10003')
        correct_data = [('10003', u'DC Non Residential Non Heat', 561.9, u'therms', '2011-11-12', '2011-12-14', 3.37, 17.19, 43.7, 164.92, 23.14, 430.02, 42.08, 7.87, 11.2),
            ('10003', u'DC Non Residential Non Heat', 561.9, u'therms', '2011-12-15', '2012-01-14', 3.37, 17.19, 43.7, 164.92, 23.14, 430.02, 42.08, 7.87, 11.2),]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))