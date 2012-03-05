#!/usr/bin/python
import os
import sys
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

    def export(self, statedb_session, output_file, account=None):
        '''Writes a spreadsheet to output_file containing all utility bills for
        the given account. If 'account' is not given, writes one sheet for each
        account.'''
        workbook = xlwt.Workbook(encoding="utf-8")
        if account == None:
            for an_account in sorted(self.state_db.listAccounts(statedb_session)):
                self.write_account_sheet(statedb_session, workbook, an_account)
        else:
            self.write_account_sheet(statedb_session, workbook, account)
        workbook.save(output_file)


    def write_account_sheet(self, statedb_session, workbook, account):
        '''Adds a sheet to 'workbook' consisting of all actual andy
        hypothetical charges for all utility bills belonging to 'account'.
        Format: account & sequence in first 2 columns, later columns are charge
        names (i.e. pairs of charge group + charge description) in pairs
        (hypothetical and actual) with values wherever charges having those
        names occur. Utility bills with errors are skipped and an error message
        is printed.'''
        # each account gets its own sheet. 1st 2 columns are account, sequence
        sheet = workbook.add_sheet(account)
        sheet.write(0, 0, 'Account')
        sheet.write(0, 1, 'Sequence')

        # a "charge name" is a string consisting of a charge group and a
        # description. the spreadsheet has one column per charge name (so
        # charges that have the same name but occur in different groups go in
        # separate columns). obviously, not every charge name will occur in
        # every bill.
        # charge names are organized into pairs, since there is always an
        # actual and hypothetical version of each charge. A "charge name pair"
        # is 2-tuple of charge names, one actual and one hypothetical.
        # 
        # this dictionary maps charge names to their columns in the
        # spreadsheet. last_column keeps the highest column index of any
        # charge name so far
        charge_names_columns = {}
        last_column = 1

        row = 1
        for sequence in sorted(self.state_db.listSequences(statedb_session, account)):
            if self.verbose:
                print '%s-%s' % (account, sequence)
            reebill = self.reebill_dao.load_reebill(account, sequence)

            # this becomes true if there was any error reading data for this
            # row
            error = False

            # get all charges from this bill in "flattened" format, sorted by
            # name, with (actual) or (hypothetical) appended
            services = reebill.services
            actual_charges = sorted(reduce(lambda x,y: x+y,
                    [reebill.actual_chargegroups_flattened(service) for service in
                    services]), key=lambda x:x['description'])
            hypothetical_charges = sorted(reduce(lambda x,y: x+y,
                    [reebill.hypothetical_chargegroups_flattened(service) for service in
                    services]), key=lambda x:x['description'])
            for charge in actual_charges:
                charge['description'] = charge['description'] + ' (actual)'
            for charge in hypothetical_charges:
                charge['description'] = charge['description'] + ' (hypothetical)'

            # write each actual and hypothetical charge in a separate column,
            # creating new columns when necessary
            for charge in hypothetical_charges + actual_charges:
                try:
                    name = charge['chargegroup'] + ': ' + charge['description']
                    total = charge['total']
                except KeyError as key_error:
                    print >> sys.stderr, '%s-%s ERROR %s: %s' % (account,
                            sequence, key_error, pformat(charge))
                    error = True
                except IndexError as index_error:
                    print >> sys.stderr, '%s-%s ERROR %s: no hypothetical charge matching actual charge "%s"' % (account,
                            sequence, index_error, charge['chargegroup'] + ': ' + charge['description'])
                    error = True
                else:
                    # if this charge's name already exists in
                    # charge_names_columns, either put the total of that
                    # charge in the existing column with that charge's
                    # name, or create a new column
                    if name in charge_names_columns:
                        col = charge_names_columns[name]
                    else:
                        last_column += 1
                        charge_names_columns[name] = last_column
                        sheet.write(0, last_column, name)
                        col = last_column
                    try:
                        sheet.write(row, col, total)
                    except Exception as write_error:
                        if write_error.message.startswith('Attempt to overwrite cell:'):
                            # if charge descriptions are not unique within
                            # their group, xlwt attempts to overwrite an
                            # existing cell, which is an error: show that
                            # there was an error, but leave the existing
                            # charges as they are
                            error = True
                            print >> sys.stderr, '%s-%s ERROR %s: %s' % (
                                    account, sequence, write_error,
                                    pformat(charge))
                        else:
                            raise

            # account and sequence go in 1st 2 columns (show ERROR with
            # sequence if there was an error)
            sheet.write(row, 0, account)
            sheet.write(row, 1, sequence if not error else '%s: ERROR' % sequence)
            row += 1


    #def write_sheet(self, session, workbook, account, sequence, output_file):
        #if self.verbose:
            #print '%s-%s' % (account, sequence)
        #reebill = self.reebill_dao.load_reebill(account, sequence)

        ## each reebill gets its own sheet
        #sheet = workbook.add_sheet('%s-%s' % (account, sequence))

        ## write headers of 1st 2 columns
        ## (indices are row, column)
        #sheet.write(0, 0, 'Account')
        #sheet.write(0, 1,'Sequence')

        ## write charges starting at row 1
        #chargegroups = [reebill.chargegroups_flattened(service) for service in reebill.services]
        #row = 1
        #for chargegroup in chargegroups:
            #for charge in chargegroup:
                #try:
                    #group, description, total = charge['chargegroup'], charge['description'], charge['total']
                #except Exception as e:
                    #print '%s-%s ERROR %s: %s' % (account, sequence, e, pformat(charge))
                #else:
                    #sheet.write(row, 0, group)
                    #sheet.write(row, 1, description)
                    #sheet.write(row, 2, total)
                #row += 1

    #def export_all(self, statedb_session, output_file):
        #workbook = xlwt.Workbook(encoding="utf-8")
        #for account in sorted(self.state_db.listAccounts(statedb_session)):
            #for sequence in sorted(self.state_db.listSequences(statedb_session, account)):
                #self.write_sheet(statedb_session, workbook, account, sequence, output_file)
        #workbook.save(output_file)

def main():
    '''Run this file with the command line to test. Use account as argument, or
    no argument to make spreadsheet with all accounts. Output is saved in
    "spreadsheet.xls".'''

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

    if len(sys.argv) > 1:
        account = sys.argv[1]
    else:
        account = None

    session = state_db.session()
    with open('spreadsheet.xls', 'wb') as output_file:
        exporter.export(session, output_file, account=account)
    session.commit()


if __name__ == '__main__':
    main()
