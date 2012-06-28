#!/usr/bin/python
import MySQLdb

statedb_config = {
    'host': 'localhost',
    'password': 'reebill-dev',
    'database': 'skyline_dev',
    'user': 'reebill-dev'
}

conn = MySQLdb.connect(host='localhost', db=statedb_config['database'],
        user=statedb_config['user'], passwd=statedb_config['password'])
cursor = conn.cursor()

# NOTE will fail if column is already present: script can only run once
cursor.execute('alter table rebill add max_version int not null default 0')
