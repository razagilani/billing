#!/usr/bin/env python2
from copy import deepcopy
from billing.processing.excel_export import Exporter
from billing.processing.state import (
    StateDB, ReeBill, Payment, ReeBillCharge, Reading, UtilBill, Address,
    Charge)
from billing.processing.mongo import ReebillDAO
from datetime import date, datetime
import unittest
import mock


class ExporterTest(unittest.TestCase):

    def setUp(self):
        #Set up the mock
        self.mock_StateDB = mock.create_autospec(StateDB)
        self.mock_ReebillDAO = mock.create_autospec(ReebillDAO)
        self.exp = Exporter(self.mock_StateDB, self.mock_ReebillDAO)

    def test_get_reebill_details_dataset(self):

        def make_reebill():
            result = mock.Mock(autospec=ReeBill)
            result.sequence = 1
            result.version = 0
            result.issued = 1
            result.utilbills = [mock.Mock(autospec=UtilBill)]
            result.billing_address = 'Monroe Towers, Silver Spring, MD'
            result.service_address = 'Monroe Towers, Silver Spring, MD'
            result.issue_date = date(2013, 4, 1)
            result.ree_value = 4.3
            result.prior_balance = 2.20
            result.payment_received = None
            result.total_adjustment = 0.00
            result.balance_forward = 62.29
            result.ree_charge = 122.20
            result.late_charge = 32.2
            result.balance_due = 5.01

            result.get_period.return_value = (
                date(2011, 11, 12), date(2011, 12, 14))
            result.get_total_actual_charges.return_value = 743.49
            result.get_total_hypothetical_charges.return_value = 980.33
            result.get_total_renewable_energy.return_value = 188.20

            return result

        def make_payment(date_applied, amount):
            result = mock.Mock(autospec=Payment)
            result.date_applied = date_applied
            result.credit = amount
            return result

        self.mock_StateDB.payments.side_effect = [
            [make_payment(datetime(2011, 11, 30, 0, 0, 0), 400.13),  # '10003'
             make_payment(datetime(2011, 12, 01, 0, 0, 0), 13.37)],
            [] # '10004'
        ]
        self.mock_StateDB.listReebills.side_effect = [
            ([make_reebill()], 1),   # For account '10003'
            ([make_reebill()], 1)]   # For account '10004'

        dataset = self.exp.get_export_reebill_details_dataset(
            ['10003', '10004'], None, None)
        correct_data=[('10003', 1, 0, u'Monroe Towers, Silver Spring, MD',
                       u'Monroe Towers, Silver Spring, MD', '2013-04-01',
                       '2011-11-12', '2011-12-14', '980.33', '743.49', '4.30',
                       '2.20', None, '2011-11-30', '400.13', '0.00', '62.29',
                       '122.20', 32.2, '5.01', '', '-117.90', '-117.90',
                       '188.20', '1.26'),
                      ('10003', 1, 0, None, None, None, None, None, None, None,
                       None, None, None, '2011-12-01', '13.37', None, None,
                       None, None, None, None, None, None, None, None),
                      ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
                       u'Monroe Towers, Silver Spring, MD', '2013-04-01',
                       '2011-11-12', '2011-12-14', '980.33', '743.49', '4.30',
                       '2.20', None, None, None, '0.00', '62.29', '122.20',
                       32.2, '5.01', '', '-117.90', '-117.90', '188.20',
                       '1.26')]
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
