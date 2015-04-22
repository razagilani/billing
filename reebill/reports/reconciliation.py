from tablib import Dataset

class ReconcilationReport(object):
    def __init__(self, reebill_dao, ree_getter):
        self.reebill_dao = reebill_dao
        self.ree_getter = ree_getter

    def get_dataset(self):
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

