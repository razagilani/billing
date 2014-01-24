'''Removes the account and sequence fields from mongo reebills, they are stored in _id'''
from sys import stderr
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

count = 0
for reebill in db.reebills.find():
    #delete account
    if (reebill.has_key('account')):
        del reebill['account']
    else:
        print >> stderr, "Reebill %s-%s-%s had no reebill.account" %(reebill['_id']['account'],reebill['_id']['sequence'],reebill['_id']['version'])
    #delete seqence
    if (reebill.has_key('sequence')):
        del reebill['sequence']
    else:
        print >> stderr, "Reebill %s-%s-%s had no reebill.sequence" %(reebill['_id']['account'],reebill['_id']['sequence'],reebill['_id']['version'])
        
    db.reebills.save(reebill)
