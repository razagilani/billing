'''Changes UPRS document ids to contain reebill sequence and version.'''
from sys import stderr
import pymongo

host = 'localhost'
database = 'skyline-dev'

db = pymongo.Connection(host, 27017)[database]

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
    uprs = db.ratestructure.find_one(uprs_query)
    if uprs is None:
        print >> stderr, "missing UPRS: %s" % uprs_query
        continue

    try:
        del uprs['_id']['effective']
        del uprs['_id']['expires']
    except KeyError:
        print >> stderr, "malformed UPRS id:", uprs['_id']
    uprs['_id']['account'] = reebill['_id']['account']
    uprs['_id']['sequence'] = reebill['_id']['sequence']
    uprs['_id']['version'] = reebill['_id']['version']

    db.ratestructure.remove({'_id': uprs['_id']})
    db.ratestructure.save(uprs)
    print 'upgraded', reebill['_id']
