from datetime import date, datetime
from collections import defaultdict
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from billing.processing.process import Process
from billing.dateutils import estimate_month, month_offset, months_of_past_year, date_generator
from billing.nexus_util import NexusUtil

class EstimatedRevenue(object):

    def __init__(self, state_db, rebill_dao, process, splinter, monguru):
        self.state_db = state_db
        self.reebill_dao = reebill_dao
        self.process = process
        self.splinter = splinter
        self.monguru = monguru

    def report(self, session):
        # dictionary account -> ((year, month) -> $) whose default value is an
        # empty dict whose default value is 0
        data = defaultdict(lambda: defaultdict(int))

        now = datetime.utcnow()
        for account in self.state_db.listAccounts(session):
            last_seq = self.state_db.last_sequence(session, account)
            for year, month in months_of_past_year(now.year, now.month):

                # get sequences of bills this month
                sequences = self.process.sequences_for_approximate_month(
                        session, account, year, month)

                # for each sequence, add that bill's real or estimated balance
                # due to the total for this month
                for seq in sequences:
                    if seq <= last_seq:
                        data[account][year, month] += self.reebill_dao\
                            .load_reebill(account, seq).balance_due
                    else:
                        data[account][year, month] += self._estimate_balance_due(
                                session, account, year, month)
        return data

    def _estimate_balance_due(self, session, account, year, month):
        '''Returns the best estimate of balance_due for a bill that would be
        issed for the given account in the given month. The month must exceed
        the approximate month of the account's last real bill.'''
        # make sure (year, month) is not the approximate month of a real bill
        last_sequence = self.state_db.last_sequence(session, account)
        last_reebill = self.reebill_dao.load_reebill(account, last_sequence)
        last_approx_month = estimate_month(last_reebill.period_begin,
                last_reebill.period_end)
        if (year, month) <= last_approx_month:
            raise ValueError(('%s does not exceed last approximate billing '
                'month for account %s, which is %s') % ((year, month), account,
                last_approximate_month))

        # the period over which to get energy sold is the entire calendar month
        # up to the present, unless this is the month following that of the
        # last real bill, in which case the period starts at the end of the
        # last bill's period (which may precede or follow the first day of this
        # month).
        if (year, month) == month_offset(*(last_approx_month + (1,))):
            start = last_reebill.period_end
        else:
            start = date(year, month, 1)
        month_end_year, month_end_month = month_offset(year, month, 1)
        end = min(date.today(), date(month_end_year, month_end_month, 1))
        
        # get energy sold during that period
        # TODO optimize by not repeatedly creating these objects
        olap_id = NexusUtil().olap_id(account)
        install = self.splinter.get_install_obj_for(olap_id)
        energy_sold = 0
        print 'geting energy_sold for %s from %s to %s' % (olap_id, start, end)
        for day in date_generator(start, end):
            try:
                daily_energy_sold = self.monguru.get_data_for_day(install,
                        day).energy_sold
                if daily_energy_sold == None:
                    # measure does not exist in the olap doc
                    daily_energy_sold = 0
            except ValueError:
                # olap doc is missing
                daily_energy_sold = 0
            energy_sold += daily_energy_sold

        # pretend energy costs $1/therm
        return energy_sold * 1/100000.

        # TODO
        # figure out how much that energy costs:
        ## if this reebill has utility bills, use the real utility rate to
        ## compute the price of the energy
        #state_db.guess_utilbills_and_end_date(account, max(start_date,
        ## TOD0
        #return 0


if __name__ == '__main__':
    from billing.processing.state import StateDB
    from billing.mongo import ReebillDAO
    state_db = StateDB({
        'host': 'localhost',
        'database': 'skyline_dev',
        'user': 'dev',
        'password': 'dev',
    })
    reebill_dao = ReebillDAO({
        'database': 'skyline',
        'collection': 'reebills',
        'host': 'localhost',
        'port': '27017'
    })
    splinter = Splinter('http://duino-drop.appspot.com/', 'tyrell', 'dev')
    monguru = Monguru('tyrell', 'dev')
    process = Process(None, state_db, reebill_dao, None, splinter, monguru)
    session = state_db.session()
    er = EstimatedRevenue(state_db, reebill_dao, process, splinter, monguru)
    data = er.report(session)
    all_months = sorted(set(reduce(lambda x,y: x+y, [data[account].keys() for account in data], [])))
    now = date.today()
    data_months = months_of_past_year(now.year, now.month)
    print '      '+('%10s '*12) % tuple(map(str, data_months))
    for account in sorted(data.keys()):
        print account + '%10.1f '*12 % tuple([data[account].get((year, month), 0) for (year, month) in data_months])
    session.commit()
