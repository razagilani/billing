import sys
import pymongo
import mongoengine
import MySQLdb
from billing.processing.state import StateDB, UtilBill, Customer
from billing.processing.mongo import ReebillDAO
from billing.processing.rate_structure2 import RateStructureDAO, RateStructure

sdb = StateDB(**{
    'host': 'localhost',
    'database': 'skyline_dev',
    'user': 'dev',
    'password': 'dev'
})
mongoengine.connect('skyline-dev',
        host='localhost',
        alias='ratestructure')
db = pymongo.Connection(host='localhost')['skyline-dev']
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
