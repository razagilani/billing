'''Adds manual adjustment key with value 0 to all reebill documents to ensure data integrity.'''

from sys import stderr
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

# Set manual_adjustment = 0 on all reebills
db.reebills.update({}, {"$set": {"manual_adjustment": 0.0}}, multi=True)

error = db.error()

if error is not None:
    stderr.write('Database error. %s' % str(error))
else:
    print 'Manual adjustment keys inserted successfully.'

