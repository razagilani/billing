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
from skyliner.skymap.monguru import Monguru
from skyliner import sky_handlers
from billing.nexus_util import NexusUtil
from billing import json_util
from billing import dateutils
import xlwt

LOG_FILE_NAME = 'xls_export.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

class Exporter(object):
    def __init__(self, logger, billdb_config, statedb_config, splinter_config, monguru_config):
        self.logger = logger

        # objects for database access
        self.reebill_dao = mongo.ReebillDAO(billdb_config)
        self.state_db = state.StateDB(statedb_config)
        self.splinter = Splinter(splinter_config['url'], splinter_config['host'],
                splinter_config['db'])
        self.monguru = Monguru(monguru_config['host'], monguru_config['db'])

    def export(self, account, sequence, output_file):
        session = self.state_db.session()

        workbook = xlwt.Workbook(encoding="utf-8")

        for sequence in self.state_db.listSequences(session, account):
            reebill = self.reebill_dao.load_reebill(account, sequence)

            # each reebill gets its own sheet
            sheet = workbook.add_sheet('%s-%s' % (account, sequence))

            # write column headers
            # (row, column)
            sheet.write(0, 1, 'Name')
            sheet.write(0, 2, 'Charge Total')

            # write charges starting at row 1
            chargegroups = reebill.chargegroups_flattened
            for row, charge in [(i+1, c) for (i, c) in zip(*enumerate(chargegroups))]:
                print row, charge





            session.commit()


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
    monguru_config = {
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

    exporter = Exporter(logger, billdb_config, statedb_config, splinter_config,
            monguru_config)
    with open('output.xls', 'wb') as output_file:
        exporter.export('10003', 16, output_file)


if __name__ == '__main__':
    main()
