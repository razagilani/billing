from copy import deepcopy
from datetime import date, datetime
from itertools import cycle
from StringIO import StringIO
import unittest

import mock

from core import init_config, init_model
from core.model import UtilBill, Register, Charge, Session, Utility, Address,\
    Supplier, RateClass, UtilityAccount
from reebill.reports.excel_export import Exporter
from reebill.reebill_model import ReeBill, Payment
from reebill.reebill_dao import ReeBillDAO
from reebill.payment_dao import PaymentDAO


class ExporterSheetTest(unittest.TestCase):

    def setUp(self):
        #Set up the mock
        self.mock_StateDB = mock.create_autospec(ReeBillDAO)
        self.payment_dao = mock.Mock(autospec=PaymentDAO)
        self.exp = Exporter(self.mock_StateDB, self.payment_dao)

    def test_get_reebill_details_dataset(self):

        def make_reebill(id, month):
            result = mock.Mock(autospec=ReeBill)
            result.id = id
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
                date(2011, month, 3), date(2011, month+1, 2))
            result.get_total_actual_charges.return_value = 743.49
            result.get_total_hypothetical_charges.return_value = 980.33
            result.get_total_renewable_energy.return_value = 188.20

            return result

        def make_payment(date_applied, amount):
            result = mock.Mock(autospec=Payment)
            result.date_applied = date_applied
            result.credit = amount
            return result

        def get_payments_for_reebill_id(id):
            if id == 1:
                return [
                    make_payment(datetime(2011, 1, 30, 0, 0, 0), 400.13),  # '10003'
                    make_payment(datetime(2011, 2, 01, 0, 0, 0), 13.37)
                ]
            else:
                return []

        self.payment_dao.get_payments_for_reebill_id.side_effect = \
            get_payments_for_reebill_id
        self.mock_StateDB.get_all_reebills_for_account.side_effect = cycle([
            [make_reebill(1, 1)],   # For account '10003'
            [make_reebill(2, 2), make_reebill(3, 3), make_reebill(4, 4)] # 10004
        ])

        # No start or end date
        dataset = self.exp.get_export_reebill_details_dataset(
            ['10003', '10004'])
        correct_data = [
            ('10003', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-01-03', '2011-02-02', '980.33', '743.49', '4.30',
             '2.20', None, '2011-01-30', '400.13', '0.00', '62.29',
             '122.20', 32.2, '5.01', '', '-117.90', '-117.90',
             '188.20', '1.26'),
            ('10003', 1, 0, None, None, None, None, None, None, None,
             None, None, None, '2011-02-01', '13.37', None, None,
             None, None, None, None, None, None, None, None),
            ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-02-03', '2011-03-02', '980.33', '743.49', '4.30',
             '2.20', None, None, None, '0.00', '62.29', '122.20',
             32.2, '5.01', '', '-117.90', '-117.90', '188.20',
             '1.26'),
            ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-03-03', '2011-04-02', '980.33', '743.49', '4.30',
             '2.20', None, None, None, '0.00', '62.29', '122.20',
             32.2, '5.01', '', '-117.90', '-235.80', '188.20',
             '1.26'),
            ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-04-03', '2011-05-02', '980.33', '743.49', '4.30',
             '2.20', None, None, None, '0.00', '62.29', '122.20',
             32.2, '5.01', '', '-117.90', '-353.70', '188.20',
             '1.26')
        ]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

        # Only start date
        dataset = self.exp.get_export_reebill_details_dataset(
            ['10003', '10004'], begin_date=date(2011, 4, 1))
        correct_data = [
            ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-04-03', '2011-05-02', '980.33', '743.49', '4.30',
             '2.20', None, None, None, '0.00', '62.29', '122.20',
             32.2, '5.01', '', '-117.90',  '-117.90', '188.20',
             '1.26')
        ]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

        # Only end date
        dataset = self.exp.get_export_reebill_details_dataset(
            ['10003', '10004'], end_date=date(2011, 3, 5))
        correct_data = [
            ('10003', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-01-03', '2011-02-02', '980.33', '743.49', '4.30',
             '2.20', None, '2011-01-30', '400.13', '0.00', '62.29',
             '122.20', 32.2, '5.01', '', '-117.90', '-117.90',
             '188.20', '1.26'),
            ('10003', 1, 0, None, None, None, None, None, None, None,
             None, None, None, '2011-02-01', '13.37', None, None,
             None, None, None, None, None, None, None, None),
            ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-02-03', '2011-03-02', '980.33', '743.49', '4.30',
             '2.20', None, None, None, '0.00', '62.29', '122.20',
             32.2, '5.01', '', '-117.90', '-117.90', '188.20',
             '1.26')
        ]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

        # Start and end date
        dataset = self.exp.get_export_reebill_details_dataset(
            ['10003', '10004'], begin_date=date(2011, 2, 1),
            end_date=date(2011, 3, 5))
        correct_data = [
            ('10004', 1, 0, u'Monroe Towers, Silver Spring, MD',
             u'Monroe Towers, Silver Spring, MD', '2013-04-01',
             '2011-02-03', '2011-03-02', '980.33', '743.49', '4.30',
             '2.20', None, None, None, '0.00', '62.29', '122.20',
             32.2, '5.01', '', '-117.90', '-117.90', '188.20',
             '1.26')
        ]
        for indx,row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

    def test_account_charges_sheet(self):
        def make_utilbill(month):
            result = mock.Mock(autospec=UtilBill)
            result.period_start = datetime(2013, month, 3)
            result.period_end = datetime(2013, month+1, 4)
            result.state = UtilBill.Complete
            return result

        def make_charge(group, desc, number):
            result = mock.Mock(autospec=Charge)
            result.total = number
            result.group = group
            result.description = desc
            return result

        def make_reebill(seq):
            result = mock.Mock(autospec=ReeBill)
            result.sequence = seq
            ub = make_utilbill(seq)
            result.utilbills = [ub]
            result.utilbill = ub
            return result

        r1 = make_reebill(1)
        r1.utilbill.charges = [make_charge(x,y,z) for x,y,z in [
            ('Group1', "Description1", 1.11),
            ('Group1', "Description2", 2.22),
            ('Group2', "Description3", 3.33),
        ]]
        r2 = make_reebill(2)
        r2.utilbill.charges = [make_charge(x,y,z) for x,y,z in [
            ('Group1', "Description1", 4.44),
            ('Group2', "Description2", 5.55),
            ('Group2', "Description3", 6.66),
        ]]
        r3 = make_reebill(3)
        r3.utilbill.charges = [make_charge(x,y,z) for x,y,z in [
            ('Group1', "Description1", 4.44),
            ('Group2', "Description2", 5.55),
            ('Group2', "Description3", 6.66),
        ]]

        # No start date or end date
        dataset = self.exp.get_account_charges_sheet('999999', [r1, r2, r3])
        correct_data = [('999999', 1, '2013-01-03', '2013-02-04', '2013-01',
                         'No', '1.11', '2.22', '3.33', ''),
                        ('999999', 2, '2013-02-03', '2013-03-04', '2013-02',
                         'No', '4.44', '', '6.66', '5.55'),
                        ('999999', 3, '2013-03-03', '2013-04-04', '2013-03',
                         'No', '4.44', '', '6.66', '5.55')]
        headers = ['Account', 'Sequence', 'Period Start', 'Period End',
                   'Billing Month', 'Estimated', 'Group1: Description1',
                   'Group1: Description2', 'Group2: Description3',
                   'Group2: Description2']
        self.assertEqual(headers, dataset.headers)
        for indx, row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))
        # Only start date
        dataset = self.exp.get_account_charges_sheet(
            '999999', [r1, r2, r3], start_date=datetime(2013, 2, 1))
        correct_data = [('999999', 2, '2013-02-03', '2013-03-04', '2013-02',
                         'No', '4.44', '5.55', '6.66'),
                        ('999999', 3, '2013-03-03', '2013-04-04', '2013-03',
                         'No', '4.44', '5.55', '6.66')]
        headers = ['Account', 'Sequence', 'Period Start', 'Period End',
                   'Billing Month', 'Estimated', 'Group1: Description1',
                   'Group2: Description2', 'Group2: Description3']
        self.assertEqual(headers, dataset.headers)
        for indx, row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))
        # Only end date
        dataset = self.exp.get_account_charges_sheet(
            '999999', [r1, r2, r3], end_date=datetime(2013, 3, 5))
        correct_data = [('999999', 1, '2013-01-03', '2013-02-04', '2013-01',
                         'No', '1.11', '2.22', '3.33', ''),
                        ('999999', 2, '2013-02-03', '2013-03-04', '2013-02',
                         'No', '4.44', '', '6.66', '5.55')]
        headers = ['Account', 'Sequence', 'Period Start', 'Period End',
                   'Billing Month', 'Estimated', 'Group1: Description1',
                   'Group1: Description2', 'Group2: Description3',
                   'Group2: Description2']
        self.assertEqual(headers, dataset.headers)
        for indx, row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))
        # Both start and end date
        dataset = self.exp.get_account_charges_sheet(
            '999999', [r1, r2], start_date=datetime(2013, 2, 1),
            end_date=datetime(2013, 3, 5))
        correct_data = [('999999', 2, '2013-02-03', '2013-03-04', '2013-02',
                         'No', '4.44', '5.55', '6.66')]
        headers = ['Account', 'Sequence', 'Period Start', 'Period End',
                   'Billing Month', 'Estimated', 'Group1: Description1',
                   'Group2: Description2', 'Group2: Description3']
        self.assertEqual(headers, dataset.headers)
        for indx, row in enumerate(dataset):
            self.assertEqual(row, correct_data[indx])
        self.assertEqual(len(dataset), len(correct_data))

    def test_get_energy_usage_sheet(self):
        def make_charge(number):
            result = mock.Mock(autospec=Charge)
            result.total = number
            result.group = str(number)
            result.description = ''
            return result

        #Setup Mock
        u1 = mock.Mock(autospec=UtilBill)
        u1.utility_account.account = '10003'
        u1.rate_class.name = 'DC Non Residential Non Heat'
        u1.period_start = date(2011,11,12)
        u1.period_end = date(2011,12,14)
        u1.charges = [make_charge(x) for x in [3.37, 17.19, 43.7, 164.92,
                23.14, 430.02, 42.08, 7.87, 11.2]]
        # replacement for document above
        register1 = mock.Mock(autospec=Register)
        register1.description = ''
        register1.quantity = 561.9
        register1.unit = 'therms'
        register1.estimated = False
        register1.reg_type = 'total'
        register1.register_binding = Register.TOTAL
        register1.active_periods = None
        u1.registers = [register1]
        u2 = deepcopy(u1)
        u2.period_start = date(2011,12,15)
        u2.period_end = date(2012,01,14)
        u2.registers = [deepcopy(register1)]

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


