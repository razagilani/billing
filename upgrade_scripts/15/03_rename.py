'''Rename "rebill" to "reebill".'''
from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()

cur.execute('''rename table rebill to reebill''')
cur.execute('''alter table utilbill_version change column rebill_id reebill_id int(11)''')

# re-add constraints that were removed when utilbill_version was created (this has to come after renaming)
cur.execute("alter table utilbill_version add constraint fk_utilbill_version_customer foreign key (customer_id) references customer (id)")
cur.execute("alter table utilbill_version add constraint fk_utilbill_version_utilbill foreign key (utilbill_id) references utilbill (id)")
cur.execute("alter table utilbill_version add constraint fk_utilbill_version_reebill foreign key (reebill_id) references reebill (id)")
