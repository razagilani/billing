#!/usr/bin/python
'''Rename "date" column of payment table to "date_received", add column
"date_applied", initially with same value.'''
import MySQLdb

statedb_config = {
    'host': 'localhost',
    'password': 'dev',
    'database': 'skyline_dev',
    'user': 'dev'
}

conn = MySQLdb.connect(host='localhost', db=statedb_config['database'],
        user=statedb_config['user'], passwd=statedb_config['password'])
cursor = conn.cursor()

cursor.execute('alter table payment change date date_received datetime not null')
cursor.execute('alter table payment add date_applied date not null')

# TODO why does this work when typed into myql but have no effect when run from this script?
cursor.execute('update payment set date_applied = date_received')
conn.commit()
