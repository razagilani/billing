'''Copies "rates" (Rate Structure Items) from CPRS documents into UPRS
documents.'''
from sys import stderr
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

count = 0
for reebill in db.reebills.find():
    account = reebill['_id']['account']
    sequence = reebill['_id']['sequence']
    version = reebill['_id']['version']

    # get utility bill
    utilbill = db.utilbills.find_one({'_id': reebill['utilbills'][0]['id']})

    # get CPRS
    cprs_query = {
        '_id.type': 'CPRS',
        '_id.account': account, 
        '_id.sequence': sequence,
        '_id.version': version
    }
    cprs = db.ratestructure.find_one(cprs_query)

    # skip this reebill if the CPRS document is missing or has empty list of RSIs
    if cprs is None:
        print >> stderr, "missing CPRS: %s" % cprs_query
        continue
    if cprs['rates'] == []:
        print >> stderr, 'empty CPRS: %s' % cprs_query
        continue

    # get UPRS
    uprs_query = {
        '_id.type': 'UPRS',
        '_id.account': account,
        '_id.sequence': sequence,
        '_id.version': version
    }
    result = db.ratestructure.find(uprs_query)

    # skip this reebill if there's no UPRS
    if result.count() == 0:
        print >> stderr, '%s-%s-%s' % (account, sequence, version), "missing UPRS: %s" % uprs_query
        continue
    if result.count() > 1:
        import ipdb; ipdb.set_trace()
        continue
    uprs = result[0]

    # put CPRS rates into UPRS
    for cprs_rsi in cprs['rates']:
        found = False
        for uprs_rsi in uprs['rates']:
            if cprs_rsi['rsi_binding'] == uprs_rsi['rsi_binding']:
                found = True
                break
        if not found:
            uprs['rates'].append(cprs_rsi)
    assert uprs['rates'] != []

    # save UPRS
    db.ratestructure.save(uprs)
    print account, sequence, version, 'upgraded'
    count += 1

num_uprss = db.ratestructure.find({'_id.type':'UPRS'}).count()
print count, 'upgraded', num_uprss - count, 'remaining'
