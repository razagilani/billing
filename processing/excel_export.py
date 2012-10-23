#!/usr/bin/python
import os
import sys
import tablib
from billing.processing import mongo
from billing.processing import state
from billing import dateutils
from billing.monthmath import approximate_month
from billing.processing.db_objects import UtilBill, ReeBill, Customer

import pprint
pformat = pprint.PrettyPrinter().pformat

LOG_FILE_NAME = 'xls_export.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

class Exporter(object):
    '''Exports a spreadsheet with data about utility bill charges.'''

    def __init__(self, state_db, reebill_dao, verbose=False):
        # objects for database access
        self.state_db = state_db
        self.reebill_dao = reebill_dao
        self.verbose = verbose

    def export(self, statedb_session, output_file, account=None):
        '''Writes an Excel spreadsheet to output_file containing all utility
        bills for the given account. If 'account' is not given, writes one
        sheet for each account.'''
        book = tablib.Databook()
        if account == None:
            for acc in sorted(self.state_db.listAccounts(statedb_session)):
                book.add_sheet(self.get_account_sheet(statedb_session, acc))
        else:
            book.add_sheet(self.get_account_sheet(statedb_session, account))
        output_file.write(book.xls)

    def get_account_sheet(self, statedb_session, account):
        '''Returns a tablib Dataset consisting of all actual and hypothetical
        charges for all utility bills belonging to 'account'. Format: account &
        sequence in first 2 columns, later columns are charge names (i.e. pairs
        of charge group + charge description) in pairs (hypothetical and
        actual) with values wherever charges having those names occur. Utility
        bills with errors are skipped and an error message is printed.'''
        # each account gets its own sheet. 1st 2 columns are account, sequence
        dataset = tablib.Dataset(title=account)
        dataset.headers = ['Account', 'Sequence', 'Period Start', 'Period End',
                'Billing Month', 'Estimated']

        # load customer from MySQL in order to load reebill and utilbill below
        customer = statedb_session.query(Customer)\
                .filter(Customer.account==account).one()

        for sequence in sorted(self.state_db.listSequences(statedb_session,
                account)):
            if self.verbose:
                print '%s-%s' % (account, sequence)

            reebill = self.reebill_dao.load_reebill(account, sequence)

            # load reebill from MySQL in order to load utilbill below
            rb = statedb_session.query(ReeBill)\
                    .filter(ReeBill.customer==customer)\
                    .filter(ReeBill.sequence==sequence).one()

            # load utilbill from mysql to find out if the bill was
            # (utility-)estimated
            utilbills = statedb_session.query(UtilBill)\
                    .filter(UtilBill.reebill==rb)
            estimated = any([u.state == UtilBill.UtilityEstimated
                    for u in utilbills])
            if utilbills == []:
                print 'No utilbills in MySQL for %s-%s' % (account, sequence)
                estimated = False

            # new row. initially contains 5 columns: account, sequence, start,
            # end, fuzzy month
            row = [
                account,
                #sequence if not error else '%s: ERROR' % sequence,
                sequence,
                reebill.period_begin.strftime(dateutils.ISO_8601_DATE),
                reebill.period_end.strftime(dateutils.ISO_8601_DATE),
                # TODO rich hypothesizes that for utilities, the fuzzy "billing
                # month" is the month in which the billing period ends
                approximate_month(reebill.period_begin,
                        reebill.period_end).strftime('%Y-%m'),
                'Yes' if estimated else 'No'
            ]
            # pad row with blank cells to match dataset width
            row.extend([''] * (dataset.width - len(row)))

            # this becomes true if there was any error reading data for this
            # row
            error = False
            # TODO put error in cell

            # get all charges from this bill in "flattened" format, sorted by
            # name, with (actual) or (hypothetical) appended
            services = reebill.services
            actual_charges = sorted(reduce(lambda x,y: x+y,
                    [reebill.actual_chargegroups_flattened(service)
                    for service in services]), key=lambda x:x['description'])
            hypothetical_charges = sorted(reduce(lambda x,y: x+y,
                    [reebill.hypothetical_chargegroups_flattened(service)
                    for service in services]), key=lambda x:x['description'])
            for charge in actual_charges:
                charge['description'] += ' (actual)'
            for charge in hypothetical_charges:
                charge['description'] += ' (hypothetical)'
            # extra charges: actual and hypothetical totals, difference between
            # them, Skyline's late fee from the reebill
            actual_total = sum(ac.get('total', 0) for ac in actual_charges)
            hypothetical_total = sum(hc.get('total', 0) for hc in hypothetical_charges)
            extra_charges = [
                { 'description': 'Actual Total', 'total': actual_total },
                { 'description': 'Hypothetical Total', 'total': hypothetical_total },
                {
                    'description': 'Energy Offset Value (Hypothetical - Actual)',
                    'total': hypothetical_total - actual_total,
                },
                {
                    'description': 'Skyline Late Charge',
                    'total': reebill.late_charges \
                            if hasattr(reebill, 'late_charges') else 0
                },
            ]

            # write each actual and hypothetical charge in a separate column,
            # creating new columns when necessary
            for charge in hypothetical_charges + actual_charges + extra_charges:
                try:
                    if 'chargegroup' in charge:
                        name = '{chargegroup}: {description}'.format(**charge)
                    else:
                        # totals do not have a chargegroup
                        name = charge['description']
                    total = charge['total']
                except KeyError as key_error:
                    print >> sys.stderr, '%s-%s ERROR %s: %s' % (account,
                            sequence, key_error, pformat(charge))
                    error = True
                except IndexError as index_error:
                    print >> sys.stderr, ('%s-%s ERROR %s: no hypothetical '
                            'charge matching actual charge "%s"') % (account,
                            sequence, index_error, charge['chargegroup'] +
                            ': ' + charge['description'])
                    error = True
                else:
                    # if this charge's name already exists in
                    # charge_names_columns, either put the total of that charge
                    # in the existing column with that charge's name, or create
                    # a new column
                    if name in dataset.headers:
                        # get existing column whose header is the charge name
                        col_idx = dataset.headers.index(name)
                        try:
                            if row[col_idx] == '':
                                row[col_idx] = total
                            else:
                                row[col_idx] = ('ERROR: duplicate charge name'
                                        '"%s"') % name
                        # write cell in existing column
                        except IndexError as index_error:
                            #import ipdb; ipdb.set_trace()
                            raise
                    else:
                        # add new column: first add all-blank column to
                        # existing dataset, then put total in a new cell at the
                        # end of the row
                        #dataset.append_col([''] * dataset.height, header=name)
                        # TODO https://github.com/kennethreitz/tablib/issues/64
                        if dataset.height == 0:
                            dataset.headers.append(name)
                        else:
                            dataset.append_col([''] * dataset.height,
                                    header=name)
                        row.append(str(total))
            dataset.append(row)

        return dataset


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
        'host': 'localhost',
        'password': 'dev',
        'database': 'skyline_dev',
        'user': 'dev'
    }
    state_db = state.StateDB(**statedb_config)

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
