from datetime import date, datetime, timedelta
from collections import defaultdict
from billing.util.dateutils import date_to_datetime, date_generator
from billing.processing.mongo import float_to_decimal
from decimal import Decimal
import pymongo
from billing.processing.process import Process
from billing.processing.state import StateDB
from billing.processing.session_contextmanager import DBSession
from billing.processing.rate_structure import RateStructureDAO
from billing.processing.mongo import ReebillDAO
from billing.processing.exceptions import NoSuchRSIError

state_db = StateDB(
    host='localhost',
    database='skyline_dev',
    user='dev',
    password='dev'
)
bill_dao = ReebillDAO(state_db, database='skyline-dev')
rs_dao = RateStructureDAO(**{
    'database': 'skyline-dev',
    'collection': 'ratestructure',
    'host': 'localhost',
    'port': 27017
})
db = pymongo.Connection('localhost')['skyline-dev']
process = Process(state_db, bill_dao, rs_dao, None, None, None)

# build dict mapping RSIs to list of periods during which they occur
earliest, latest = date(3000,1,1), date(1000,1,1)
bindings = defaultdict(lambda: [])
with DBSession(state_db) as session:
    # TODO only use last issued version (lower ones contain errors)
    for acc, seq, ver in state_db.reebills(session, include_unissued=False):
        reebill = bill_dao.load_reebill(acc, seq)

        service = reebill.services[0] # assume only 1 service bc almost all bills have 1
        utility = reebill.utility_name_for_service(service)
        rs_name = reebill.rate_structure_name_for_service(service)
        if rs_name != 'DC Non Residential Non Heat':
            continue

        try:
            # load raw dictionary (RateStructure object is unusable)
            rs = rs_dao._load_combined_rs_dict(reebill, service)
            charges = reebill.actual_chargegroups_flattened(service)
        except Exception as e:
            print acc, seq, ver, 'ERROR:', e
        else:
            period = reebill.meter_read_period(service)
            for binding in [r['rsi_binding'] for r in rs['rates'] if r['rate'] != 0]:
                # exclude RSIs whose rate is 0 or ones that don't have a
                # corresponding charge, because that's often used instead of
                # removal
                if r['rate'] != 0 and any(c['rsi_binding'] == binding for c in charges):
                    bindings[binding].append(period)
            earliest = min(earliest, period[0])
            latest = max(latest, period[1])

def period_contains_day(period, day):
    return day >= period[0] and day < period[1]

from tablib import Dataset
keys = sorted(bindings.keys())
table = Dataset(headers=(['date'] + keys))
for day in date_generator(earliest, latest):
    row = [0] * (len(keys) + 1)
    row[0] = day
    for i, binding in enumerate(keys):
        # how many bills had a given rsi today?
        row[i+1] = sum(1 for period in bindings[binding] if period_contains_day(period, day))
    table.append(row)

format = '%10s ' + ('%11s' * (len(row)-1))
print format % tuple(h[:10] for h in table.headers)
print format % tuple(h[10:20] for h in table.headers)
print format % tuple(h[20:30] for h in table.headers)
print format % tuple(h[30:40] for h in table.headers)
for row in table:
    print format % row
