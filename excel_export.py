#!/usr/bin/python
import os
import sys
import errno
import traceback
import datetime
import argparse
import logging
from billing import mongo
from billing.reebill import render
from billing.processing import state
from skyliner.splinter import Splinter
from skyliner import sky_handlers
from billing.nexus_util import NexusUtil
from billing import json_util
from billing import dateutils
import xlwt
import pprint
pformat = pprint.PrettyPrinter().pformat

LOG_FILE_NAME = 'xls_export.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

class Exporter(object):
    def __init__(self, reebill_dao, state_db, verbose=False):
        # objects for database access
        self.reebill_dao = reebill_dao
        self.state_db = state_db
        self.verbose = verbose

    def write_sheet(self, session, workbook, account, sequence, output_file):
        if self.verbose:
            print '%s-%s' % (account, sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence)

        # each reebill gets its own sheet
        sheet = workbook.add_sheet('%s-%s' % (account, sequence))

        # write column headers
        # (indices are row, column)
        sheet.write(0, 0, 'Group')
        sheet.write(0, 1,'Name')
        sheet.write(0, 2, 'Charge Total')

        # write charges starting at row 1
        chargegroups = [reebill.actual_chargegroups_flattened(service) for service in reebill.services]
        row = 1
        for chargegroup in chargegroups:
            for charge in chargegroup:
                try:
                    group, description, total = charge['chargegroup'], charge['description'], charge['total']
                except Exception as e:
                    print '%s-%s ERROR %s: %s' % (account, sequence, e, pformat(charge))
                else:
                    sheet.write(row, 0, group)
                    sheet.write(row, 1, description)
                    sheet.write(row, 2, total)
                row += 1

    def export_all(self, output_file):
        workbook = xlwt.Workbook(encoding="utf-8")
        session = self.state_db.session()
        for account in sorted(self.state_db.listAccounts(session)):
            for sequence in sorted(self.state_db.listSequences(session, account)):
                self.write_sheet(session, workbook, account, sequence, output_file)
        session.commit()
        workbook.save(output_file)

def main():
    billdb_config = {
        'database': 'skyline',
        'collection': 'reebills',
        'host': 'localhost',
        'port': '27017'
    }
    statedb_config = {
        'host': 'tyrell',
        'password': 'dev',
        'database': 'skyline_dev',
        'user': 'dev'
    }
    splinter_config = {
        'url': 'http://duino-drop.appspot.com/',
        'host': 'localhost',
        'db': 'dev'
    }

    log_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), LOG_FILE_NAME)

    # set up logger
    logger = logging.getLogger('export_xls')
    formatter = logging.Formatter(LOG_FORMAT)
    handler = logging.FileHandler(log_file_path)
    handler.setFormatter(formatter)
    logger.addHandler(handler) 
    logger.setLevel(logging.DEBUG)

    exporter = Exporter(
        mongo.ReebillDAO(billdb_config),
        state.StateDB(statedb_config),
        verbose=True
    )
    with open('output.xls', 'wb') as output_file:
        exporter.export_all(output_file)


if __name__ == '__main__':
    main()
