'''Prints out rate structure documents that have something wrong with them:
document is malformed, no reebill exists with the same account/sequence/version
as the RS document, utility bill associated with that reebill doesn't have the
same utility name and rate structure name as the RS document.'''
import pymongo
import MySQLdb

def one(iterator):
    result = next(iterator)
    try:
        next(iterator)
    except StopIteration:
        return result
    raise ValueError("more than one!")


db = pymongo.Connection('localhost')['skyline-dev']
print 'searching in', db

con = MySQLdb.Connection(host='localhost', db='skyline_dev', user='dev', passwd='dev')
cur = con.cursor()

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
        cur.execute('select id from customer where account = %s' % acc)
        customer_id = cur.fetchone()[0]
        num = cur.execute('select max_version from rebill where customer_id = %s and sequence = %s' % (customer_id, seq))
        rows = cur.fetchall()
        if num > 1:
            raise ValueError("didn't expect more than one reebill")
        if num == 0 or rows[0][0] < ver:
            # this reebill doesn't exist in MySQL, so it's not going to cause
            # problems in actually using ReeBill
            print 'Orphaned rate structure document:', rs['_id']
            continue
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
