from billing import init_model
init_model("mysql://root:root@localhost:3306/skyline_dev")

from sys import stderr
from itertools import chain
import pymongo
import mongoengine
import MySQLdb
from billing.processing.state import StateDB, Customer, ReeBill, ReeBillCharge, Address
from billing.processing.rate_structure import RateStructureDAO, RateStructure
from billing.processing.mongo import ReebillDAO
from billing.processing.state import Session

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
    a_quantity float not null,
    h_quantity float not null,
    quantity_unit varchar(1000) not null,
    rate float not null,
    h_rate float not null,
    a_total float not null,
    h_total float not null,
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

sdb = StateDB(Session)

db = pymongo.Connection(host='localhost')['skyline-dev']
rbd = ReebillDAO(sdb, db)
rsd = RateStructureDAO()

s = sdb.session()

for reebill in s.query(ReeBill).join(Customer)\
        .filter(ReeBill.customer_id==Customer.id)\
        .order_by(Customer.account, ReeBill.sequence).all():
    document = rbd.load_reebill(reebill.customer.account,
            reebill.sequence, version=reebill.version) # TODO what about multiple utility bills? should charges actually be
    utilbill_doc = rbd._load_utilbill_by_id(
            document.reebill_dict['utilbills'][0]['id'])
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
        h_charges = document.reebill_dict['utilbills'][0]['hypothetical_charges']
    except KeyError as e:
        print >> stderr, 'ERROR', reebill, e

    if not all(chain.from_iterable((key in c for key, _ in keys_defaults) for c in h_charges)):
        print >> stderr, 'WARNING %s-%s-%s: default values substituted for missing keys' % (reebill.customer.account, reebill.sequence, reebill.version)

    # copy charges to MySQL (using SQLAlchemy object ReeBillCharge
    # corresponding to new table)
    reebill.charges = [ReeBillCharge(reebill,
        ac.get('rsi_binding', 'UNKNOWN'),
        ac.get('description', ''),
        ac.get('group', ''),
        ac.get('quantity', 0), hc.get('quantity', 0),
        # substitute '' for None in quantity_unit field
        ac.get('quantity_units', '') or '',
        ac.get('rate', 0), hc.get('rate', 0),
        ac.get('total', 0), hc.get('total', 0),
    ) for ac, hc in zip(utilbill_doc['charges'], h_charges)]

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

    # NOTE: no need to remove the data from Mongo since it will just be unused

con.commit()
s.commit()

cur.execute('''alter table reebill add constraint fk_billing_address_address
foreign key (billing_address_id) references address (id);
''')
cur.execute('''alter table reebill add constraint fk_service_address_address
foreign key (service_address_id) references address (id);
''')

# to check:
# select sum(c) from (select count(*) as c from reebill_charge where h_quantity - a_quantity < 0 group by reebill_id order by reebill_id) as t;


