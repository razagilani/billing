import sys
import pymongo
import mongoengine
import MySQLdb
from billing.processing.state import StateDB, Customer, ReeBill, ReeBillCharge
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

con = MySQLdb.Connect(host='localhost', db='skyline_dev', user='dev',
    passwd='dev')
cur = con.cursor()

# create new table reebill_charge
cur.execute('''
create table reebill_charge (
    id integer not null auto_increment primary key,
    reebill_id integer foreign key references reebill (id),
    rsi_binding varchar(1000) not null,
    description varchar(1000) not null,
    group,
    quantity float not null,
    rate float not null,
    total float not null,
)''')

for reebill in s.query(ReeBill).join(Customer)\
        .filter(ReeBill.customer_id==Customer.id)\
        .order_by(Customer.account, ReeBill.sequence).all():
    document = self.reebill_dao.load_reebill(reebill.customer.account,
            reebill.sequence, version=reebill.version)
    # TODO what about multiple utility bills? should charges actually be
    # associated with utilbill_reebill instead of reebill?

    # copy charges to MySQL (using SQLAlchemy object ReeBillCharge
    # corresponding to new table)
    reebill.charges = [ReeBillCharge(c['rsi_binding'], c['description'], c['group'],
            c['quantity'], c['rate'], c['total'])
            for c in document['hypothetical_charges']]

    # remove charges fro Mongo
    del document['hypothetical_charges']
    self.reebill_dao.save_reebill(document)

cur.commit()
s.commit()


