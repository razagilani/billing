import MySQLdb
import pymongo
from billing.util.dateutils import date_to_datetime
import pprint
pp = pprint.PrettyPrinter().pprint

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

# convert promary key column utilbill_version.id into foreign key column
# "utilbill_id"
# TODO is there no way to add the foreign key constraint and remove the primary
# key constraint at the same time as the column is redefined, like other
# constraints?
cur.execute("alter table utilbill_version modify id int not null")
cur.execute("alter table utilbill_version drop primary key")
cur.execute("alter table utilbill_version change column id utilbill_id int(11) not null")
cur.execute('''alter table utilbill_version add constraint foreign key
        (utilbill_id) references utilbill (id)''')

# add id column for utilbill_version itself
cur.execute("alter table utilbill_version add column id int(11) not null auto_increment primary key")

# also add utility name column, since this isn't in mysql yet
cur.execute("alter table utilbill_version add column utility varchar(45) not null")

# fill utilbill_version with data from utilbill (excluding customer_id, processed), creating one row for each mongo document
cur.execute('''select utilbill.id, customer.account, customer_id, rebill_id, period_start, period_end, service, total_charges, state, date_received from utilbill join customer where customer_id = customer.id order by customer.account, utilbill.period_start''')
for utilbill_id, account, customer_id, rebill_id, start, end, service, total_charges, state, date_received in cur.fetchall():
    # load all mongo documents corresponding to this utilbill row, except if
    # they have sequence 0 (which means they're just templates)
    query = {
        'account': account,
        'start': date_to_datetime(start),
        'end': date_to_datetime(end),
        'service': service,
        'sequence': {'$ne':0}
    }
    mongo_docs = db.utilbills.find(query)

    # a utilbill that is not attached to a reebill should not have any mongo
    # documents. but if it is attached, not finding any mongo documents is an
    # error (e.g. the dates in mongo disagree with mysql).
    if mongo_docs.count() == 0 and rebill_id != None:
        print "could not find utility bill document (id %s): %s" % (utilbill_id, query)

    # for each mongo document, create one utilbill_version row, with the
    # utilbill row's id as its utilbill_id, and put the utilbill_version row id
    # in the mongo document
    for doc in mongo_docs:
        try:
            # get the "rebill_id" value for the new utilbill_version row:
            if 'sequence' in doc:
                # if this mongo utility bill is attached to a rebill, get the
                # mysql id of the reebill row in the (now expanded) rebill
                # table.
                cur.execute('''select rebill.id from rebill join customer where
                rebill.customer_id = customer.id and customer.account = %s
                and rebill.sequence = %s and rebill.version = %s''',
                (doc['account'], doc['sequence'], doc['version']))
                if cur.rowcount != 1:
                    print ("Mongo utilbill's reebill does not exist in MySQL:"
                            " %s-%s-%s") % (doc['account'], doc['sequence'],
                            doc['version'])
                    #import ipdb; ipdb.set_trace()
                    rebill_id = None
                    continue
                rebill_id = cur.fetchone()[0]
            else:
                # if the mongo utilbill does not have "sequence" in it, it does
                # not technically belong to any reebill, even if the utilbill
                # row in the former utilbill table had a non-null rebill_id
                rebill_id = None

            cur.execute('''insert into utilbill_version (customer_id, rebill_id,
                    utilbill_id, period_start, period_end, service,
                    total_charges, utility, state, date_received) values (%s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s)''', (customer_id, rebill_id, utilbill_id, start, end,
                    service, total_charges, doc['utility'], state, date_received))
        except MySQLdb.IntegrityError as e:
            print e
            import ipdb; ipdb.set_trace()
        if doc is not None:
            doc['mysql_id'] = cur.lastrowid
            db.utilbills.save(doc)

    # TODO each utilbill_version should get the id of the row for the reebill
    # it belongs to in the now expanded rebill table

# add constraint for uniqueness on {account, service, utility, start, end}
# (which we already enforce for mongo documents in rebillDAO)
#cur.execute("alter table utilbill_version add constraint utilbill_version_unique unique (customer_id, service, utility, period_start, period_end)")
# TODO temporarily disabled because the data do not actually allow it

###############################################################################
# utilbill

cur.execute("alter table utilbill drop foreign key fk_utilbill_rebill")

# remove all data that have been moved to the utilbill_version table
cur.execute("alter table utilbill drop column rebill_id")
cur.execute("alter table utilbill drop column period_start")
cur.execute("alter table utilbill drop column period_end")
cur.execute("alter table utilbill drop column service")
cur.execute("alter table utilbill drop column total_charges")
cur.execute("alter table utilbill drop column state")
cur.execute("alter table utilbill drop column date_received")
cur.execute("alter table utilbill drop column processed") # completely removed because meaningless

con.commit()


total = db.utilbills.count()
total_nonzero = db.utilbills.find({'sequence': {'$ne': 0}}).count()
print db.utilbills.find({'mysql_id': {'$exists': True}}).count(), 'of', total_nonzero, 'non-sequence-0 documents have mysql_id; total', total
