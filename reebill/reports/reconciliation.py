from tablib import Dataset

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

    def get_dataset(self):
        """Return a tablib.Dataset containing the report data.
        """
        dataset = Dataset(headers=['Customer ID', 'Sequence', 'Total Energy',
                                   'Current Total Energy'])
        for reebill in self.reebill_dao.get_all_reebills():
            original_energy = reebill.get_total_renewable_energy()
            self.ree_getter.update_renewable_readings(reebill)
            current_energy = reebill.get_total_renewable_energy()
            dataset.append(
                [reebill.get_customer_id(), reebill.sequence, original_energy,
                 current_energy])
        return dataset

    def write_json(self, output_file):
        """Write report data to a file.
        :param output_file: file object.
        """
        dataset = self.get_dataset()
        output_file.write(dataset.json)