from datetime import datetime, timedelta
from flask import logging
from tablib import Dataset
from exc import BillingError

LOG_NAME = 'reebill'

class ReconciliationReport(object):
    """Produces a report on how much energy was billed for in each bill vs.
    actual energy sold as currently shown in the OLAP database.
    """
    def __init__(self, reebill_dao, ree_getter):
        """
        :param reebill_dao: ReeBillDAO
        :param ree_getter: RenewableEnergyGetter
        """
        self.reebill_dao = reebill_dao
        self.ree_getter = ree_getter

    def get_dataset(self, start=None):
        """Return a tablib.Dataset containing the report data for bills
        before the given date, or 365 days ago by default.
        :param start: datetime
        """
        if start is None:
            start = (datetime.utcnow() - timedelta(days=365)).date()
        dataset = Dataset(headers=['customer_id', 'nextility_account_number',
                                   'sequence', 'energy', 'current_energy'])
        log = logging.getLogger(LOG_NAME)
        for reebill in self.reebill_dao.get_all_reebills():
            if reebill.get_period_start() < start:
                log.info('%s with account number "%s" excluded from '
                         'reconciliation report because it started on %s, '
                         'before %s' % (
                             reebill, reebill.get_account(),
                             reebill.get_period_start(), start))
                original_energy = current_energy = None
            else:
                original_energy = reebill.get_total_renewable_energy()
                try:
                    self.ree_getter.update_renewable_readings(reebill)
                except BillingError:
                    log.info('%s with account number "%s" excluded from '
                             'reconciliation report because its utility bill '
                             'lacks required registers' % (
                        reebill, reebill.get_account()))
                    original_energy = current_energy = None
                else:
                    current_energy = reebill.get_total_renewable_energy()
            dataset.append(
                [reebill.get_customer_id(), reebill.get_account(),
                 reebill.sequence, original_energy, current_energy])
        return dataset

    def write_json(self, output_file):
        """Write report data to a file.
        :param output_file: file object.
        """
        dataset = self.get_dataset()
        output_file.write(dataset.json)