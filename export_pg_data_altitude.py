'''Script to generate CSV file with data described in "Billing 24" Google
doc. Can be executed by cron.

This file doesn't/shouldn't have test coverage so don't put substantive code
in it!
'''
from argparse import ArgumentParser
from uuid import uuid4
from billing import init_config, init_model
from billing.core import altitude
from billing.pg.export_altitude import PGAltitudeExporter, _load_pg_utilbills

# TODO determine file destination. maybe use a command-line argument.
FILE_PATH = 'reebill_pg_utility_bills.csv'

if __name__ == '__main__':
    init_config()
    init_model()
    pgae = PGAltitudeExporter(uuid4, altitude)
    with open(FILE_PATH, 'w') as the_file:
        pgae.write_csv(_load_pg_utilbills(), the_file)