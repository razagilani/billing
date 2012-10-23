import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from calendar import Calendar
from collections import defaultdict
import tablib
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner import sky_handlers
from billing.processing.process import Process
from billing.dateutils import estimate_month, month_offset, months_of_past_year, date_generator, date_to_datetime
from billing.nexus_util import NexusUtil
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state
from billing.processing.state import StateDB
from billing.processing.mongo import ReebillDAO
from billing.dictutils import deep_map
from billing import dateutils
from billing.processing.monthmath import Month, months_of_past_year

import pprint
pp = pprint.PrettyPrinter(indent=4).pprint
sys.stdout = sys.stderr

calendar = Calendar()

class NoRateError(Exception):
    '''Raised when a there's no per-therm energy price for a given account and
    sequence.'''
    pass

class EstimatedRevenue(object):

    def __init__(self, state_db, reebill_dao, ratestructure_dao, billupload, nexus_util, splinter):
        self.state_db = state_db
        self.reebill_dao = reebill_dao
        self.splinter = splinter
        self.monguru = splinter.get_monguru()
        self.ratestructure_dao = ratestructure_dao
        self.process = Process(state_db, reebill_dao, ratestructure_dao,
                billupload, nexus_util, splinter)

        # pre-load all the olap ids of accounts for speed (each one requires an
        # HTTP request)
        session = self.state_db.session()
        self.olap_ids = dict([
            (account, nexus_util.olap_id(account)) for account in
            self.state_db.listAccounts(session)
        ])
        session.commit()

        # cache of already-loaded reebills for speed--will become especially
        # useful if we start re-computing bills before using their energy, so
        # they need to be recomputed only once
        self.reebill_cache = {}

        # cache of average energy prices ($/therm) by account, month
        self.rate_cache = {}

    def report(self, session, accounts=None, failfast=False):
        '''Returns a dictionary containing data about real and renewable energy
        charges in reebills for 'accounts' in the past year (or all accounts,
        if 'accounts' is not given). Keys are (year, month) tuples. Each value
        is a dictionary whose key is an account (or 'total') and whose value is
        a dictionary containing real or estimated renewable energy charge in
        all reebills whose approximate calendar month was or probably will be
        that month, and a boolean representing whether that value was
        estimated.

        If there was an error, and 'failfast' is False, an Exception is put in
        the dictionary with the key "error", and "value" and "estimated" keys
        are omitted. The monthly total only includes accounts for which there
        wasn't an error.

        If 'failfast' is True, Exceptions are raised immediately rather than
        stored (for debugging).

        Dictionary structure is like this:
        {
            10001 : {
                (2012,1): {
                    "value": $,
                    "estimated": False
                },
                (2012,2): {
                    "value": $,
                    "estimated": True
                },
                (2012,3): {
                    "error": "Error Message"
                },
                ...
            }
            ...
        }
        '''
        print 'Generating estimated revenue report'

        # dictionary account -> (Month -> { monthtly data })
        # by default, value is 0 and it's not estimated
        data = defaultdict(lambda: defaultdict(lambda:
                {'value':0., 'estimated': False}))

        # use all accounts if 'accounts' argument was not given
        if accounts == None:
            accounts = self.state_db.listAccounts(session)

        for account in accounts:
            last_issued_sequence = self.state_db.last_sequence(session,
                    account)
            if last_issued_sequence > 0:
                last_reebill_end = self._load_reebill(account,
                        last_issued_sequence).period_end
            else:
                last_reebill_end = None

            for month in months_of_past_year():
                try:
                    # get all issued bills that have any part of their periods
                    # inside this month--possibly including a hypothetical bill
                    # whose period would be in this month if it existed. (note
                    # that un-issued bills effectively don't exist for this
                    # purpose, since they may have 0 energy in them).
                    sequences = self.process.sequences_in_month(session,
                            account, month.year, month.month)

                    # if there are no sequences, skip (value is 0 by default)
                    if sequences == []:
                        continue

                    # for each sequence, get the approximate portion of the
                    # corresponding bill's actual or estimated revenue that was
                    # generated during this month, and add that revenue to the
                    # total for this month
                    for seq in sequences:
                        if seq <= last_issued_sequence:
                            # issued bill: get approximate portion of its
                            # revenue during this month
                            this_month_energy_for_sequence = self.\
                                    _quantize_revenue_in_month(session,
                                    account, seq, month)
                        else:
                            # not an issued bill: period starts at start of
                            # month or end of last issued bill period,
                            # whichever comes later, and ends at end of month
                            if last_reebill_end is None:
                                start = month.first
                            else:
                                start = max(month.first, last_reebill_end)
                            this_month_energy_for_sequence = self.\
                                    _estimate_ree_charge(session, account,
                                    start, month.last)
                            # a single estimated bill makes the whole month's
                            # revenue estimated
                            data[account][month]['estimated'] = True

                        data[account][month]['value'] += this_month_energy_for_sequence
                except Exception as e:
                    if failfast:
                        raise
                    data[account][month] = {'error': e}
                    print '%s %s ERROR: %s' % (account, month, e)

        # compute total
        for month in months_of_past_year():
            # add up revenue for all accounts in this month
            data['total'][month]['value'] = sum(data[acc][month].get('value', 0)
                    for acc in accounts if not isinstance(data[acc][month],
                        Exception))

            # total value is estimated iff any estimated bills contributed to
            # it (errors are treated as non-estimated zeroes). this will almost
            # certainly be true because utility bills for the present month
            # have not even been received.
            data['total'][month]['estimated'] = any(data[acc][month].get('estimated',False) == True for acc in accounts)

        return data


    def report_table(self, session, failfast=False):
        '''Returns a Tablib table of the data produced in report().'''
        report = self.report(session, failfast=failfast)
        table = tablib.Dataset()
        table.headers = ['Account'] + [str(month) for month in months_of_past_year()]

        for account in sorted(report.keys()):
            row = [account]
            for month in sorted(report[account]):
                # note that 'estimated' is ignored because we can't easily
                # display it in a tabular format
                cell_data = report[account][month]
                if 'value' in cell_data:
                    value = cell_data['value']
                else:
                    value = 'ERROR: %s' % cell_data['error']
                row.append(value)
            table.append(row)
        return table

    def write_report_xls(self, session, output_file):
        '''Writes an Excel spreadsheet of the data produced in report() to
        'output_file'.'''
        table = self.report_table(session)
        output_file.write(table.xls)

    def _quantize_revenue_in_month(self, session, account, sequence, month):
        '''Returns the approximate amount of energy from the reebill given by
        account and sequence during the given month, assuming the energy was
        evenly distributed over time.'''
        print 'quantizing revenue for %s in %s' % (account, month)

        # Rich says we should rely on OLTP, not on the bill, because even if
        # the bill shows what we actually charged someone, OLTP is a better
        # representation of how much revenue was actually generated because a
        # discrepancy between the bill and OLTP means the bill will have to be
        # re-issued. Bills are gospel, OTLP is truth.
        # However, due to our rate structure implementation, the only way we
        # can price the energy from a bill during a particular time period is
        # to apply the rate structure to recompute the bill's charges for its
        # entire period. This is equivalent to relying on the bill instead of
        # OLTP, but recomputing it first. So we decided to to it the easy way
        # and just rely on the bill. We can make it better later if we want.
        # (This is also a lot faster and lets us generate the report in real
        # time instead of using cron.)

        reebill = self._load_reebill(account, sequence)
        ree_charges = float(reebill.ree_charges)
        days_in_month = dateutils.days_in_month(month.year, month.month,
                reebill.period_begin, reebill.period_end)
        period_length = (reebill.period_end - reebill.period_begin).days
        revenue_in_month = ree_charges * days_in_month / float(period_length)
        return revenue_in_month


    def _estimate_ree_charge(self, session, account, start, end):
        '''Returns an estimate of renewable energy charges for a reebill that
        would be issued for the given account with the period [start, end). The
        period must be after the end of the account's last issued reebill.'''
        # make sure (year, month) is not the approximate month of a real bill
        last_sequence = self.state_db.last_issued_sequence(session, account)
        last_reebill = self._load_reebill(account, last_sequence)
        if start > end:
            raise ValueError('Start %s must precede end %s' % (start, end))
        if last_sequence > 0 and end < last_reebill.period_end:
            raise ValueError(('Period [%s, %s) does not exceed last actual '
                    'billing period for account %s, which is [%s, %s)') %
                    (start, end, account, last_reebill.period_begin,
                    last_reebill.period_end))
        
        # get energy sold during the period [start, end)
        olap_id = self.olap_ids[account]
        energy_sold_btu = 0
        if start.month == end.month and start.day == 1 and end.day == len(Month(end)):
            # date range happens to be whole month: get monthly OLAP document
            monthly_sold_btu = self.monguru.get_data_for_month(olap_id,
                    start.year, start.month).energy_sold
            if monthly_sold_btu == None:
                # measure does not exist in olap doc
                # TODO OK to count this as 0?
                monthly_sold_btu = 0
            energy_sold_btu += monthly_sold_btu
        else:
            # not a whole month: use individual days
            for day in date_generator(start, end):
                daily_sold_btu = self.monguru.get_data_for_day(olap_id,
                        day).energy_sold
                if daily_sold_btu == None:
                    # measure does not exist in the olap doc
                    # TODO OK to count this as 0?
                    daily_sold_btu = 0
                energy_sold_btu += daily_sold_btu

        # subtract energy for hours marked by unbillable annotations
        install = self.splinter.get_install_obj_for(olap_id)
        unbillable_annos = [anno for anno in install.get_annotations() if
                anno._from >= date_to_datetime(start) and anno._to <=
                date_to_datetime(end) and anno.unbillable]
        for anno in unbillable_annos:
            annotation_btu = 0
            for hour in sky_handlers.cross_range(anno._from, anno._to):
                annotation_btu += self.monguru.get_data_for_hour(olap_id,
                        hour.date(), hour.hour).energy_sold
            if annotation_btu > 0:
                print '    subtracting %s BTU for annotation: %s to %s' % (
                        annotation_btu, anno._from, anno._to)
                energy_sold_btu -= annotation_btu

        # convert to therms
        energy_sold_therms = energy_sold_btu / 100000.

        # now we figure out how much that energy costs. if the utility bill(s)
        # for this reebill are present, we could get them with
        # state.guess_utilbills_and_end_date(), and then use their rate
        # structure(s) to calculate the cost. but currently there are never any
        # utility bills until a reebill has been created. so there will never
        # be rate structure to use unless there is actually a reebill.
        unit_price = self._get_average_rate(session, account, last_sequence)
        energy_price = unit_price * energy_sold_therms
        # NOTE the sequence reported below may not be the real origin of the
        # rate if last_reebill has no energy in it
        print 'estimating %s/%s from %s to %s: $%.3f/therm (from #%s) * %.3f therms = $%.2f' % (
                account, olap_id, start, end, unit_price,
                last_reebill.sequence, energy_sold_therms, energy_price)
        return energy_price


    def _load_reebill(self, account, sequence):
        '''Returns the reebill given by account, sequence, taken from cache if
        possible.'''
        # load from cache if present
        if (account, sequence) in self.reebill_cache:
            return self.reebill_cache[account, sequence]

        # otherwise load from mongo and save in cache
        reebill = self.reebill_dao.load_reebill(account, sequence)
        self.reebill_cache[account, sequence] = reebill
        return reebill

    def _get_average_rate(self, session, account, sequence, use_default=True):
        '''Returns the average per-therm energy price for the reebill (or
        hypothetical reebill period) given by account, sequence. If there's an
        issued reebill for the given sequence, that reebill itself is used to
        compute the rate. If there is no issued reebill for that sequence, the
        rate of the last issued reebill is used. If there are no issued
        reebills for the account at all, a default (global average) rate is
        used unless 'use_default' is False.'''
        # if the rate is cached, just get it
        if (account, sequence) in self.rate_cache:
            return self.rate_cache[account, sequence]

        # to compute the rate: get the last issued reebill
        last_sequence = self.state_db.last_issued_sequence(session, account)
        last_reebill = self._load_reebill(account, last_sequence)

        # if there's no cached rate for last_sequence, go back through the
        # sequences until a cached rate or a reebill with non-0 energy is found
        while last_sequence > 0 and (account, last_sequence) not in \
                self.rate_cache and last_reebill.total_renewable_energy(
                ccf_conversion_factor=Decimal("1.0")) == 0:
            last_sequence -= 1
            if last_sequence == 0:
                break
            last_reebill = self._load_reebill(account,
                    last_sequence)

        if (account, last_sequence) in self.rate_cache:
            rate = self.rate_cache[account, last_sequence]
        else:
            # no cached rates for this account at all: they must be computed
            if last_sequence == 0:
                # if the account has no reebills with non-zero renewable
                # energy, use the default rate
                if use_default:
                    rate = self._get_default_rate(session)
                else:
                    raise NoRateError(("%s has no reebills with non-zero "
                        "renewable energy."))
            else:
                # average price per therm of renewable energy is just renewable
                # energy charge (the price at which its energy was sold to the
                # customer, including the discount) / quantity of renewable energy
                # TODO: 28825375 - ccf conversion factor is as of yet unavailable so 1 is assumed.
                ree_charges = float(last_reebill.ree_charges)
                total_renewable_energy = float(last_reebill.total_renewable_energy(
                        ccf_conversion_factor=Decimal("1.0")))
                rate = ree_charges / total_renewable_energy

        # store rate in cache for this sequence and all others that lack a
        # reebill with non-0 energy
        for s in range(last_reebill.sequence, sequence + 1):
            self.rate_cache[account, s] = rate

        return rate

    def _get_default_rate(self, session):
        '''Returns the per-therm enery price used for estimating revenue for an
        account that has no reebills or none with any energy in them.'''
        # if default rate is already cached, return it
        if 'default' in self.rate_cache:
            return self.rate_cache['default']

        # compute average rate for every account and month in the report
        # (after this, all rates will be cached)
        total, count = 0, 0
        for month in months_of_past_year():
            for account in self.state_db.listAccounts(session):
                sequences = self.process.sequences_in_month(session,
                        account, month.year, month.month)
                for sequence in sequences:
                    # don't use default rates when computing the average, because
                    # this method is where default rates come from
                    try:
                        total += self._get_average_rate(session, account,
                                sequence, use_default=False)
                        count += 1
                    except NoRateError:
                        pass
        default_rate = total / float(count)
        
        # store default rate in cache
        self.rate_cache['default'] = default_rate

        return default_rate


