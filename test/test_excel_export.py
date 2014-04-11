#!/usr/bin/env python2
from billing.processing.excel_export import Exporter
from billing.processing.state import StateDB, ReeBill, Payment, UtilBill
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

def createMockUtilBill():
    ub = mock.create_autospec(UtilBill)
    return ub

def createMockReebill():
    rb = mock.create_autospec(spec=ReeBill)
    rb.issued = 1
    rb.sequence = 1
    rb.version = 0
    rb.issue_date = date(2013, 4, 1)
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
    rb.utilbills = [createMockUtilBill()]
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
        correct_data=[('10003', 1, 0, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2013-04-01', '2011-11-12', '2011-12-14', '980.33', '743.49', '4.30', '2.20', None, '2011-11-30', '400.13', '0.00', '62.29', '122.20', 32.2, '5.01', '', '-117.90', '-117.90', '188.20', '1.26'),
                      ('10003', 1, 0, None, None, None, None, None, None, None, None, None, None, '2011-12-01', '13.37', None, None, None, None, None, None, None, None, None, None),
                      ('10004', 1, 0, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2013-04-01', '2011-11-12', '2011-12-14', '980.33', '743.49', '4.30', '2.20', None, None, None, '0.00', '62.29', '122.20', 32.2, '5.01', '', '-117.90', '-117.90', '188.20', '1.26')]
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

    def test_get_account_charges_sheet(self):
        self.mock_StateDB.listSequences.return_value = [1]
        self.mock_ReebillDAO.load_reebill.return_value = \
            example_data.get_reebill('10003',1,version=0)
        self.mock_StateDB.get_reebill.return_value = createMockReebill()
        self.mock_ReebillDAO._load_utilbill_by_id.return_value =\
            example_data.get_utilbill_dict('10003', start=date(2011,12,15),
                                           end=date(2012,1,14))
        with self.mock_session(self.mock_StateDB) as session:
            dataset=self.exp.get_account_charges_sheet(session, '10003')
        self.assertEqual(len(dataset), 1)
        for row in dataset:
            self.assertEqual(row, ('10003', 1, '2011-11-12', '2011-12-14', '2011-11', 'No', '58.34', '220.16', '4.50', '574.05', '23.14', '22.95', '55.49', '10.50', '11.20', '3.37', '17.19', '43.70', '164.92', '23.14', '430.02', '42.08', '7.87', '11.20', '743.49', '980.33', '236.84', '0.00'))
        self.assertEqual(dataset.headers, ['Account', 'Sequence', 'Period Start', 'Period End', 'Billing Month', 'Estimated', u'All Charges: Delivery tax (hypothetical)', u'All Charges: Distribution charge for all therms (hypothetical)', u'All Charges: DC Energy Assistance Trust Fund (hypothetical)', u'All Charges: Purchased Gas Charge (hypothetical)', u'All Charges: Peak Usage Charge (hypothetical)', u'All Charges: DC Rights-of-Way Fee (hypothetical)', u'All Charges: Sales tax (hypothetical)', u'All Charges: Sustainable Energy Trust Fund (hypothetical)', u'All Charges: System Charge (hypothetical)', u'All Charges: DC Energy Assistance Trust Fund (actual)', u'All Charges: DC Rights-of-Way Fee (actual)', u'All Charges: Delivery tax (actual)', u'All Charges: Distribution charge for all therms (actual)', u'All Charges: Peak Usage Charge (actual)', u'All Charges: Purchased Gas Charge (actual)', u'All Charges: Sales tax (actual)', u'All Charges: Sustainable Energy Trust Fund (actual)', u'All Charges: System Charge (actual)', ': Actual Total', ': Hypothetical Total', ': Energy Offset Value (Hypothetical - Actual)', ': Skyline Late Charge'])
        self.assertEqual(dataset.title, '10003')
