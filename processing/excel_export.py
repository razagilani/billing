#!/usr/bin/env python2
import sys
from operator import itemgetter
import pymongo
import tablib
import traceback
from billing.processing import mongo
from billing.processing import state
from billing.util import dateutils
from billing.util.monthmath import approximate_month
from billing.processing.state import UtilBill, ReeBill, Customer
from billing.exc import *

import pprint
pformat = pprint.PrettyPrinter().pformat

LOG_FILE_NAME = 'xls_export.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'


class Exporter(object):
    '''Exports a spreadsheet with data about utility bill charges.'''

    def __init__(self, state_db, reebill_dao, verbose=False):
        # objects for database access
        self.state_db = state_db
        self.verbose = verbose
        self.reebill_dao = reebill_dao

    def export_account_charges(self, output_file, account=None,
                               start_date=None, end_date=None):
        '''
        Writes an Excel spreadsheet to output_file containing utility bills for
        the given account. If 'account' is not given, writes one sheet for each
        account. If neither 'start_date' nor 'end_date' is given, all utility
        bills for the given account(s) are output. If only 'start_date' is
        given, all utility bills after that date are output. If only 'end_date'
        are given, all utility bills before that date are output.
        '''
        book = tablib.Databook()
        if account == None:
            for acc in sorted(self.state_db.listAccounts()):
                book.add_sheet(
                    self.get_account_charges_sheet(acc,
                                                   start_date=start_date,
                                                   end_date=end_date))
        else:
            book.add_sheet(
                self.get_account_charges_sheet(account,
                                               start_date=start_date,
                                               end_date=end_date))
        output_file.write(book.xls)

    def get_account_charges_sheet(self, account, start_date=None,
                                  end_date=None):
        '''
        Returns a tablib Dataset consisting of all actual and hypothetical
        charges for all utility bills belonging to 'account'. Format: account &
        sequence in first 2 columns, later columns are charge names (i.e. pairs
        of charge group + charge description) in pairs (hypothetical and
        actual) with values wherever charges having those names occur. Utility
        bills with errors are skipped and an error message is printed. If either
        'start_date' or 'end_date' are included, they restrict the set of data
        returned based on their comparison to the fetched ReeBills'
        'period_start' and 'period_end' properties.
        '''
        # each account gets its own sheet. 1st 2 columns are account, sequence
        dataset = tablib.Dataset(title=account)
        dataset.headers = ['Account', 'Sequence', 'Period Start', 'Period End',
                           'Billing Month', 'Estimated']

        for sequence in sorted(self.state_db.listSequences(account)):
            reebill = self.state_db.get_reebill(account, sequence)

            # load utilbill from mysql to find out if the bill was
            # (utility-)estimated
            if not len(reebill.utilbills) == 1:
                continue    # Skip old reebills that are based
                            # on two utility bills
            assert len(reebill.utilbills) == 1
            utilbill = reebill.utilbills[0]
            estimated = utilbill.state == UtilBill.UtilityEstimated

            # new row. initially contains 6 columns: account, sequence, start,
            # end, fuzzy month, estimated?
            row = [
                account,
                sequence,
                utilbill.period_start.strftime(dateutils.ISO_8601_DATE),
                utilbill.period_end.strftime(dateutils.ISO_8601_DATE),
                # TODO rich hypothesizes that for utilities, the fuzzy "billing
                # month" is the month in which the billing period ends
                approximate_month(utilbill.period_start,
                                  utilbill.period_end).strftime('%Y-%m'),
                'Yes' if estimated else 'No'
            ]
            # pad row with blank cells to match dataset width
            row.extend([''] * (dataset.width - len(row)))

            # get all charges from this bill
            try:
                actual_charges = sorted(utilbill.charges,
                                        key=lambda c: c.description)
            except KeyError as e:
                print >> sys.stderr, ('%s-%s ERROR %s: %s' % (account,
                        sequence, e.message, traceback.format_exc()))
                continue

            # write each actual and hypothetical charge in a separate column,
            # creating new columns when necessary
            for charge in actual_charges:
                column_name = '%s: %s' % (charge.group, charge.description)
                total = charge.total

                if column_name in dataset.headers:
                    # Column already exists. Is there already something in the
                    # cell?
                    col_idx = dataset.headers.index(column_name)
                    if row[col_idx] == '':
                        row[col_idx] = ("%.2f" % total)
                    else:
                        row[col_idx] = ('ERROR: duplicate charge name'
                                                '"%s"') % column_name
                else:
                    # Add a new column 'column_name'
                    if dataset.height == 0:
                        dataset.headers.append(column_name)
                    else:
                        dataset.append_col([''] * dataset.height,
                                           header=column_name)
                    row.append(("%.2f" % total))
            dataset.append(row)
        return dataset

    def export_energy_usage(self, output_file, account=None):
        '''
        Writes an Excel spreadsheet to output_file containing utility bills for
        the given account. If 'account' is not given, writes one sheet for each
        account.
        ( period start, period end, total energy, rate class, and one column per
        charge) the given account. If 'account' is not given, writes one sheet
        for each account.
        '''
        book = tablib.Databook()
        if account == None:
            #Only export brokerage accounts (id>20000)
            for acc in [
                x for x in sorted(self.state_db.listAccounts()) if
                    (int(x) >= 20000)]:
                utilbills, _ = self.state_db.list_utilbills(acc)
                book.add_sheet(self.get_energy_usage_sheet(utilbills))
        else:
            utilbills = self.state_db.list_utilbills(account)
            book.add_sheet(self.get_energy_usage_sheet(utilbills))
        output_file.write(book.xls)

    def get_energy_usage_sheet(self, utilbills):
        '''
        Returns a tablib Dataset consisting of a period start,
        period end, total energy, rate class, and one column per
        charge for all 'utilbills'.
        '''
        account = ''
        # Initital datasheet headers
        ds_headers = ['Account', 'Rate Class', 'Total Energy', 'Units',
                      'Period Start', 'Period End']
        # Initial datasheet rows
        ds_rows = []
        for ub in utilbills:

            units = quantity = ''
            account = ub.customer.account
            try:
                # Find the register whose binding is reg_total and get the quantity and units
                ub_doc = self.reebill_dao._load_utilbill_by_id(
                ub.document_id)
                for register in mongo.get_all_actual_registers_json(ub_doc):
                    if register.get('binding', '').lower() == 'reg_total':
                        units = register.get('quantity_units', '')
                        quantity = register.get('quantity', '')
            except NoSuchBillException:
                units = quantity = "ERROR"
            # Create a row
            row = [ub.customer.account,
                   ub.rate_class,
                   quantity, units,
                   ub.period_start.strftime(dateutils.ISO_8601_DATE),
                   ub.period_end.strftime(dateutils.ISO_8601_DATE)]
            # Find all Insert register binding hereactual chagres connected to this utility bill
            actual_charges = sorted(ub.charges,
                                    key=lambda c: c.description)
            # write each actual charge in a separate column,
            # creating new columns when necessary
            for charge in actual_charges:
                try:
                    if charge.group:
                        name = '%s: %s' % (charge.group, charge.description)
                    else:
                        name = charge.description
                    total = charge.total
                except KeyError as key_error:
                    print >> sys.stderr, '%s KEY ERROR %s: %s' % (
                        ub.customer.account, key_error, pformat(charge))
                else:
                    # pad row with empty values up to the length of the header
                    # if this charge header doesn't exists. Then append the total
                    row += [''] * (len(ds_headers) - len(row))
                    if name in ds_headers:
                        # get existing column whose header is the charge name
                        col_idx = ds_headers.index(name)
                        # write cell in existing column
                        try:
                            if row[col_idx] == '':
                                row[col_idx] = total
                            else:
                                row[col_idx] = ('ERROR: duplicate charge name'
                                                '"%s"') % name
                        except IndexError as index_error:
                            raise
                    else:
                        # header doesn't exists, append a new one
                        ds_headers.append(name)
                        row.append(total)
                # add row to dataset
            ds_rows.append(row)
            # Bring the dataset to uniform dimensions by padding
        # all rows up to the length of the final header
        for row in ds_rows:
            row.extend([''] * (len(ds_headers) - len(row)))
        dataset = tablib.Dataset(
            *ds_rows, headers=ds_headers, title=account)
        return dataset

    def export_reebill_details(self, output_file, begin_date=None,
                               end_date=None):
        '''
        Writes an Excel spreadsheet to output_file. This Spreadsheet is
        intended to give a general overview ove reebill. It contains details
        of all issued reebills and related payments for all accounts and
        calculates cumulative savings and RE&E energy
        '''

        accounts = self.state_db.listAccounts()
        dataset = self.get_export_reebill_details_dataset(
            accounts, begin_date, end_date)
        workbook = tablib.Databook()
        workbook.add_sheet(dataset)
        output_file.write(workbook.xls)

    def get_export_reebill_details_dataset(self, accounts, begin_date,
                                           end_date):
        ''' Helper method for export_reebill_details_xls: extracts details
        data from issued  reebills and related payments for all accounts and
        calculates cumulative savings and RE&E energy.

        Columns containing data about reebills:

        Account - Needed because this is how customer information is looked up in Nexus
        Sequence - Because account and sequence are used to identify ReeBills
        Version - Because the amount of ReeBilling churn should be visible
        Billing Addressee - Needed to for account management/maintenance reasons
        Service Addressee - Needed to for account management/maintenance reasons
        Issue Date - Needed to determine how far along or not the bill processing cycle is
        Period Begin - Needed for a variety of reasons to determine when utility bills need to be downloaded.
        Period End - Needed for a variety of reasons to determine when utility bills need to be downloaded.
        Hypothesized Charges (total) - Needed to sanity check ReeBills and
        find  billing errors
        Actual Utility Charges (total)- Needed to sanity check ReeBills and
        find  billing errors
        RE&E Value - Needed for various dashboard/reporting purposes/requests
        Prior Balance - Accounting (All accounting needs related to QuickBooks)
        Payment Applied (in a particular reebill) - Accounting
        Adjustment - Accounting
        Balance Forward - Accounting
        RE&E Charges - Accounting
        Late Charges - Accounting
        Balance Due - Accounting
        Savings - Customer reporting/sales
        Cumulative Savings - Customer reporting/sales
        RE&E Energy - Needed to sanity check OLAP
        Average Rate per Unit RE&E during the billing period (Total RE/Energy
        Sold)- Needed to sanity check sales proposals

        Columns containing data about payments:
            Payment Date
            Payment Amount

        Since payment columns are not associated with reebills, ether the
        reebill columns or the payment columns of each row will be filled in,
        but not both. The relative ordering of reebill rows and payment
        rows is indeterminate (though it could be done by reebill Issue
        Date and Payment Date).
        '''

        ds_rows = []

        for account in accounts:
            payments = self.state_db.payments(account)
            cumulative_savings = 0

            reebills = self.state_db.listReebills(0, 10000,
                    account, u'sequence', u'ASC')[0]
            for reebill in reebills:
                # Skip over unissued reebills
                if not reebill.issued==1:
                    continue

                # Reebills with > 1 utilitybills are no longer supported.
                # Skip them
                if len(reebill.utilbills) > 1:
                    continue

                period_start, period_end = reebill.get_period()

                # if the user has chosen a begin and/or end date *and* this
                # reebill falls outside of its bounds, skip to the next one
                reebill_in_period = False
                if begin_date:
                    if period_start >= begin_date:
                        reebill_in_period = True
                if end_date:
                    if period_end <= end_date:
                        reebill_in_period = True
                if (begin_date or end_date) and not reebill_in_period:
                    continue

                # iterate the payments and find the ones that apply.
                if period_start and period_end:
                    applicable_payments = filter(
                        lambda x: period_start <= x.date_applied.date() <
                                  period_end,
                        payments)
                    # pop the ones that get applied from the payment list
                    # (there is a bug due to the reebill periods overlapping,
                    # where a payment may be applicable more than ones)
                    for applicable_payment in applicable_payments:
                        payments.remove(applicable_payment)

                savings = 0
                if reebill.ree_value and reebill.ree_charge:
                    savings = reebill.ree_value - reebill.ree_charge
                cumulative_savings += savings

                # The first payment applied to a bill is listed in the same row
                # All additional payments are seperate rows
                payment_date = None
                payment_amount = None
                if applicable_payments:
                    payment_date = applicable_payments[0].date_applied.date().isoformat()
                    payment_amount = applicable_payments[0].credit
                    applicable_payments.pop(0)

                average_rate_unit_ree=None
                actual_total = reebill.get_total_actual_charges()
                hypothetical_total = reebill.get_total_hypothetical_charges()

                total_ree = reebill.get_total_renewable_energy()
                if total_ree != 0:
                    average_rate_unit_ree = ((hypothetical_total-actual_total)
                                             / total_ree)

                row = [account,
                       reebill.sequence,
                       reebill.version,
                       str(reebill.billing_address),
                       str(reebill.service_address),
                       reebill.issue_date.isoformat(),
                       period_start.isoformat(),
                       period_end.isoformat(),
                       hypothetical_total,
                       actual_total,
                       reebill.ree_value,
                       reebill.prior_balance,
                       reebill.payment_received,
                       payment_date,
                       payment_amount,
                       reebill.total_adjustment,
                       reebill.balance_forward,
                       reebill.ree_charge,
                       reebill.late_charge,
                       reebill.balance_due,
                       '', #spacer
                       savings,
                       cumulative_savings,
                       total_ree,
                       average_rate_unit_ree
                       ]

                # Formatting
                # The following columns are numbers with two decimals
                for i in (8, 9, 10, 11, 12, 14, 15, 16, 17, 19, 21, 22, 23, 24):
                    try:
                        row[i] = ("%.2f" % row[i])
                    except TypeError:
                        pass
                ds_rows.append(row)

                # For each additional payment include a row containing
                # only account, reebill and payment data
                for applicable_payment in applicable_payments:
                    # ok, there was more than one applicable payment
                    row = [account, reebill.sequence, reebill.version,
                           None, None, None, None, None,
                           None, None, None, None, None,
                           applicable_payment.date_applied.date().isoformat(),
                           applicable_payment.credit,
                           None, None, None, None, None,
                           None, None, None, None, None]
                    row[14] = ("%.2f" % row[14])
                    ds_rows.append(row)

        # We got all rows! Assemble the dataset
        ds_headers = ['Account', 'Sequence', 'Version',
                      'Billing Addressee', 'Service Addressee',
                      'Issue Date', 'Period Begin', 'Period End',
                      'Hypothesized Charges', 'Actual Utility Charges',
                      'RE&E Value',
                      'Prior Balance',
                      'Payment Applied',
                      'Payment Date',
                      'Payment Amount',
                      'Adjustment',
                      'Balance Forward',
                      'RE&E Charges',
                      'Late Charges',
                      'Balance Due',
                      '',  # spacer
                      'Savings',
                      'Cumulative Savings',
                      'RE&E Energy',
                      'Average Rate per Unit RE&E',
        ]
        dataset = tablib.Dataset(*ds_rows, headers=ds_headers,
                                 title='All REE Charges')
        return dataset


