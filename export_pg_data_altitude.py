'''Script to generate CSV file with data described in "Billing 24" Google
doc. Can be executed by cron.

This file doesn't/shouldn't have test coverage so don't put substantive code
in it!
'''
from argparse import ArgumentParser
from billing import init_config, init_model
from billing.pg.export_altitude import export_csv

# TODO determine file destination. maybe use a command-line argument.
FILE_PATH = 'reebill_pg_utility_bills.csv'

if __name__ == '__main__':
    init_config()
    init_model()
    with open(FILE_PATH, 'w') as the_file:
        export_csv(the_file)