'''
In the ReeBill 16 database, some utility bills (accounts 10008, 100011) have
state 3 ("Hypothetical") but have reebills attached to them. I am not sure why
this was done but they probably should be considered "Skyline Estimated" (state
2). This allows us to enforce the rule that utility bills have document ids iff
only if they are "real" (i.e. state < 3).
'''
from MySQLdb import Connection
from bson import ObjectId
from billing.util.mongo_utils import check_error

con = Connection('localhost', 'dev', 'dev', 'skyline_dev')
cur = con.cursor()

result = cur.execute('''update utilbill
set state = 2 where state = 3 and rebill_id is not null
''')

# 15 rows should have been updated
assert result == 15

con.commit()
