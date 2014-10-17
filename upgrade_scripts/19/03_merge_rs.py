import sys
import pymongo
import mongoengine
import MySQLdb
import argparse
from billing.processing.state import StateDB, UtilBill, Customer
from billing.processing.mongo import ReebillDAO
from billing.processing.rate_structure import RateStructureDAO, RateStructure

# command-line arguments
parser = argparse.ArgumentParser(description='03_merge_rs')
parser.add_argument('--statedbhost', required=True)
parser.add_argument('--statedbname', required=True)
parser.add_argument('--statedbuser', required=True)
parser.add_argument('--statedbpasswd', required=True)

parser.add_argument('--billdbhost', required=True)
parser.add_argument('--billdbname', required=True)

args = parser.parse_args()

sdb = StateDB(**{
    'host': args.statedbhost,
    'database': args.statedbname,
    'user': args.statedbuser,
    'password': args.statedbpasswd
})
mongoengine.connect(args.billdbname,
        host=args.billdbhost,
        alias='ratestructure')
db = pymongo.Connection(host=args.billdbhost)[args.billdbname]
rbd = ReebillDAO(sdb, db)
rsd = RateStructureDAO()

s = sdb.session()

query = s.query(UtilBill).join(Customer).filter(UtilBill.customer_id ==
        Customer.id).order_by(Customer.account)

for utilbill in query.all():
    # print utilbill.customer.account, utilbill
    try:
        uprs = rsd.load_uprs_for_utilbill(utilbill)
        cprs = rsd.load_cprs_for_utilbill(utilbill)
    except Exception as e:
        print >> sys.stderr, 'ERROR', utilbill, e.__class__.__name__, e
        continue

    for rsi in uprs.rates:
        assert rsi.shared == True
    for rsi in cprs.rates:
        rsi.shared = False

    try:
        combined_rs = RateStructure.combine(uprs, cprs)
    except Exception as e:
        print >> sys.stderr, 'ERROR', utilbill, e.__class__.__name__, e
        continue

    uprs.rates = combined_rs.rates
    uprs.save()
