'''Rename "rebill" to "reebill".'''
from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()

cur.execute('''rename table rebill to reebill''')
cur.execute('''alter table utilbill_version change column rebill_id reebill_id int(11)''')

