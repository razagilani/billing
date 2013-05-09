'''Rename "rebill" to "reebill".'''
from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()

cur.execute('''rename table rebill to reebill''')
cur.execute('''alter table utilbill_version change column rebill_id reebill_id int(11)''')

# delete "key indices" (i.e. those lines starting with "KEY" in the "show
# create table" output) remaining from when the utilbill_version table was the
# utilbill table, in preparation for adding new constraints below.
cur.execute("alter table utilbill_version drop key fk_utilbill_customer")
cur.execute("alter table utilbill_version drop key fk_utilbill_rebill")

# re-add constraints that were removed when utilbill_version was created (this has to come after renaming)
cur.execute("alter table utilbill_version add constraint fk_utilbill_version_customer foreign key (customer_id) references customer (id) on delete no action on update no action")
cur.execute("alter table utilbill_version add constraint fk_utilbill_version_reebill foreign key (reebill_id) references reebill (id) on delete no action on update no action")

con.commit()
