'''Changes UPRS document ids to contain reebill sequence and version.'''
from sys import stderr
from copy import deepcopy
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

uprs_ids_to_remove = []

count = 0
for reebill in db.reebills.find():
    # get utility bill
    utilbill = db.utilbills.find_one({'_id': reebill['utilbills'][0]['id']})

    # skip this reebill if utilbill periods are not filled in
    # (note that null as value in a mongo query always matches)
    if utilbill['start'] is None or utilbill['end'] is None:
        continue

    ## get CPRS
    #cprs_query = {
        #'_id.type': 'CPRS',
        #'_id.account': reebill['_id']['account'],
        #'_id.sequence': reebill['_id']['sequence'],
        #'_id.version': reebill['_id']['version']
    #}
    #cprs = db.ratestructure.find_one(cprs_query)
    #if cprs is None:
        ##print >> stderr, "missing CPRS: %s" % cprs_query
        #continue

    # get UPRS
    uprs_query = {
        '_id.type': 'UPRS',
        '_id.utility_name': utilbill['utility'],
        '_id.rate_structure_name': utilbill['rate_structure_binding'],
        '_id.effective': utilbill['start'],
        '_id.expires': utilbill['end'],
        '_id.account': {'$exists': False},
    }
    original_uprs = db.ratestructure.find_one(uprs_query)
    if original_uprs is None:
        #print >> stderr, "missing UPRS: %s" % uprs_query
        continue
    new_uprs = deepcopy(original_uprs)

    # NOTE not deleting "effective" and "expires" because dates are needed to
    # find the distance of a UPRS from a new utility bill period; the utility
    # bill could be used, but this is more convenient.
    try:
        del new_uprs['_id']['effective']
        del new_uprs['_id']['expires']
    except keyerror:
        print >> stderr, "malformed uprs id:", new_uprs['_id']
    new_uprs['_id']['account'] = reebill['_id']['account']
    new_uprs['_id']['sequence'] = reebill['_id']['sequence']
    new_uprs['_id']['version'] = reebill['_id']['version']
    assert 'effective' not in new_uprs['_id']
    assert 'expires' not in new_uprs['_id']

    uprs_ids_to_remove.append(original_uprs['_id'])
    db.ratestructure.save(new_uprs)
    print 'upgraded', reebill['_id']
    count += 1

for id in uprs_ids_to_remove:
    db.ratestructure.remove({'_id': id})

not_upgraded = db.ratestructure.find({'_id.type':'UPRS', '_id.account':{'$exists': False}}).count()
print count, 'upgraded', not_upgraded, 'remaining'
