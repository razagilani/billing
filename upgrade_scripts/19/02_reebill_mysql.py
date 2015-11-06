import sys
import pymongo
import mongoengine
import MySQLdb
import argparse
from billing.processing.state import StateDB, UtilBill, Customer, ReeBill
from billing.processing.rate_structure import RateStructureDAO, RateStructure
from billing.processing.mongo import ReebillDAO


# command-line arguments
parser = argparse.ArgumentParser(description='02_reebill_mysql')
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
db = pymongo.Connection(host=args.billdbhost)[args.billdbname]
rbd = ReebillDAO(sdb, db)
rsd = RateStructureDAO()

s = sdb.session()

keys_to_remove = [
    'hypothetical_total',
    'actual_total',
]

keys_to_rename = {
    'late_charges': 'late_charge',
    'ree_charges': 'ree_charge',
    'bill_recipients': 'email_recipient',
}

other_keys = [
    'balance_due',
    'balance_forward',
    'discount_rate',
    'due_date',
    'late_charge_rate',
    'total_adjustment',
    'manual_adjustment',
    'payment_received',
    'prior_balance',
    'ree_value',
    'ree_savings',
]

# keys above for which null values should be allowed in corresponding MySQL
# column
null_allowed = ['issue_date', 'due_date', 'email_recipient']

con = MySQLdb.Connect(host=args.statedbhost, db=args.statedbname, user=args.statedbuser,
    passwd=args.statedbpasswd)
cur = con.cursor()
for key in other_keys + keys_to_rename.values():
    if key == 'due_date':
        sql = 'alter table reebill add column due_date date'
    elif key == 'email_recipient':
        sql = 'alter table reebill add column email_recipient varchar(1000)'
    else:
        sql = 'alter table reebill add column %s float' % key

    if key not in null_allowed:
        sql += ' not null'
    cur.execute(sql)
    print 'INFO executing:', sql

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
        if key == 'bill_recipients':
            recipients_list = doc.get('bill_recipients', [])
            reebill.recipients = ', '.join(recipients_list)
        else:
            set_key(key, new_name)

    for key in other_keys:
        set_key(key, key)

    #rbd.save_reebill_and_utilbill(doc)

s.commit()
