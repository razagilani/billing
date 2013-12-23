#!/usr/bin/env python2
import os
import sys
from itertools import chain
from operator import itemgetter
import pymongo
import tablib

from billing.processing import mongo
from billing.processing import state
from billing.util import dateutils
from billing.util.monthmath import approximate_month
from billing.processing.state import UtilBill, ReeBill, Customer
from billing.processing.exceptions import *

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

    def export_account_charges(self, statedb_session, output_file, account=None,
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
            for acc in sorted(self.state_db.listAccounts(statedb_session)):
                book.add_sheet(
                    self.get_account_charges_sheet(statedb_session, acc,
                                                   start_date=start_date,
                                                   end_date=end_date))
        else:
            book.add_sheet(
                self.get_account_charges_sheet(statedb_session, account,
                                               start_date=start_date,
                                               end_date=end_date))
        output_file.write(book.xls)

    def get_account_charges_sheet(self, statedb_session, account,
                                  start_date=None,
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

        # load customer from MySQL in order to load reebill and utilbill below
        customer = statedb_session.query(Customer) \
            .filter(Customer.account == account).one()

        for sequence in sorted(self.state_db.listSequences(statedb_session,
                                                           account)):
            if self.verbose:
                print '%s-%s' % (account, sequence)

            reebill = self.reebill_dao.load_reebill(account, sequence)

            ## if this reebill is not inside of the given date range, skip this
            ## iteration
            #if (start_date and reebill.period_start >= start_date) \
            #or (end_date and reebill.period_end <= end_date):

            # load reebill from MySQL in order to load utilbill below
            rb = statedb_session.query(ReeBill) \
                .filter(ReeBill.customer == customer) \
                .filter(ReeBill.sequence == sequence) \
                .filter(
                ReeBill.version == self.state_db.max_version(statedb_session,
                                                             account,
                                                             sequence)).one()

            # load utilbill from mysql to find out if the bill was
            # (utility-)estimated
            utilbills = rb.utilbills
            mongo_utilbills = self.reebill_dao.load_utilbills(
                account=rb.customer.account,
                sequence=rb.sequence,
                version=rb.version)
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
            actual_charges = sorted(chain.from_iterable(
                mongo.actual_chargegroups_flattened(m_ub)
                for m_ub in mongo_utilbills), key=itemgetter('description'))
            hypothetical_charges = sorted(chain.from_iterable(
                reebill.hypothetical_chargegroups_flattened(service)
                for service in services), key=itemgetter('description'))
            for charge in actual_charges:
                charge['description'] += ' (actual)'
            for charge in hypothetical_charges:
                charge['description'] += ' (hypothetical)'
                # extra charges: actual and hypothetical totals, difference between
            # them, Skyline's late fee from the reebill
            actual_total = sum(ac.get('total', 0) for ac in actual_charges)
            hypothetical_total = float(
                sum(hc.get('total', 0) for hc in hypothetical_charges))
            extra_charges = [
                {'description': 'Actual Total', 'total': actual_total},
                {'description': 'Hypothetical Total',
                 'total': hypothetical_total},
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
                                                                 sequence,
                                                                 key_error,
                                                                 pformat(
                                                                     charge))
                    error = True
                except IndexError as index_error:
                    print >> sys.stderr, ('%s-%s ERROR %s: no hypothetical '
                                          'charge matching actual charge "%s"') % (
                        account,
                        sequence, index_error,
                        charge['chargegroup'] +
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
            #else:
            #if self.verbose:
            #print 'skipping %s-%s as it falls outside of [%s,%s]' % (account, sequence, start_date, end_date)

        return dataset

    def export_energy_usage(self, statedb_session, output_file, account=None):
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
            #Only export XBill accounts (id>20000)
            for acc in [x for x in
                        sorted(self.state_db.listAccounts(statedb_session)) if
                        (int(x) >= 20000)]:
                book.add_sheet(
                    self.get_energy_usage_sheet(statedb_session, acc))
        else:
            book.add_sheet(
                self.get_energy_usage_sheet(statedb_session, account))
        output_file.write(book.xls)

    def get_energy_usage_sheet(self, statedb_session, account):
        '''
        Returns a tablib Dataset consisting of a period start,
        period end, total energy, rate class, and one column per
        charge for all utility bills belonging to 'account'.
        '''
        # Initital datasheet headers
        ds_headers = ['Account', 'Rate Structure', 'Total Energy', 'Units',
                      'Period Start', 'Period End']
        # Initial datasheet rows
        ds_rows = []
        mongo_utilbills = self.reebill_dao.load_utilbills(account=account)
        for m_ub in mongo_utilbills:
            units = quantity = ''
            # Find the register whose binding is reg_total and get the quantity and units
            for register in mongo.get_all_actual_registers_json(m_ub):
                if register.get('binding', '').lower() == 'reg_total':
                    units = register.get('quantity_units', '')
                    quantity = register.get('quantity', '')
                # Create a row
            row = [account,
                   m_ub.get("rate_structure_binding", ''),
                   quantity, units,
                   m_ub.get("start", '').strftime(dateutils.ISO_8601_DATE),
                   m_ub.get("end", '').strftime(dateutils.ISO_8601_DATE)]
            # Find all actual chagres connected to this utility bill
            actual_charges = sorted(mongo.actual_chargegroups_flattened(m_ub),
                                    key=itemgetter('description'))
            # write each actual charge in a separate column,
            # creating new columns when necessary
            for charge in actual_charges:
                try:
                    if 'chargegroup' in charge:
                        name = '{chargegroup}: {description}'.format(**charge)
                    else:
                        # totals do not have a chargegroup
                        name = charge['description']
                    total = charge['total']
                except KeyError as key_error:
                    print >> sys.stderr, '%s KEY ERROR %s: %s' % (account,
                                                                  key_error,
                                                                  pformat(
                                                                      charge))
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
        dataset = tablib.Dataset(*ds_rows, headers=ds_headers, title=account)
        return dataset

    def export_reebill_details(self, session, output_file, begin_date=None,
                               end_date=None):
        '''
        Writes an Excel spreadsheet to output_file. This Spreadsheet is
        intended to give a general overview ove reebill. It contains details
        of all issued reebills and related payments for all accounts and
        calculates cumulative savings and RE&E energy
        '''

        dataset = self.get_export_reebill_details_dataset(session, begin_date,
                                                          end_date)
        workbook = tablib.Databook()
        workbook.add_sheet(dataset)
        output_file.write(workbook.xls)

    def get_export_reebill_details_dataset(self, session, begin_date, end_date):
        ''' Extracts details data from issued reebills
        and related payments for all accounts and
        calculates cumulative savings and RE&E energy '''

        # Method to format the Service address/Billin address in a Reebill
        def format_addr(addr):
            addr_str = "%s %s %s %s %s" % (
                addr['addressee'] if 'addressee' in addr and addr[
                    'addressee'] is not None else "",
                addr['street'] if 'street' in addr and addr[
                    'street'] is not None else "",
                addr['city'] if 'city' in addr and addr[
                    'city'] is not None else "",
                addr['state'] if 'state' in addr and addr[
                    'state'] is not None else "",
                addr['postal_code'] if 'postal_code' in addr and addr[
                    'postal_code'] is not None else "",
            )
            return addr_str

        # Create the dataset rows
        accounts = self.state_db.listAccounts(session)
        ds_rows = []
        for account in accounts:
            payments = self.state_db.payments(session, account)
            cumulative_savings = 0
            try:
                reebills= self.reebill_dao.load_reebills_for(account, 0)
            except NoSuchBillException:
                # A bill exists in MySQL, but not in mongo. Ignore this bill
                pass
            for reebill_doc in reebills:
                reebill = self.state_db.get_reebill(session,account,reebill_doc.sequence,
                                               reebill_doc.version)
                # Skip over unissued reebills
                if not reebill.issued==1:
                    continue
                # if the user has chosen a begin and/or end date *and* this
                # reebill falls outside of its bounds, skip to the next one
                have_period_dates = begin_date or end_date
                reebill_begins_in_this_period = begin_date and reebill_doc.period_begin >= begin_date
                reebill_ends_in_this_period = end_date and reebill_doc.period_end <= end_date
                reebill_in_this_period = reebill_begins_in_this_period or reebill_ends_in_this_period
                if have_period_dates and not reebill_in_this_period: continue

                # iterate the payments and find the ones that apply.
                if (reebill_doc.period_begin is not None and reebill_doc.period_end is not None):
                    applicable_payments = filter(lambda x: x.date_applied >
                            reebill_doc.period_begin and x.date_applied <
                            reebill_doc.period_end, payments)
                    # pop the ones that get applied from the payment list
                    # (there is a bug due to the reebill periods overlapping,
                    # where a payment may be applicable more than ones)
                    for applicable_payment in applicable_payments:
                        payments.remove(applicable_payment)

                savings = reebill_doc.ree_value - reebill_doc.ree_charges
                cumulative_savings += savings

                # The first payment applied to a bill is listed in the same row
                # All additional payments are seperate rows
                payment_date = None
                payment_amount = None
                if applicable_payments:
                    payment_date = applicable_payments[0].date_applied.isoformat()
                    payment_amount = applicable_payments[0].credit
                    applicable_payments.pop(0)

                average_rate_unit_ree=None
                try:
                    total_ree = reebill_doc.total_renewable_energy()
                    if total_ree != 0:
                        average_rate_unit_ree = (reebill_doc.hypothetical_total -
                                reebill_doc.actual_total)/total_ree
                except StopIteration:
                    # A bill didnt have registers, ignore this column
                    total_ree = 'Error! No Registers found!'
                try:
                    late_charges = reebill_doc.late_charges
                except KeyError:
                    late_charges = None

                row = [account,
                       reebill_doc.sequence,
                       reebill_doc.version,
                       format_addr(reebill_doc.billing_address),
                       format_addr(reebill_doc.service_address),
                       reebill.issue_date.isoformat(),
                       reebill_doc.period_begin.isoformat(),
                       reebill_doc.period_end.isoformat(),
                       reebill_doc.hypothetical_total,
                       reebill_doc.actual_total,
                       reebill_doc.ree_value,
                       reebill_doc.prior_balance,
                       reebill_doc.payment_received,
                       payment_date,
                       payment_amount,
                       reebill_doc.total_adjustment,
                       reebill_doc.balance_forward,
                       reebill_doc.ree_charges,
                       late_charges,
                       reebill_doc.balance_due,
                       '', #spacer
                       savings,
                       cumulative_savings,
                       total_ree,
                       average_rate_unit_ree
                       ]
                ds_rows.append(row)

                # For each additional payment include a row containing
                # only account, reebill and payment data
                for applicable_payment in applicable_payments:
                    # ok, there was more than one applicable payment
                    row = [ account, reebill_doc.sequence, reebill_doc.version,
                            None, None, None, None, None,
                            None, None, None, None, None,
                           applicable_payment.date_applied.isoformat(),
                           applicable_payment.credit,
                            None, None, None, None, None,
                            None, None, None, None, None]
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
                    '', # spacer
                    'Savings',
                    'Cumulative Savings',
                    'RE&E Energy',
                    'Average Rate per Unit RE&E',
        ]
        dataset = tablib.Dataset(*ds_rows, headers=ds_headers,
                                 title='All REE Charges')
        return dataset


def main(export_func, filename):
    '''Run this file with the command line to test.
    Arguments:  Export type 'energy' or 'charges' (optional, uses 'energy' )
                Account number (optional, uses all accounts or standard range)
    Saves output in "spreadsheet.xls".'''

    billdb_config = {
        'database': 'skyline-dev',
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
    reebill_dao = mongo.ReebillDAO(state_db,
                         pymongo.Connection(billdb_config['host'],
                                            int(billdb_config['port']))[
                             billdb_config['database']])
    exporter = Exporter(
        state_db,
        reebill_dao
    )
    session = state_db.session()
    with open(filename, 'wb') as output_file:
        if export_func == 'energy':
            exporter.export_energy_usage(session, output_file, account=account)
        elif export_func == 'reebill_details':
            exporter.export_reebill_details(session, output_file)
        else:
            exporter.export_account_charges(session, output_file,
                                            account=account)
    session.commit()


if __name__ == '__main__':
    filename = 'spreadsheet.xls'
    export_func = 'reebill_details'
    if len(sys.argv) > 1:
        export_func = sys.argv[1]
    elif len(sys.argv) > 2:
        account = sys.argv[2]
    else:
        account = None
    main(export_func, filename)
