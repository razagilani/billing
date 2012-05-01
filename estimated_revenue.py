import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from calendar import Calendar
from collections import defaultdict
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from billing.processing.process import Process
from billing.dateutils import estimate_month, month_offset, months_of_past_year, date_generator
from billing.nexus_util import NexusUtil
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state
from billing.processing.state import StateDB
from billing.mongo import ReebillDAO
from billing.dictutils import deep_map
from billing import dateutils
from billing.monthmath import Month, months_of_past_year

import pprint
pp = pprint.PrettyPrinter(indent=4).pprint
sys.stdout = sys.stderr

calendar = Calendar()

class EstimatedRevenue(object):

    def __init__(self, state_db, reebill_dao, ratestructure_dao, splinter):
        self.state_db = state_db
        self.reebill_dao = reebill_dao
        self.splinter = splinter
        self.monguru = splinter.get_monguru()
        self.ratestructure_dao = ratestructure_dao
        self.process = Process(None, self.state_db, self.reebill_dao, None,
                self.splinter, self.monguru)

        # pre-load all the olap ids of accounts for speed (each one requires an
        # HTTP request)
        nexus_util = NexusUtil()
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

    def report(self, session):
        '''Returns a dictionary containing data about real and renewable energy
        charges in reebills for all accounts in the past year. Keys are (year,
        month) tuples. Each value is a dictionary whose key is an account (or
        'total') and whose value is a dictionary containing real or estimated
        renewable energy charge in all reebills whose approximate calendar
        month was or probably will be that month, and a boolean representing
        whether that value was estimated.

        If there was an error, an Exception is put in the dictionary with the
        key "error", and "value" and "estimated" keys are omitted.
        The monthly total only includes accounts for which there wasn't an
        error.

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

        # dictionary account -> ((year, month) -> { monthtly data })
        # by default, value is 0 and it's not estimated
        data = defaultdict(lambda: defaultdict(lambda:
                {'value':0., 'estimated': False}))
        # TODO replace (year, month) tuples with Months

        # accounts = self.state_db.listAccounts(session)
        accounts = ['10006'] # enable all accounts when this is faster
        now = datetime.utcnow()
        for account in accounts:
            last_issued_sequence = self.state_db.last_sequence(session,
                    account)
            last_reebill_end = self.reebill_dao.load_reebill(
                    account, last_issued_sequence).period_end

            for month in months_of_past_year(now.year, now.month):
                try:
                    print account, month
                    #if account == '10006' and month == (2011,6):
                        #import pdb; pdb.set_trace()

                    # get all issued bills that have any part of their periods
                    # inside this month--possibly including a hypothetical bill
                    # whose period would be in this month if it existed. (note
                    # that un-issued bills effectively don't exist for this
                    # purpose, since they may have 0 energy in them).
                    try:
                        sequences = self.process.sequences_in_month(
                                session, account, month.year, month.month)
                    except ValueError:
                        import pdb; pdb.set_trace()

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
                                    account, seq, month.year, month.month)
                        else:
                            # not an issued bill: period starts at start of
                            # month or end of last issued bill period,
                            # whichever comes later, and ends at end of month
                            this_month_energy_for_sequence = self.\
                                    _estimate_ree_charge(session, account,
                                    max(month.first, last_reebill_end),
                                    month.last)
                            # a single estimated bill makes the whole month's
                            # revenue estimated
                            data[account][month.year, month.month]['estimated'] = True

                        data[account][month.year, month.month]['value'] += this_month_energy_for_sequence
                except Exception as e:
                    raise
                    data[account][month.year, month.month] = {'error': e}
                    print '%s %s-%s ERROR: %s' % (account, month.year, month.month, e)

        # compute total
        for month in months_of_past_year(now.year, now.month):
            # add up revenue for all accounts in this month
            data['total'][month.year, month.month]['value'] = sum(data[acc][month.year, month.month].get('value', 0)
                    for acc in accounts if not isinstance(data[acc]
                    [month.year, month.month], Exception))

            # total value is estimated iff any estimated bills contributed to
            # it (errors are treated as non-estimated zeroes). this will almost
            # certainly be true because utility bills for the present month
            # have not even been received.
            data['total'][month.year, month.month]['estimated'] = any(data[acc][month.year,
                month.month].get('estimated',False) == True for acc in accounts)

        return data


    def _quantize_revenue_in_month(self, session, account, sequence, year,
            month):
        '''Returns the approximate amount of energy from the reebill given by
        account and sequence during the given month, assuming the energy was
        evenly distributed over time.'''

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

        reebill = self.reebill_dao.load_reebill(account, sequence)
        ree_charges = float(reebill.ree_charges)
        days_in_month = dateutils.days_in_month(year, month,
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
        last_reebill = self.reebill_dao.load_reebill(account, last_sequence)
        if start > end:
            raise ValueError('Start %s must precede end %s' % (start, end))
        if end < last_reebill.period_end:
            raise ValueError(('Period [%s, %s) does not exceed last actual '
                    'billing period for account %s, which is [%s, %s)') %
                    (start, end, account, last_reebill.period_begin,
                    last_reebill.period_end))
        
        # get energy sold during the period [start, end)
        olap_id = self.olap_ids[account]
        energy_sold_btu = 0
        for day in date_generator(start, end):
            try:
                daily_sold_btu = self.monguru.get_data_for_day(olap_id,
                        day).energy_sold
                if daily_sold_btu == None:
                    # measure does not exist in the olap doc
                    daily_sold_btu = 0
            except ValueError:
                # olap doc is missing
                daily_sold_btu = 0
            energy_sold_btu += daily_sold_btu
        energy_sold_therms = energy_sold_btu / 100000.

        # now we figure out how much that energy costs. if the utility bill(s)
        # for this reebill are present, we could get them with
        # state.guess_utilbills_and_end_date(), and then use their rate
        # structure(s) to calculate the cost. but currently there are never any
        # utility bills until a reebill has been created. so there will never
        # be rate structure to use unless there is actually a reebill.

        # if last_reebill has zero renewable energy, replace it with the newest
        # bill that has non-zero renewable energy, if there is one
        while last_reebill.total_renewable_energy(
                ccf_conversion_factor=Decimal("1.0")) == 0:
            if last_reebill.sequence == 0:
                raise Exception(('No reebills with non-zero renewable '
                        'energy.') % account)
            last_reebill = self.reebill_dao.load_reebill(account,
                    last_reebill.sequence - 1)

        # to approximate the price per therm of renewable energy in the last
        # bill, we can just divide its renewable energy charge (the price at
        # which its energy was sold to the customer, including the discount) by
        # the quantity of renewable energy
        try:
            # TODO: 28825375 - ccf conversion factor is as of yet unavailable so 1 is assumed.
            ree_charges = float(last_reebill.ree_charges)
            total_renewable_energy = float(last_reebill.total_renewable_energy(
                    ccf_conversion_factor=Decimal("1.0")))
            unit_price = ree_charges / total_renewable_energy
            energy_price = unit_price * energy_sold_therms
            print '%s/%s %s to %s: $%.2f/therm (from #%s) * %.3f therms = $%.2f' % (
                    account, olap_id, start, end, unit_price,
                    last_reebill.sequence, energy_sold_therms, energy_price)
        except Exception as e:
            raise
        
        return energy_price


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
    splinter = Splinter('http://duino-drop.appspot.com/', 'tyrell', 'dev')
    session = state_db.session()
    er = EstimatedRevenue(state_db, reebill_dao, ratestructure_dao,
            splinter)

    data = er.report(session)

    ## print a table
    #all_months = sorted(set(reduce(lambda x,y: x+y, [data[account].keys() for
        #account in data], [])))
    #now = date.today()
    #data_months = months_of_past_year(now.year, now.month)
    #print '      '+('%10s '*12) % tuple(map(str, data_months))
    #for account in sorted(data.keys()):
        #print account + '%10.1f '*12 % tuple([data[account].get((year, month),
                #0) for (year, month) in data_months])
    #print 'total' + '%10.1f '*12 % tuple([sum(float(data[account].get((year, month),
            #0)) for account in data) for (year, month) in data_months])

    data = deep_map(lambda x: dict(x) if type(x) == defaultdict else x, data)
    data = deep_map(lambda x: dict(x) if type(x) == defaultdict else x, data)
    pp(data)

    session.commit()
