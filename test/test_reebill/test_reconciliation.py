from datetime import date
from unittest import TestCase
from StringIO import StringIO

from mock import Mock

from reebill.fetch_bill_data import RenewableEnergyGetter
from reebill.reports.reconciliation import ReconciliationReport
from reebill.reebill_dao import ReeBillDAO
from reebill.reebill_model import ReeBill


class TestReconciliationReport(TestCase):
    """Unit test for ReconciliationReport.
    """
    def setUp(self):
        self.reebill_dao = Mock(autospec=ReeBillDAO)
        self.ree_getter = Mock(autospec=RenewableEnergyGetter)
        self.rr = ReconciliationReport(self.reebill_dao, self.ree_getter)

        bill1 = Mock(autospec=ReeBill)
        bill1.sequence = 1
        bill1.get_customer_id.return_value = 1
        bill1.get_account.return_value = '1'
        bill1.get_total_renewable_energy.side_effect = [100, 110]
        bill1.get_period_start.return_value = date(2000, 1, 1)

        bill2 = Mock(autospec=ReeBill)
        bill2.sequence = 2
        bill2.get_customer_id.return_value = 2
        bill2.get_account.return_value = '2'
        bill2.get_total_renewable_energy.return_value = 200
        bill2.get_period_start.return_value = date(2000, 1, 2)
        self.reebill_dao.get_all_reebills.return_value = [bill1, bill2]

    def test_get_dataset(self):
        dataset = self.rr.get_dataset(start=date(2000, 1, 1))
        self.assertEqual(
            ['customer_id', 'nextility_account_number', 'sequence', 'energy',
             'current_energy'], dataset.headers)
        self.assertEqual([
            (1, '1', 1, 100, 110),
            (2, '2', 2, 200, 200)
        ], dataset[:dataset.height])

        # exclusion of bills before the start date
        dataset = self.rr.get_dataset(start=date(2000, 1, 2))
        self.assertEqual([
            (1, '1', 1, None, None),
            (2, '2', 2, 200, 200)
        ], dataset[:dataset.height])

    def test_write_file(self):
        # just check that it wrote something; don't need to test tablib JSON
        # formatting
        output_file = StringIO()
        self.rr.write_json(output_file)
        self.assertGreater(output_file.tell(), 0)
