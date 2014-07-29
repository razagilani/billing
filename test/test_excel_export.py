#!/usr/bin/env python2
from copy import deepcopy
from billing.processing.excel_export import Exporter
from billing.processing.state import (StateDB, ReeBill, Payment,
        ReeBillCharge, Reading, UtilBill, Address, Charge)
from billing.processing.mongo import ReebillDAO
from billing.processing.session_contextmanager import DBSession
from datetime import date, datetime
from billing.test import example_data
import unittest
import mock

def load_reebills_for():
    return [example_data.get_reebill('10003',1,version=0)]
def load_utilbills():
    return [example_data.get_utilbill_dict('10003',start=date(2011,11,12), end=date(2011,12,14)),
            example_data.get_utilbill_dict('10003',start=date(2011,12,15), end=date(2012,1,14))]

def payments():
    mock_Payment = mock.create_autospec(Payment)
    mock_Payment.date_received = datetime(2011, 11, 30)
    mock_Payment.date_applied = datetime(2011, 11, 30)
    mock_Payment.credit = 400.13
    mock_Payment2 = mock.create_autospec(Payment)
    mock_Payment2.date_received = datetime(2011, 12, 1)
    mock_Payment2.date_applied = datetime(2011, 12, 1)
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
    rb = mock.create_autospec(spec=ReeBill, instance=True)
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
    rb.total = 743.49
    rb.charges = [ReeBillCharge(rb, *args) for args in [
        (u"SYSTEM_CHARGE", u"System Charge", u'All Charges', 1, 1, u'dollars',
         11.2, 11.2, 11.2, 11.2),
        (u"DISTRIBUTION_CHARGE", u"Distribution charge for all therms",
         u'All Charges', 750.10197727, 750.10197727, u'dollars', 0.2935, 0.2935,
         220.16, 220.16),
        (u"PGC", u"Purchased Gas Charge",
         u'All Charges', 750.10197727, 750.10197727, u'therms', 0.7653, 0.7653,
         574.05, 574.05),
        (u"PUC", u"Peak Usage Charge",
         u'All Charges', 1, 1, u'kWh', 23.14, 23.14,
         23.14, 23.14),
        (u"RIGHT_OF_WAY", u"DC Rights-of-Way Fee",
         u'All Charges', 750.10197727, 750.10197727, u'therms', 0.03059, 0.03059,
         22.95, 22.95),
        (u"SETF", u"Sustainable Energy Trust Fund",
         u'All Charges', 750.10197727, 750.10197727, u'therms', 0.01399, 0.01399,
         10.5, 10.5),
        (u"EATF", u"DC Energy Assistance Trust Fund",
         u'All Charges', 750.10197727, 750.10197727, u'therms', 0.006, 0.006,
         4.5, 4.5),
        (u"SALES_TAX", u"Sales tax",
         u'All Charges', 924.84, 924.84, u'dollars', 0.06, 0.06,
         55.49, 55.49),
        (u"DELIVERY_TAX", u"Delivery tax",
         u'All Charges', 750.10197727, 750.10197727, u'therms', 0.07777, 0.07777,
         58.34, 58.34)]]
    rb.readings = [Reading('REG_TOTAL', 'Energy Sold', 561.9,
                           188.20197727, '', 'therms')]
    rb.service_address = Address('Managing Member', 'Monroe Towers',
                                 'Silver Spring', 'MD', 'Silver Spring')
    rb.billing_address = Address('Managing Member', 'Monroe Towers',
                                 'Silver Spring', 'MD', 'Silver Spring')
    rb.get_total_renewable_energy.return_value = 188.20197727
    rb.get_total_hypothetical_charges.return_value = sum(c.h_total for c in rb
        .charges)
    rb.get_period.return_value = date(2011,11,12), date(2011,12,14)
    rb.utilbills = [createMockUtilBill()]
    return rb


class ExporterTest(unittest.TestCase):

    def setUp(self):
        #Set up the mock
        self.mock_StateDB = mock.create_autospec(StateDB)
        self.mock_ReebillDAO = mock.create_autospec(ReebillDAO)
        self.exp = Exporter(self.mock_StateDB, self.mock_ReebillDAO)

    def test_get_reebill_details_dataset(self):
        #Set up the mock
        self.mock_StateDB.listAccounts.return_value = listAccounts()
        self.mock_StateDB.payments.return_value = payments()
        self.mock_StateDB.listReebills.return_value = [[createMockReebill()] ,1]

        dataset = self.exp.get_export_reebill_details_dataset(None, None)
        correct_data=[('10003', 1, 0, u'Monroe Towers, Silver Spring, MD', u'Monroe Towers, Silver Spring, MD', '2013-04-01', '2011-11-12', '2011-12-14', '980.33', '743.49', '4.30', '2.20', None, '2011-11-30', '400.13', '0.00', '62.29', '122.20', 32.2, '5.01', '', '-117.90', '-117.90', '188.20', '1.26'),
                      ('10003', 1, 0, None, None, None, None, None, None, None, None, None, None, '2011-12-01', '13.37', None, None, None, None, None, None, None, None, None, None),
                      ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD', u'Monroe Towers, Silver Spring, MD', '2013-04-01', '2011-11-12', '2011-12-14', '980.33', '743.49', '4.30', '2.20', None, None, None, '0.00', '62.29', '122.20', 32.2, '5.01', '', '-117.90', '-117.90', '188.20', '1.26')]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

    def test_get_energy_usage_sheet(self):
        def make_charge(number):
            result = mock.Mock(autospec=Charge)
            result.total = number
            result.group = str(number)
            result.description = ''
            return result

        doc = {
            'service': 'gas',
            'meters': [{
                'identifier': '',
                'registers': [{
                    "description" : "Insert description",
                    "quantity" : 561.9,
                    "quantity_units" : "therms",
                    "identifier" : '',
                    "type" : "total",
                    "register_binding": "REG_TOTAL"
                }]
            }]
        }

        #Setup Mock
        u1 = mock.Mock(autospec=UtilBill)
        u1.customer.account = '10003'
        u1.rate_class = 'DC Non Residential Non Heat'
        u1.period_start = date(2011,11,12)
        u1.period_end = date(2011,12,14)
        u1.charges = [make_charge(x) for x in [3.37, 17.19, 43.7, 164.92,
                23.14, 430.02, 42.08, 7.87, 11.2]]
        u2 = deepcopy(u1)
        u2.period_start = date(2011,12,15)
        u2.period_end = date(2012,01,14)
        self.mock_ReebillDAO._load_utilbill_by_id.side_effect = [doc, doc]

        dataset = self.exp.get_energy_usage_sheet([u1, u2])
        correct_data = [('10003', u'DC Non Residential Non Heat', 561.9, u'therms', '2011-11-12', '2011-12-14', 3.37, 17.19, 43.7, 164.92, 23.14, 430.02, 42.08, 7.87, 11.2),
            ('10003', u'DC Non Residential Non Heat', 561.9, u'therms', '2011-12-15', '2012-01-14', 3.37, 17.19, 43.7, 164.92, 23.14, 430.02, 42.08, 7.87, 11.2),]
        headers = ['Account', 'Rate Class', 'Total Energy', 'Units',
                'Period Start', 'Period End', '3.37: ', '17.19: ', '43.7: ',
                '164.92: ', '23.14: ', '430.02: ', '42.08: ', '7.87: ',
                '11.2: ']
        self.assertEqual(headers, dataset.headers)
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))
