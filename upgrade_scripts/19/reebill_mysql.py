import sys
import pymongo
import mongoengine
import MySQLdb
from billing.processing.state import StateDB, UtilBill, Customer, ReeBill
from billing.processing.rate_structure2 import RateStructureDAO, RateStructure
from billing.processing.mongo import ReebillDAO

sdb = StateDB(**{
    'host': 'localhost',
    'database': 'skyline_dev',
    'user': 'dev',
    'password': 'dev'
})
db = pymongo.Connection(host='localhost')['skyline-dev']
rbd = ReebillDAO(sdb, db)
rsd = RateStructureDAO()

s = sdb.session()

keys_to_remove = [
    'hypothetical_total',
    'actual_total',
]

keys_to_rename = {
    'late_charges': 'late_charge',
    'ree_charges': 'ree_charge'
}

other_keys = [
    'balance_due',
    'balance_forward',
    'discount_rate',
    'due_date',
    'late_charge_rate',
    'manual_adjustment',
    'payment_received',
    'prior_balance',
    'ree_value',
    'ree_savings',
]

con = MySQLdb.Connect(host='localhost', db='skyline_dev', user='dev',
    passwd='dev')
cur = con.cursor()
for key in keys_to_remove + other_keys + keys_to_rename.values():
    if key == 'due_date':
        sql = 'alter table reebill add column due_date date'
    else:
        sql = 'alter table reebill add column %s float' % key
    cur.execute(sql)
    print 'INFO', sql

for reebill in s.query(ReeBill).join(Customer)\
        .filter(ReeBill.customer_id==Customer.id)\
        .order_by(Customer.account, ReeBill.sequence).all():
    doc = rbd.load_reebill(reebill.customer.account, reebill
            .sequence, version=reebill.version).reebill_dict

    for key in keys_to_remove:
        try:
            del doc[key]
        except KeyError as e:
            print 'WARNING', reebill, 'missing key to be removed:', e

    def set_key(old_name, new_name):
        try:
            value = doc[old_name]
        except KeyError as e:
            if old_name in ('late_charges', 'late_charge_rate'):
                value = 0
            else:
                print 'ERROR', reebill, 'missing key:', e
                return
        setattr(reebill, new_name, value)

    for key, new_name in keys_to_rename.iteritems():
        set_key(key, new_name)

    for key in other_keys:
        set_key(key, key)

    #rbd.save_reebill(doc)
