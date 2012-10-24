from datetime import date, datetime, timedelta
from billing.util.dateutils import date_to_datetime
import pymongo
from billing.processing.state import StateDB
from billing.processing.session_contextmanager import DBSession
from billing.processing.rate_structure import RateStructureDAO
from billing.processing.mongo import ReebillDAO

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

TOLERANCE = 5

with DBSession(state_db) as session:
    for acc, seq, ver in state_db.reebill_versions(session, include_unissued=False):
        reebill = bill_dao.load_reebill(acc, seq, version=ver)

        service = reebill.services[0] # assume only 1 service bc almost all bills have 1
        utility = reebill.utility_name_for_service(service)
        rs_name = reebill.rate_structure_name_for_service(service)

        # locate nearby utility bills
        start_min = date_to_datetime(reebill.period_begin - timedelta(days=TOLERANCE))
        start_max = date_to_datetime(reebill.period_begin + timedelta(days=TOLERANCE))
        end_min = date_to_datetime(reebill.period_end - timedelta(days=TOLERANCE))
        end_max = date_to_datetime(reebill.period_end + timedelta(days=TOLERANCE))
        neighbors = list(db.utilbills.find({
            # same utility & rate structure
            'utility': utility,
            'rate_structure_binding': rs_name,
            # different account
            'account': {'$ne': acc},
            # must be attached to a reebill (so we know it's correct)
            'sequence': {'$exists': True},
            'version': {'$exists': True},
            # period must be within TOLERANCE OF this bill's period
            'start': {'$gte': start_min, '$lte': start_max},
            'end': {'$gte': end_min, '$lte': end_max},
        }))

        try:
            rs_dao.load_rate_structure(reebill, service)
        except Exception as e:
            #print acc, seq, ver, 'ERROR', e
            pass
        else:
            print acc, seq, ver, utility, rs_name, 'neighbors:', len(neighbors)

            # 
