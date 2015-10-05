from sys import stderr
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

for reebill in db.reebills.find({'_id.sequence':0}):
    for utilbill in reebill['utilbills']:
        ub = db.utilbills.find_one({'_id':utilbill['id']})
        ub['sequence'] = 0
        ub['version'] = 0
        db.utilbills.save(ub)