class ExporterDataBookTest(unittest.TestCase):

    def setUp(self):
        init_config('test/tstsettings.cfg')
        init_model()

        self.exp = Exporter(ReeBillDAO(), PaymentDAO())

        s = Session()
        utility = Utility(name='New Utility', address=Address())
        s.add(utility)

        supplier = Supplier(name='New Supplier', address=Address())
        s.add(supplier)

        rate_class = RateClass(name='New Rate Class', utility=utility,
                               service='electric')
        s.add(rate_class)

        utility_account = UtilityAccount(
                'some name',
                '20001',
                utility,
                supplier,
                rate_class,
                None,
                Address(),
                Address(),
                '1234567890'
        )
        s.add(utility_account)

        s.add(
            UtilBill(
                utility_account, utility,
                rate_class, supplier=supplier,
                period_start=date(2010, 11, 1), period_end=date(2011, 2, 3),
                date_received=datetime.utcnow().date(),
                state=UtilBill.Estimated,
            )
        )

    def test_exports_returning_binaries(self):
        """
        This test simply calls all export functions returning binaries. This
        way we can at least verify that the code in those functions is
        syntactically correct and calls existing methods
        """

        string_io = StringIO()

        # export_account_charges
        self.exp.export_account_charges(string_io)
        self.exp.export_account_charges(string_io, '20001')
        self.exp.export_account_charges(string_io, '20001', date(2010, 11, 1))
        self.exp.export_account_charges(string_io, '20001',
                                        date(2010, 11, 1), date(2011, 2, 3))

        # export_energy_usage
        self.exp.export_energy_usage(string_io)
        self.exp.export_energy_usage(string_io, '20001')

        # export_reebill_details
        self.exp.export_reebill_details(string_io)
        self.exp.export_reebill_details(string_io, '20001')
        self.exp.export_reebill_details(string_io, '20001', date(2010, 11, 1))
        self.exp.export_reebill_details(string_io, '20001',
                                        date(2010, 11, 1), date(2011, 2, 3))
