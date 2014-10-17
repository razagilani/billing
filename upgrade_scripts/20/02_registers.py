'''Move data from "shadow_registers" subdocuments in Mongo to new "reading"
table in MySQL.
'''
from billing import init_model
init_model("mysql://root:root@localhost:3306/skyline_dev")


from sys import stderr
import pymongo
import MySQLdb
from billing.processing.state import StateDB, Customer, ReeBill, ReeBillCharge, Session
from billing.processing.rate_structure import RateStructureDAO, RateStructure
from billing.processing.mongo import ReebillDAO
from itertools import chain


sdb = StateDB(Session)

db = pymongo.Connection(host='localhost')['skyline-dev']
rbd = ReebillDAO(sdb, db)
rsd = RateStructureDAO()

s = sdb.session()

con = MySQLdb.Connect(host='localhost', db='skyline_dev', user='dev',
                      passwd='dev')
con.autocommit(False)
cur = con.cursor()

# create new table reebill_charge
cur.execute('''
create table if not exists reading (
    id integer not null auto_increment primary key,
    reebill_id integer not null,
    register_binding varchar(1000) not null,
    measure varchar(1000) not null,
    conventional_quantity float not null,
    renewable_quantity float not null,
    unit varchar(1000) not null,
    aggregate_function varchar(15) default 'SUM',
    foreign key (reebill_id) references reebill (id) on delete cascade
)''')

for reebill in s.query(ReeBill).join(Customer) \
        .filter(ReeBill.customer_id==Customer.id) \
        .order_by(Customer.account, ReeBill.sequence).all():
    document = rbd.load_reebill(reebill.customer.account,
                                reebill.sequence, version=reebill.version)
    # TODO what about multiple utility bills? should charges actually be
    # associated with utilbill_reebill instead of reebill?
    if len(document._utilbills) > 1:
        print >> stderr, 'ERROR skipped %s due to multiple utility bills' % reebill

    utilbill_doc = rbd.load_doc_for_utilbill(reebill.utilbills[0])
    all_registers = chain.from_iterable((r for r in m['registers'])
                                        for m in utilbill_doc['meters'])

    for sr in document.reebill_dict['utilbills'][0]['shadow_registers']:
        binding = sr.get('register_binding', None)
        try:
            the_register = next(r for r in all_registers
                    if r.get('register_binding', None) == binding)
        except StopIteration:
            print >> stderr, 'ERROR', reebill, 'No register matching ' \
                   '"%s"' % binding
            conventional_quantity = 0
            unit = ''
        else:
            conventional_quantity = the_register['quantity']
            unit = the_register['quantity_units']

        # for 10004, an account that has multiple meters that all measure
        # total energy, only the first meter should  be used.
        # see https://www.pivotaltracker.com/story/show/72656436
        if reebill.customer.account == '10004' and \
                sr['register_binding'] not in (None, 'REG_TOTAL'):
            print 'INFO %s-%s-%s skipped register %s' % (
                    reebill.customer.account, reebill.sequence, reebill.version,
                    sr['register_binding'])
            continue
        cur.execute('''insert into reading (reebill_id, register_binding,
                measure, conventional_quantity, renewable_quantity, unit)
                values (%s, '%s', '%s', %s, %s, '%s')''' % (
                reebill.id, sr['register_binding'], sr['measure'],
                conventional_quantity, sr['quantity'], unit))

con.commit()
