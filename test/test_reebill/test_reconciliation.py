from unittest import TestCase

from mock import Mock

from nexusapi.nexus_util import NexusUtil
from reebill.fetch_bill_data import RenewableEnergyGetter
from reebill.reports.reconciliation import ReconcilationReport
from reebill.reebill_dao import ReeBillDAO
from reebill.reebill_model import ReeBill


class TestReconciliationReport(TestCase):
    def setUp(self):
        self.reebill_dao = Mock(autospec=ReeBillDAO)
        self.ree_getter = Mock(autospec=RenewableEnergyGetter)
        self.rr = ReconcilationReport(self.reebill_dao, self.ree_getter)

    def test_get_dataset(self):
        bill1 = Mock(autospec=ReeBill)
        bill1.sequence = 1
        bill1.get_customer_id.return_value = 1
        bill1.get_total_renewable_energy.side_effect = [100, 110]

        bill2 = Mock(autospec=ReeBill)
        bill2.sequence = 2
        bill2.get_customer_id.return_value = 2
        bill2.get_total_renewable_energy.return_value = 200
        self.reebill_dao.get_all_reebills.return_value = [bill1, bill2]

        dataset = self.rr.get_dataset()
        self.assertEqual(
            ['Customer ID', 'Sequence', 'Total Energy', 'Current Total Energy'],
            dataset.headers)
        self.assertEqual([
            (1, 1, 100, 110),
            (2, 2, 200, 200)
        ], dataset[:dataset.height])