from datetime import date, datetime, timedelta
from billing.util.dateutils import date_to_datetime
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

with DBSession(state_db) as session:
    for acc, seq, ver in state_db.reebill_versions(session, include_unissued=False):
        reebill = bill_dao.load_reebill(acc, seq, version=ver)

        service = reebill.services[0] # assume only 1 service bc almost all bills have 1
        utility = reebill.utility_name_for_service(service)
        rs_name = reebill.rate_structure_name_for_service(service)

        try:
            predecessor = bill_dao.load_reebill(acc, seq - 1, version=0)
            process.compute_bill(session, predecessor, reebill)
        except:
            continue
        total = reebill.actual_total_for_service(service)

        # locate nearby utility bills
        start_min = date_to_datetime(reebill.period_begin - timedelta(days=TOLERANCE))
        start_max = date_to_datetime(reebill.period_begin + timedelta(days=TOLERANCE))
        end_min = date_to_datetime(reebill.period_end - timedelta(days=TOLERANCE))
        end_max = date_to_datetime(reebill.period_end + timedelta(days=TOLERANCE))
        neighbor_ubs = list(db.utilbills.find({
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
        if neighbor_ubs == []:
            continue

        # now get the rate structures of the neighboring utility bills; for
        # this we need the reebills
        neighbor_rate_structures = []
        for neighbor_ub in neighbor_ubs:
            neighbor_rb = bill_dao.load_reebill(neighbor_ub['account'],
                    neighbor_ub['sequence'], version=neighbor_ub['version'])
            try:
                rs = rs_dao.load_rate_structure(neighbor_rb, service)
            except Exception as e:
                #print acc, seq, ver, 'ERROR', e
                continue
            neighbor_rate_structures.append((neighbor_ub['account'], neighbor_ub['start'], neighbor_ub['end'], rs))
        print acc, seq, ver, utility, rs_name, 'neighbors:', len(neighbor_rate_structures)

        for ub_account, start, end, neighbor_rs in neighbor_rate_structures:
            print acc, ub_account
            try:
                neighbor_rs.bind_register_readings(reebill.actual_registers(service))
                actual_chargegroups = reebill.actual_chargegroups_for_service(service)
                for charges in actual_chargegroups.values():
                    neighbor_rs.bind_charges(charges)
                reebill.set_actual_chargegroups_for_service(service, actual_chargegroups)
            except (KeyError, NoSuchRSIError, ZeroDivisionError) as e:
                #print e
                continue

            try:
                from billing.util.dictutils import deep_map
                reebill.reebill_dict = deep_map(float_to_decimal, reebill.reebill_dict)
                reebill.actual_total = Decimal("0")
                actual_total = Decimal("0")
                for chargegroup, charges in reebill.actual_chargegroups_for_service(service).items():
                    actual_subtotal = Decimal("0")
                    for charge in charges:
                        actual_subtotal += Decimal(charge["total"])
                        actual_total += Decimal(charge["total"])
                reebill.set_actual_total_for_service(service, actual_total)
                print '**********', total, reebill.actual_total_for_service(service)
            except Exception as e:
                raise




# TODO instead of comparing totals, compare rate structure items
