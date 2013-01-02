import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime

con = MySQLdb.Connection('localhost', 'dev', 'dev', 'skyline_dev')
db = pymongo.Connection('localhost')['skyline-dev']

# TODO why does the whole transaction get committed if the script is interrupted before commit() at the end?
# (transaction isolation level in MySQL shell is "repeatable read" (the default))
# select @@session.tx_isolation
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

# fill utilbill_version with data from utilbill (excluding customer_id, processed, state, date_received), creating one row for each mongo document
#cur.execute("insert into utilbill_version select (rebill_id, period_start, period_end, service, total_charges) from utilbill")
cur.execute("select utilbill.id, customer.account, customer_id, rebill_id, period_start, period_end, service, total_charges from utilbill join customer where customer_id = customer.id order by customer.account, utilbill.period_start")
for utilbill_id, account, customer_id, rebill_id, start, end, service, total_charges in cur.fetchall():
    query = {'account': account, 'start': date_to_datetime(start), 'end': date_to_datetime(end), 'service': service}
    mongo_docs = db.utilbills.find(query)
    if mongo_docs.count() < 1:
        # problem utility bills: use None as a placeholder for nonexistent mongo doc, so 1 row gets saved in utilbill_version
        if account == '10001':#utilbill_id in (4, 5, 7, 8, 9, 10):
            mongo_docs = [None]
        else:
            raise Exception("could not find utility bill document (id %s): %s" % (utilbill_id, query))

    # create one row in utilbill_version for each mongo document, and put the row's id in the document
    for doc in mongo_docs:
        if doc is not None:
            utility_name = doc['utility']
        else:
            utility_name = ''
        try:
            cur.execute("insert into utilbill_version (customer_id, rebill_id, utilbill_id, period_start, period_end, service, total_charges, utility) values (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (customer_id, rebill_id, utilbill_id, start, end, service, total_charges, utility_name))
        except MySQLdb.IntegrityError as e:
            print e
            import ipdb; ipdb.set_trace()
        if doc is not None:
            doc['mysql_id'] = cur.lastrowid
            db.utilbills.save(doc)

    # TODO each utilbill_version should get the id of the row for the reebill it belongs to in the now expanded reebill table

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

