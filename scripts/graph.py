#!/usr/bin/python
import argparse
from pychartdir import XYChart
import matplotlib.pyplot as plt
from billing.mongo import ReebillDAO
'''Creates a sample CSV file with random energy values every 15 minutes in the
format used by fetch_interval_meter_data. Command-line arguments are file name,
start date (ISO 8601, inclusive), end date (exclusive). E.g:
    make_sample_csv.py interval_meter_sample.csv 2012-11-10 2012-12-12
'''

def integrate(array):
    '''Converts a list of per-unit-time values into a cumulative one.'''
    for i in range(1, len(array)):
        array[i] = array[i] + array[i-1]

class Grapher:
    def __init__(self, reebill_dao):
        self.reebill_dao = reebill_dao

    def get_time_series(self, account, func):
        '''Returns a pair of lists respectively containing numbers of days from
        the given account's first bill date and numercal values associated with
        reebills starting on those dates. 'func' determines the values in the
        second list; it should map a reebill to a number (e.g. lambda reebill:
        reebill.actual_total).'''
        time_offsets = []
        y_values = []
        first_reebill_start = self.reebill_dao.get_first_bill_date_for_account(account)
        for reebill in self.reebill_dao.load_reebills_in_period(account):
            time_offsets.append((reebill.period_begin - first_reebill_start.date()).days)
            y_values.append(float(func(reebill)))
        return time_offsets, y_values

    def plot_cumulative_actual_and_hypothetical_ce_charces(self, account):
        days, actual_charges = self.get_time_series(account, lambda r: r.actual_total)
        _, hypothetical_charges = self.get_time_series(account, lambda r: r.hypothetical_total)
        integrate(actual_charges)
        integrate(hypothetical_charges)

        #plt.plot(days, hypothetical_charges, linewidth=2)
        #plt.plot(days, actual_charges, linewidth=2)
        print actual_charges
        chart = XYChart(0, 0, 400, 300)
        chart.setPlotArea(30, 20, 200, 200)
        chart.addLineLayer(actual_charges)
        chart.xAxis().setLabels(map(str, days))
        chart.xAxis().setLabelStep(3)
        chart.makeChart('chart.png')


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

    g = Grapher(ReebillDAO(billdb_config))
    g.plot_cumulative_actual_and_hypothetical_ce_charces(args.account)
    plt.show()

if __name__ == '__main__':
    main()
