#!/usr/bin/python
import argparse
import pychartdir
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
        #print actual_charges
        #chart = XYChart(0, 0, 400, 300)
        #chart.setPlotArea(30, 20, 200, 200)
        #chart.addLineLayer(actual_charges)
        #chart.xAxis().setLabels(map(str, days))
        #chart.xAxis().setLabelStep(3)
        #chart.makeChart('chart.png')


        # The data for the line chart
        data = [30, 28, 40, 55, 75, 68, 54, 60, 50, 62, 75, 65, 75, 91, 60, 55, 53, 35, 50,
            66, 56, 48, 52, 65, 62]

        # The labels for the line chart
        #labels = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13",
            #"14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"]
        labels = map(str, days)

        # Create a XYChart object of size 250 x 250 pixels
        c = pychartdir.XYChart(500, 300)

        # Set the plotarea at (30, 20) and of size 200 x 200 pixels
        c.setPlotArea(0, 0, 500, 300, pychartdir.Transparent, pychartdir.Transparent, pychartdir.Transparent, -1, pychartdir.Transparent)

        # Add a line chart layer using the given data
        layer = c.addLineLayer(actual_charges)
        layer.addDataSet(hypothetical_charges)
        layer.setLineWidth(2)

        ## Set the labels on the x axis.
        #c.xAxis().setLabels(labels)

        ## Display 1 out of 3 labels on the x-axis.
        #c.xAxis().setLabelStep(3)

        # Output the chart
        c.makeChart("chart.png")

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
