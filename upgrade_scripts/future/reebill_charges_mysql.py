from sys import stderr
from itertools import chain
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
create table if not exists reebill_charge (
    id integer not null auto_increment primary key,
    reebill_id integer not null,
    rsi_binding varchar(1000) not null,
    description varchar(1000) not null,
    group_name varchar(1000) not null,
    quantity float not null,
    rate float not null,
    total float not null,
    foreign key (reebill_id) references reebill (id) on delete cascade
)''')

for reebill in s.query(ReeBill).join(Customer)\
        .filter(ReeBill.customer_id==Customer.id)\
        .order_by(Customer.account, ReeBill.sequence).all():
    document = rbd.load_reebill(reebill.customer.account,
            reebill.sequence, version=reebill.version)
    # TODO what about multiple utility bills? should charges actually be
    # associated with utilbill_reebill instead of reebill?
    if len(document._utilbills) > 1:
        print >> stderr, 'ERROR skipped %s due to multiple utility bills' % reebill

    # charge subdocument key names to default values to be substituted when the keys are missing
    # order is argument
    keys_defaults = [
       ('rsi_binding','UNKNOWN'),
       ('description',''),
       ('group',''),
       ('quantity', 0),
       ('rate', 0),
       ('total', 0),
    ]

    #try:
    charges = document.reebill_dict['utilbills'][0]['hypothetical_charges']
    #except KeyError as e:
        #print >> stderr, 'ERROR', reebill, e

    if not all(chain.from_iterable((key in c for key, _ in keys_defaults) for c in charges)):
        print >> stderr, 'WARNING: %s-%s-%s: default values substituted for missing keys' % (reebill.customer.account, reebill.sequence, reebill.version)

    # copy charges to MySQL (using SQLAlchemy object ReeBillCharge
    # corresponding to new table)
    reebill.charges = [ReeBillCharge(*[c.get(key, default) for (key, default) in keys_defaults]) for c in charges]

    # remove charges fro Mongo
    del document.reebill_dict['utilbills'][0]['hypothetical_charges']
    #rbd.reebill_dao.save_reebill(document)

con.commit()
s.commit()


