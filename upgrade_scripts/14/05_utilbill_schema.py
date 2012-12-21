import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
db = pymongo.Connection('localhost')['skyline-dev']

con.begin()
cur = con.cursor()

###############################################################################
# utilbill_version

cur.execute("create table utilbill_version like utilbill")

# convert promary key column utilbill_version.id into foreign key column "utilbill_id"
# TODO is there no way to add the foreign key constraint and remove the primary key constraint at the same time as the column is redefined, like other constraints?
cur.execute("alter table utilbill_version modify id int not null")
cur.execute("alter table utilbill_version drop primary key")
cur.execute("alter table utilbill_version change column id utilbill_id int(11) not null")
cur.execute("alter table utilbill_version add constraint foreign key (utilbill_id) references utilbill (id)")

# add id column for utilbill_version itself
cur.execute("alter table utilbill_version add column id int(11) not null auto_increment primary key")

# also add utility name column, since this isn't in mysql yet
cur.execute("alter table utilbill_version add column utility varchar(45) not null")

# fill utilbill_version with data from mongo (excluding customer_id, processed, state, date_received)
#cur.execute("insert into utilbill_version select (rebill_id, period_start, period_end, service, total_charges) from utilbill")
cur.execute("select customer.account, customer_id, rebill_id, period_start, period_end, service, total_charges from utilbill join customer where customer_id = customer.id order by customer.account, utilbill.period_start")
for account, customer_id, rebill_id, start, end, service, total_charges in cur.fetchall():
    mongo_docs = db.utilbill.find({'account': account, 'start': date_to_datetime(start), 'end': date_to_datetime(end), 'service': service})

    # create one row in utilbill_version for each mongo document, and put the row's id in the document
    for doc in mongo_docs:
        utility_name = doc['utility']
        cur.execute("insert into utilbill_version (customer_id, rebill_id, period_start, period_end, service, total_charges, utility) values (%s, %s, %s, %s, %s, %s, %s)",
                (rebill_id, start, end, service, total_charges, utility))
        doc['mysql_id'] = cur.lastrowid

# add constraint for uniqueness on {account, service, utility, start, end} (which we already enforce for mongo documents in rebillDAO)
cur.execute("alter table utilbill_version add constraint utilbill_version_unique unique (customer_id, service, utility, period_start, period_end)")

###############################################################################
# utilbill

cur.execute("alter table utilbill drop foreign key fk_utilbill_rebill")

# remove all data that have been moved to the utilbill_version table
cur.execute("alter table utilbill drop column rebill_id")
cur.execute("alter table utilbill drop column period_start")
cur.execute("alter table utilbill drop column period_end")
cur.execute("alter table utilbill drop column service")
cur.execute("alter table utilbill drop column total_charges")

con.commit()

