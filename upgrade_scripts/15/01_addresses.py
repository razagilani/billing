'''Replace utility bill "billingaddress" and "serviceaddress" fields with "billing_address" and "service_address" from reebill documents, using the same schema as in reebills.'''
from pymongo import Connection
from sys import stderr
db = Connection('localhost')['skyline-dev']

for reebill in db.reebills.find():
    utilbill_ids = [u['id'] for u in reebill['utilbills']]
    utilbills = db.utilbills.find({'_id': {'$in': utilbill_ids}})

    if utilbills.count() != len(utilbill_ids):
        print >> stderr, 'utility bills not found:', reebill['_id']

    for utilbill in utilbills:
        # reebill schema is OK
        utilbill['billing_address'] = reebill['billing_address']
        utilbill['service_address'] = reebill['billing_address']
        try:
            del utilbill['billingaddress']
        except KeyError:
            print >> stderr, 'utility bill has no billingaddress:', reebill['_id']
        else:
            print 'ok', rebill['_id']
        try:
            del utilbill['serviceaddress']
        except KeyError:
            print >> stderr, 'utility bill has no serviceaddress:', reebill['_id']
        else:
            print 'ok', rebill['_id']
        
        #db.utilbills.save(utilbill)
