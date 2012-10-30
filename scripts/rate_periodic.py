from datetime import date, datetime, timedelta
from collections import defaultdict
from billing.util.dateutils import date_to_datetime, date_generator
from billing.mongo import float_to_decimal
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

TOLERANCE = 10

# build dict mapping RSIs to list of periods during which they occur
earliest, latest = date(3000,1,1), date(1000,1,1)
bindings = defaultdict(lambda: [])
with DBSession(state_db) as session:
    # TODO only use last issued version (lower ones contain errors)
    for acc, seq, ver in state_db.reebill_versions(session, include_unissued=False):
        reebill = bill_dao.load_reebill(acc, seq, version=ver)

        service = reebill.services[0] # assume only 1 service bc almost all bills have 1
        utility = reebill.utility_name_for_service(service)
        rs_name = reebill.rate_structure_name_for_service(service)
        if rs_name != 'DC Non Residential Non Heat':
            continue

        try:
            # load raw dictionary (RateStructure object is unusable)
            rs = rs_dao._load_probable_rs_dict(reebill, service)
        except:
            print acc, seq, ver, 'ERROR'
            pass
        else:
            #print acc, seq, ver
            period = reebill.meter_read_period(service)
            for binding, rate in [(r['rsi_binding'], r['rate']) for r in rs['rates']]:
                # only add rate if it's a number
                try:
                    rate = float(rate)
                except ValueError:
                    pass
                else:
                    bindings[binding].append((period, rate))
            earliest = min(earliest, period[0])
            latest = max(latest, period[1])

# write out data to files for plotting
for binding in bindings:
    with open('/tmp/rs_data/' + binding, 'w') as out_file:
        for period, rate in bindings[binding]:
            out_file.write('%s %s %s\n' % ( period[0], period[1], rate)),
exit()
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
        row[i+1] = [rate for period, rate in bindings[binding] if period_contains_day(period, day)][0]
        print row
        if i > 10:
            exit()
    table.append(row)

format = '%s ' + ('%8s' * (len(row)-1))
print [str(h) for h in table.headers]
print len(row), len(table.headers), format
#print format % table.headers
for row in table:
    print format % row
print bindings.keys()
