'''Prints out rate structure documents that have something wrong with them:
document is malformed, no reebill exists with the same account/sequence/version
as the RS document, utility bill associated with that reebill doesn't have the
same utility name and rate structure name as the RS document.'''
import pymongo

def one(iterator):
    result = next(iterator)
    try:
        next(iterator)
    except StopIteration:
        return result
    raise ValueError("more than one!")


db = pymongo.Connection('localhost')['skyline-dev']
print 'searching in', db

for rs in db.ratestructure.find({'_id.type': {'$ne': 'URS'}}):
    try:
        acc, seq, ver = rs['_id']['account'], rs['_id']['sequence'], rs['_id']['version']
        u_name, rs_name = rs['_id']['utility_name'], rs['_id']['rate_structure_name']
    except:
        print 'Malformed _id:', rs['_id']

    try:
        reebill = one(db.reebills.find({'_id.account': acc,
                '_id.sequence': seq, '_id.version': ver}))
    except StopIteration:
        print 'Missing reebill: %s-%s-%s' % (acc, seq, ver)

    success = False
    for handle in reebill['utilbills']:
        utilbill = db.utilbills.find_one({'_id': handle['id']})
        try:
            if utilbill['utility'] == u_name and \
                    utilbill['rate_structure_binding'] == rs_name:
                success = True
                break
        except KeyError as e:
            print utilbill, e
    if success == False:
        #print rs
        print "Non-matching utility bill: %s-%s-%s (%s/%s, %s/%s)" % (acc, seq, ver, u_name, rs_name, utilbill['utility'], utilbill['rate_structure_binding'])
