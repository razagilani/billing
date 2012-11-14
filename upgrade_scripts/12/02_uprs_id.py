'''Changes UPRS document ids to contain reebill sequence and version.'''
from sys import stderr
from copy import deepcopy
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

count = 0
for reebill in db.reebills.find():
    # get utility bill
    utilbill = db.utilbills.find_one({'_id': reebill['utilbills'][0]['id']})

    # get CPRS
    cprs_query = {
        '_id.type': 'CPRS',
        '_id.account': reebill['_id']['account'],
        '_id.sequence': reebill['_id']['sequence'],
        '_id.version': reebill['_id']['version']
    }
    cprs = db.ratestructure.find_one(cprs_query)
    if cprs is None:
        print >> stderr, "missing CPRS: %s" % cprs_query
        continue

    # get UPRS
    uprs_query = {
        '_id.type': 'UPRS',
        '_id.utility_name': cprs['_id']['utility_name'],
        '_id.rate_structure_name': cprs['_id']['rate_structure_name'],
        '_id.effective': utilbill['start'],
        '_id.expires': utilbill['end'],
    }
    original_uprs = db.ratestructure.find_one(uprs_query)
    if original_uprs is None:
        print >> stderr, "missing UPRS: %s" % uprs_query
        continue
    new_uprs = deepcopy(original_uprs)

    # NOTE not deleting "effective" and "expires" because dates are needed to
    # find the distance of a UPRS from a new utility bill period; the utility
    # bill could be used, but this is more convenient.
    #try:
        #del new_uprs['_id']['effective']
        #del new_uprs['_id']['expires']
    #except KeyError:
        #print >> stderr, "malformed UPRS id:", new_uprs['_id']
    new_uprs['_id']['account'] = reebill['_id']['account']
    new_uprs['_id']['sequence'] = reebill['_id']['sequence']
    new_uprs['_id']['version'] = reebill['_id']['version']

    db.ratestructure.remove({'_id': new_uprs['_id']})
    db.ratestructure.save(new_uprs)
    db.ratestructure.remove(original_uprs)
    print 'upgraded', reebill['_id']
    count += 1

not_upgraded = db.ratestructure.find({'_id.type':'UPRS', '_id.effective':{'$exists': True}}).count()
print count, 'upgraded', not_upgraded, 'remaining'
