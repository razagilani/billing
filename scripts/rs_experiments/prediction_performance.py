from datetime import date, time, timedelta
from billing.processing.mongo import ReebillDAO
from billing.processing.state import StateDB
from billing.processing.rate_structure import RateStructureDAO
from billing.processing.session_contextmanager import DBSession
from sys import stderr
from pymongo import Connection

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

db = Connection('localhost')['skyline-dev']

with DBSession(state_db) as session:
    for account, sequence, max_version in state_db.reebills(session):
        reebill = bill_dao.load_reebill(account, sequence, version=max_version)
        service = reebill.services[0]
        utility_name = reebill.utility_name_for_service(service)
        rate_structure_name = reebill.rate_structure_name_for_service(service)

        try:
            #actual_rs = rs_dao._load_combined_rs_dict(reebill,
                    #service)
            actual_rs = rs_dao.load_uprs(account, sequence, max_version, utility_name, rate_structure_name)
        except ValueError as e:
            print >> stderr, account, sequence, max_version, 'missing CPRS'
        except Exception as e:
            print >> stderr, account, sequence, max_version, e
        else:
            # temporarily remove real UPRS from database
            db.ratestructure.remove({'_id.account': account, '_id.sequence':
                sequence, '_id.version': max_version})

            guessed_rs = rs_dao.get_probable_uprs(reebill, service)
            print guessed_rs['rates']

            actual_bindings = [rsi['binding'] for rsi in actual_rs['rates']]
            guessed_bindings = [rsi['binding'] for rsi in guessed_rs['rates']]

            if len(guessed_bindings) == 0:
                precision = float('inf')
            else:
                precision = len([b for b in guessed_bindings if b in
                        actual_bindings]) / len(guessed_bindings)
            if len(actual_bindings) == 0:
                recall = float('inf')
            else:
                recall = len([b for b in actual_bindings if b in
                        guessed_bindings]) / len(actual_bindings)

            print account, sequence, max_version, precision, recall

            # restore real UPRS to database
            db.ratestructure.remove({'_id.account': account, '_id.sequence':
                sequence, '_id.version': max_version})
