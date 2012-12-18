from MySQLdb import Connection

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()

cur.execute('''select count(*), sum(max_version) from rebill''')
initial_count, new_rows = cur.fetchall()[0]
print '%s rows exist; %s new rows should be added' % (initial_count, new_rows)

# remove constraint that enforces uniqueness of {customer_id, sequence}
# (in "show index from rebill" this appears as 2 separate indices, one on customer_id and another on sequence)
cur.execute('''drop index unique_constraint on rebill;''')

# add another row to rebill for each version from 0 up to max_version
cur.execute('''select max_version, sequence, customer_id, issued from rebill''')
for row in cur.fetchall():
    print row
    for v in range(row[0]):
        statement = '''insert into rebill (max_version, sequence,
                customer_id, issued) values (%s, %s, %s, %s)'''
        print statement % ((v,) + row[1:])
        cur.execute(statement, (v,) + row[1:])

# make sure the right number of rows was added
cur.execute("select count(*) from rebill")
final_count = cur.fetchone()[0]
assert final_count == initial_count + new_rows

# replate old constraint with new one
cur.execute('''alter table rebill add unique index (customer_id, sequence, max_version)''')

# rename "max_version" to "version" and "rebill" to "reebill"
cur.execute('''alter table rebill change max_version version int(11)''')
cur.execute('''rename table rebill to reebill''')

con.commit()
