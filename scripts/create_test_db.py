#!/usr/bin/env python
'''Create a test database with the same schema as the development
database, but empty. Any existing database of the same name is replaced.'''
from MySQLdb import Connection

USER, PASSWORD = 'root', 'root' # use root because only root or the "definer" can create a view
DEV_DB, TEST_DB = 'skyline_dev', 'test'

con = Connection('localhost', USER, PASSWORD)
cur = con.cursor()

# remove test database and re-create it, so it's guaranteed to exist and have
# no tables
cur.execute("drop database if exists %s" % TEST_DB)
cur.execute("create database %s" % TEST_DB)
cur.execute("use %s" % TEST_DB)

# get table/view names from dev db
cur.execute('''select table_name from information_schema.tables where
        table_schema = '%s' and table_type = "BASE TABLE"''' % DEV_DB);
dev_tables = [x[0] for x in cur.fetchall()]
cur.execute('''select table_name from information_schema.tables where
        table_schema = '%s' and table_type = "VIEW"''' % DEV_DB);
dev_views = [x[0] for x in cur.fetchall()]

# copy tables from dev db to test db
# (constraints and indices are only fully copied if the "create table" command
# is executed--"create table like" does do this.)
for table in dev_tables:
    cur.execute("show create table %s.%s" % (DEV_DB, table))
    create_command = cur.fetchone()[1]
    cur.execute(create_command)

# views can only be created when their parent tables already exist
for view in dev_views:
    cur.execute("show create table %s.%s" % (DEV_DB, view))
    create_command = cur.fetchone()[1]

    # the "create view" statement contains the original database name, so
    # replace it with the name of the test database. (NOTE this is a hack and
    # will probably fail when tables or columns have the same name as the db.)
    create_command = create_command.replace('`%s`' % DEV_DB, '`%s`' % TEST_DB)
    cur.execute(create_command)

con.commit()
