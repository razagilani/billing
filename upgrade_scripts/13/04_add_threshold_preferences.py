import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

db.users.update({}, {'$set': {'preferences.difference_threshold': .01}}, multi = True)

error = db.error()

if error is not None:
    stderr.write('Database error . %s' % str(error))
else:
    print 'Difference Threshold Preferences inserted successfully.'