if __name__ == '__main__':
    state_db = StateDB(
        host='localhost',
        database='skyline_dev',
        user='dev',
        password='dev'
    )
    reebill_dao = ReebillDAO({
        'host': 'localhost',
        'port': 27017,
        'database': 'skyline',
        'collection': 'reebills',
    })
    ratestructure_dao = RateStructureDAO({
        'host': 'localhost',
        'port': 27017,
        'database': 'skyline',
        'collection': 'ratestructure',
    })
    splinter = Splinter('http://duino-drop.appspot.com/', **{
        'skykit_host': args.host,
        'skykit_db': args.olapdb,
        'olap_cache_host': args.host,
        'olap_cache_db': args.olapdb,
        'monguru_options': {
            'olap_cache_host': args.host,
            'olap_cache_db': args.olapdb,
            'cartographer_options': {
                'olap_cache_host': args.host,
                'olap_cache_db': args.olapdb,
                'measure_collection': 'skymap',
                'install_collection': 'skyit_installs',
                'nexus_db': 'nexus',
                'nexus_collection': 'skyline',
            },
        },
        'cartographer_options': {
            'olap_cache_host': args.host,
            'olap_cache_db': args.olapdb,
            'measure_collection': 'skymap',
            'install_collection': 'skyit_installs',
            'nexus_db': 'nexus',
            'nexus_collection': 'skyline',
        },
    })

    session = state_db.session()
    er = EstimatedRevenue(state_db, reebill_dao, ratestructure_dao,
            splinter)

    data = er.report(session, failfast=True)
    #data = er.report(session)
    print table.csv

    data = deep_map(lambda x: dict(x) if type(x) == defaultdict else x, data)
    data = deep_map(lambda x: dict(x) if type(x) == defaultdict else x, data)
    pp(data)

    session.commit()

    # TODO test accuracy on historical bills here
