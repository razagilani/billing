#!/usr/bin/python
import sys
import argparse
import pychartdir
#import matplotlib.pyplot as plt
from billing.mongo import ReebillDAO
from billing.processing.state import StateDB
from StringIO import StringIO

def integrate(array):
    '''Converts a list of per-unit-time values into a cumulative one.'''
    for i in range(1, len(array)):
        array[i] = array[i] + array[i-1]

class Grapher(object):
    def __init__(self, state_db, reebill_dao):
        self.state_db = state_db
        self.reebill_dao = reebill_dao

    def get_data_points(self, account, x_func, y_func):
        x_values, y_values = [], []
        first_issue_date = self.reebill_dao.get_first_issue_date_for_account(account)
        for sequence in self.state_db.listSequences(self.state_db.session(), account):
            reebill = self.reebill_dao.load_reebill(account, sequence)
            x_values.append(x_func(reebill))
            y_values.append(y_func(reebill))
        return x_values, y_values

    def plot_cumulative_actual_and_hypothetical_ce_charces(self, account,
            output_path, actual_color='0x007437',
            hypothetical_color='0x9bbb59', width=500, height=300):
        '''Writes a line graph of cumulative actual and hypothetical charges
        for the given account to 'output_path' (file extension determines the
        format).'''
        days, actual_charges = self.get_data_points(account, lambda r:
                r.sequence, lambda r: float(r.actual_total))
        _, hypothetical_charges = self.get_data_points(account, lambda r:
                r.sequence, lambda r: float(r.hypothetical_total))
        integrate(actual_charges)
        integrate(hypothetical_charges)

        #plt.plot(days, hypothetical_charges, linewidth=2)
        #plt.plot(days, actual_charges, linewidth=2)
        c = pychartdir.XYChart(width, height)
        # offset coordinates determined by trial & error; probably could be
        # better but they look ok
        c.setPlotArea(40, 20, width-50, height-50, pychartdir.Transparent,
                pychartdir.Transparent, pychartdir.Transparent, -1,
                pychartdir.Transparent)
        layer = c.addLineLayer(actual_charges, actual_color)
        layer.addDataSet(hypothetical_charges, hypothetical_color)
        layer.setLineWidth(2)
        c.xAxis().setLabels(map(str, days))
        c.xAxis().setLabelStep(1)
        c.makeChart(output_path)

    # TODO avoid duplicated code with the method above
    def plot_monthly_actual_and_hypothetical_ce_charces(self, account,
            output_path, actual_color='0x007437',
            hypothetical_color='0x9bbb59', width=500, height=300):
        '''Writes a line graph of actual and hypothetical charges by month for
        the given account to 'output_path' (file extension determines the
        format).'''
        days, actual_charges = self.get_data_points(account, lambda r:
                r.sequence, lambda r: float(r.actual_total))
        _, hypothetical_charges = self.get_data_points(account, lambda r:
                r.sequence, lambda r: float(r.hypothetical_total))
        c = pychartdir.XYChart(width, height)
        # offset coordinates determined by trial & error; probably could be
        # better but they look ok
        c.setPlotArea(40, 20, width-50, height-50, pychartdir.Transparent,
                pychartdir.Transparent, pychartdir.Transparent, -1,
                pychartdir.Transparent)
        layer = c.addLineLayer(actual_charges, actual_color)
        layer.addDataSet(hypothetical_charges, hypothetical_color)
        layer.setLineWidth(2)
        c.xAxis().setLabels(map(str, days))
        c.xAxis().setLabelStep(1)
        c.makeChart(output_path)

def main():
    # command-line arguments
    parser = argparse.ArgumentParser(description='Draw a graph of cumulative hypothetical and actual charges for an account.')
    parser.add_argument('account', metavar='ACCOUNT', help='account of customer to graph')
    parser.add_argument('--host',  default='localhost', help='host for all databases (default: localhost)')
    parser.add_argument('--billdb', default='skyline', help='name of bill database (default: skyline)')
    parser.add_argument('--statedb', default='skyline_dev', help='name of state database (default: skyline_dev)')
    parser.add_argument('--stateuser', default='dev', help='username for state database (default: dev)')
    parser.add_argument('--statepw', default='dev', help='name of state database (default: dev)')
    args = parser.parse_args()

    # set up config dicionaries for data access objects
    billdb_config = {
        'database': args.billdb,
        'collection': 'reebills',
        'host': args.host,
        'port': '27017'
    }
    statedb_config = {
        'host': args.host,
        'password': args.statepw,
        'database': args.statedb,
        'user': args.stateuser
    }

    g = Grapher(StateDB(**statedb_config), ReebillDAO(billdb_config))
    g.plot_monthly_actual_and_hypothetical_ce_charces(args.account, 'chart.png')

if __name__ == '__main__':
    main()
