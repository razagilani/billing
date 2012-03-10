#!/usr/bin/python
import argparse
import matplotlib.pyplot as plt
from billing.mongo import ReebillDAO
'''Creates a sample CSV file with random energy values every 15 minutes in the
format used by fetch_interval_meter_data. Command-line arguments are file name,
start date (ISO 8601, inclusive), end date (exclusive). E.g:
    make_sample_csv.py interval_meter_sample.csv 2012-11-10 2012-12-12
'''

class Grapher:
    def __init__(self, reebill_dao):
        self.reebill_dao = reebill_dao

    def get_savings(self, account):
        time_offsets = [] # in days
        savings = []
        first_reebill_start = self.reebill_dao.get_first_bill_date_for_account(account)
        for reebill in self.reebill_dao.load_reebills_in_period(account):
            time_offsets.append((reebill.period_begin - first_reebill_start.date()).days)
            savings.append(float(reebill.savings))
        return time_offsets, savings

    #def get_conventional_energy_charges(self, account):
        #time_offsets = [] # in days
        #charges = []
        #first_reebill_start = self.reebill_dao.get_first_bill_date_for_account(account)
        #for reebill in self.reebill_dao.load_reebills_in_period(account):
            #time_offsets.append((reebill.period_begin - first_reebill_start.date()).days)
            #ce_total = 0
            #for charge in reebill.actual_chargegroups_flattened:
                #...
            #savings.append(float(reebill.savings))
        #return time_offsets, savings

    def plot_savings(self, account):
        time_offsets, savings = self.get_savings(account)
        plt.plot(time_offsets, savings, linewidth=2, color='g')
        plt.show()

    def plot_cumulative_savings(self, account):
        time_offsets, savings = self.get_savings(account)
        for i in range(len(savings)):
            if i == 0:
                continue
            savings[i] += savings[i-1]
        plt.plot(time_offsets, savings, linewidth=2, color='g')
        plt.show()

def main():
    # command-line arguments
    parser = argparse.ArgumentParser(description='Draw some graphs.')
    parser.add_argument('account', metavar='ACCOUNT',
           help='account of customer to graph')
    parser.add_argument('--host',  default='localhost',
            help='host for all databases (default: localhost)')
    parser.add_argument('--billdb', default='skyline',
            help='name of bill database (default: skyline)')
    args = parser.parse_args()

    # set up config dicionaries for data access objects used in generate_report
    billdb_config = {
        'database': args.billdb,
        'collection': 'reebills',
        'host': args.host,
        'port': '27017'
    }

    print args
    g = Grapher(ReebillDAO(billdb_config))
    g.plot_cumulative_savings(args.account)

if __name__ == '__main__':
    main()
