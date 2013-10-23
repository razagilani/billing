import pymongo
import bson
from datetime import date,datetime

host = 'localhost'
db = 'skyline-dev' # mongo

mongodb = pymongo.Connection(host, 27017)[db]

count = 0

for utilbill in mongodb.utilbills.find().sort([('start',pymongo.ASCENDING)]):
    if not utilbill.has_key('account') or not utilbill.has_key('sequence'):
        continue
    if utilbill['sequence'] == 0:
        continue
    start = utilbill['start']
    end = utilbill['end']
    for meter in utilbill['meters']:
        present = meter['present_read_date']
        prior = meter['prior_read_date']
        if start != prior or end != present:
            print str(utilbill['_id'])+':'
            print '    account: ',utilbill['account']
            print '    sequence:',utilbill['sequence']
            if meter.has_key('identifier'):
                print '    meter id:',meter['identifier']
            print
            print '    utilbill start:   ',start
            print '    prior read date:  ',prior
            print '    utilbill end:     ',end
            print '    present read date:',present
            print
            print
            count += 1

print count
