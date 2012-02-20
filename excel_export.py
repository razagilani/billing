#!/usr/bin/python
import os
from billing import mongo
from billing.processing import state
import xlwt
import pprint
pformat = pprint.PrettyPrinter().pformat

LOG_FILE_NAME = 'xls_export.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

class Exporter(object):
    def __init__(self, state_db, reebill_dao, verbose=False):
        # objects for database access
        self.state_db = state_db
        self.reebill_dao = reebill_dao
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

    def export_all(self, statedb_session, output_file):
        workbook = xlwt.Workbook(encoding="utf-8")
        for account in sorted(self.state_db.listAccounts(statedb_session)):
            for sequence in sorted(self.state_db.listSequences(statedb_session, account)):
                self.write_sheet(statedb_session, workbook, account, sequence, output_file)
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

    state_db = state.StateDB(statedb_config)

    exporter = Exporter(
        state_db,
        mongo.ReebillDAO(billdb_config),
        verbose=True
    )

    session = state_db.session()
    with open('output.xls', 'wb') as output_file:
        exporter.export_all(session, output_file)
    session.commit()


if __name__ == '__main__':
    main()