def main(export_func, filename, account=None):
    '''Run this file with the command line to test.
    Arguments:  Export type 'energy' or 'charges' (optional, uses 'energy' )
                Account number (optional, uses all accounts or standard range)
    Saves output in "spreadsheet.xls".'''
    from os.path import dirname, realpath, join
    from billing import init_config, init_model, init_logging

    p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
    init_logging(path=p)
    init_config(filename=p)
    init_model()
    from billing import config
    import logging

    logger = logging.getLogger('reebill')
    state_db = state.StateDB(logger=logger)
    billdb_config = dict(config.items("billdb"))
    reebill_dao = mongo.ReebillDAO(state_db,
                pymongo.Connection(billdb_config['host'],
                int(billdb_config['port']))[billdb_config['database']])

    exporter = Exporter(state_db, reebill_dao)

    with open(filename, 'wb') as output_file:
        if export_func == 'energy':
            exporter.export_energy_usage(output_file, account=account)
        elif export_func == 'reebill_details':
            exporter.export_reebill_details(output_file)
        else:
            exporter.export_account_charges(output_file,
                                            account=account)

if __name__ == '__main__':
    filename = 'spreadsheet.xls'
    export_func = ''
    account = None
    if len(sys.argv) > 1:
        export_func = sys.argv[1]
    if len(sys.argv) > 2:
        account = sys.argv[2]
    main(export_func, filename, account)
