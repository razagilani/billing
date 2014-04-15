from sys import stderr
from itertools import chain
import pymongo
import mongoengine
import MySQLdb
from billing.processing.state import StateDB, Customer, ReeBill, ReeBillCharge
from billing.processing.rate_structure2 import RateStructureDAO, RateStructure
from billing.processing.mongo import ReebillDAO

con = MySQLdb.Connect(host='localhost', db='skyline_dev', user='dev',
                      passwd='dev')
cur = con.cursor()

# create new tables reebill_charge and address
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
cur.execute('''
create table if not exists address (
    id integer not null auto_increment primary key,
    addressee varchar(1000) not null,
    street varchar(1000) not null,
    city varchar(1000) not null,
    state varchar(1000) not null,
    postal_code varchar(1000) not null
);
''')
cur.execute('''alter table reebill add column billing_address_id
integer not null
''')
cur.execute('''alter table reebill add column service_address_id
integer not null
''')
con.commit()

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


for reebill in s.query(ReeBill).join(Customer)\
        .filter(ReeBill.customer_id==Customer.id)\
        .order_by(Customer.account, ReeBill.sequence).all():
    document = rbd.load_reebill(reebill.customer.account,
            reebill.sequence, version=reebill.version) # TODO what about multiple utility bills? should charges actually be
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

    try:
        charges = document.reebill_dict['utilbills'][0]['hypothetical_charges']
    except KeyError as e:
        print >> stderr, 'ERROR', reebill, e

    if not all(chain.from_iterable((key in c for key, _ in keys_defaults) for c in charges)):
        print >> stderr, 'WARNING %s-%s-%s: default values substituted for missing keys' % (reebill.customer.account, reebill.sequence, reebill.version)

    # copy charges to MySQL (using SQLAlchemy object ReeBillCharge
    # copy charges to MySQL (using SQLAlchemy object ReeBillCharge
    # corresponding to new table)
    reebill.charges = [ReeBillCharge(*[c.get(key, default) for (key, default) in keys_defaults]) for c in charges]

    # copy addresses to MySQL
    ba = document.reebill_dict['billing_address']
    sa = document.reebill_dict['service_address']
    # fix up some malformed data
    for a in (ba, sa):
        if 'ntry' in ba:
            a['postal_code'] = a['ntry']
            del a['ntry']
    reebill.billing_address = Address(**ba)
    reebill.service_address = Address(**sa)
    s.add(reebill.billing_address)
    s.add(reebill.service_address)

    # remove charges and address from Mongo
    del document.reebill_dict['utilbills'][0]['hypothetical_charges']
    del document.reebill_dict['billing_address']
    del document.reebill_dict['service_address']
    #rbd.reebill_dao.save_reebill(document)

con.commit()
s.commit()

cur.execute('''alter table reebill add constraint fk_billing_address_address
foreign key (billing_address_id) references address (id);
''')
cur.execute('''alter table reebill add constraint fk_service_address_address
foreign key (service_address_id) references address (id);
''')



