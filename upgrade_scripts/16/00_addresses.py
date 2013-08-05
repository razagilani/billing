'''Replace utility bill "billing_address" and "service_address" fields with "billing_address" and "service_address" from reebill documents, using the same schema as in reebills.'''
from pymongo import Connection
from sys import stderr
from billing.processing.mongo import utilbill_billing_address_to_reebill_address, utilbill_service_address_to_reebill_address, reebill_address_to_utilbill_address
db = Connection('localhost')['skyline-dev']

for reebill in db.reebills.find():
    # convert address schema
    try:
        billing_address = reebill_address_to_utilbill_address(reebill['billing_address'])
        service_address = reebill_address_to_utilbill_address(reebill['service_address'])
    except KeyError:
        print >> stderr, 'bad address schema in', reebill['_id']
        print >> stderr, reebill['service_address']
        print >> stderr, reebill['billing_address']
        continue

    utilbill_ids = [u['id'] for u in reebill['utilbills']]
    utilbills = db.utilbills.find({'_id': {'$in': utilbill_ids}})

    if utilbills.count() != len(utilbill_ids):
        print >> stderr, 'utility bills not found:', reebill['_id']

    for utilbill in utilbills:
        # save in utility bill AND reebill
        utilbill['billing_address'] = billing_address
        utilbill['service_address'] = service_address
        reebill['billing_address'] = billing_address
        reebill['service_address'] = service_address
        db.utilbills.save(utilbill)
        db.reebills.save(reebill)
