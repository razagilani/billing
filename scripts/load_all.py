#!/usr/bin/env python
'''Loads all reebills and their utility bills, prints errors and warnings if
bad or semi-bad conditions occur.'''
import pprint
from sys import stderr
from billing.processing.exceptions import NotUniqueException
from billing.processing.mongo import ReebillDAO
from billing.processing.state import StateDB
from billing.processing.session_contextmanager import DBSession
pp = pprint.PrettyPrinter().pprint

# config parameters:
host = 'localhost'
db = 'skyline-dev' # mongo
statedb = 'skyline_dev' # mysql
user = 'root'
password = 'root'

# data-access objects:
sdb = StateDB(**{
    'host': host,
    'database': statedb,
    'password': password,
    'user': user,
})
dao = ReebillDAO(sdb, **{
    'host': host,
    'database': db,
    'port': 27017,
})

warnings = []
missing_sequence_0 = []
errors = []

with DBSession(sdb) as session:

    # check that all utility bills can be loaded for each reebill
    for acc in sdb.listAccounts(session):
        #check that sequence 0 has a frozen utility bill
        seq = 0
        version = 0
        try:
            # load reebill (with frozen utility bills, if issued)
            reebill = dao.load_reebill(acc, seq, version)
            
            # load the un-frozen utility bills that are supposed to exist
            # when this is the newest version of the bill (if the reebill
            # is unissued, it will the same as the reebill above, but if
            # it's not issued, it will be separate)
            for u in reebill._utilbills:
                    
                # NOTE these keys don't HAVE to be unique, because the user
                # could create 2 utility bills with the same dates. this
                # was done for 10001-32-0/1 and 10001-33 (before 10001-33
                # was deleted), and 10003-24,25.
                try:
                    dao.load_utilbill(acc, u['service'], u['utility'],
                                      u['start'], u['end'], sequence=seq,
                                      version=version)
                except NotUniqueException as e:
                    warnings.append(e)
                except Exception as e:
                    errors.append(e)
        except Exception as e:
            missing_sequence_0.append(e)
        for seq in sdb.listSequences(session, acc):
            max_version = sdb.max_version(session, acc, seq)
            for version in range(max_version + 1):

                try:
                    # load reebill (with frozen utility bills, if issued)
                    reebill = dao.load_reebill(acc, seq, version)

                    # load the un-frozen utility bills that are supposed to exist
                    # when this is the newest version of the bill (if the reebill
                    # is unissued, it will the same as the reebill above, but if
                    # it's not issued, it will be separate)
                    if version == max_version:
                        for u in reebill._utilbills:

                            # NOTE these keys don't HAVE to be unique, because the user
                            # could create 2 utility bills with the same dates. this
                            # was done for 10001-32-0/1 and 10001-33 (before 10001-33
                            # was deleted), and 10003-24,25.
                            try:
                                dao.load_utilbill(acc, u['service'], u['utility'],
                                        u['start'], u['end'], sequence=False,
                                        version=False)
                            except NotUniqueException as e:
                                warnings.append(e)

                except Exception as e:
                    errors.append(e)

print "Warnings"
print "--------"
for e in warnings:
    print e
print
print "Errors"
print "------"
for e in errors:
    print e
print
print "Errors from missing sequence 0s"
print "-------------------------------"
for e in missing_sequence_0:
    print e
print
print "Checking reebill utilbill IDs"
print "------------------------"
import pymongo
db = pymongo.Connection(host, 27017)[db]
i = 0
for reebill in db.reebills.find().sort([('_id.account',pymongo.ASCENDING),('_id.sequence',pymongo.ASCENDING),('_id.version',pymongo.ASCENDING)]):
    for utilbill in reebill['utilbills']:
        i += 1
        utilbills = db.utilbills.find({'_id':utilbill['id']})
        if utilbills.count() > 1:
            print "For reebill:",reebill['_id']
            print "Multiple utility bills found with id:",utilbill['id']
            continue
        elif utilbills.count() < 1:
            print "Missing utility bill for reebill:",reebill['_id']
            continue
        ub = utilbills.next()

        has_error = False
        if not ub.has_key('account'):
            if not has_error:
                print "For reebill:",reebill['_id']
                has_error = True
            print "Utility bill missing account"
        elif ub['account'] != reebill['_id']['account']:
            if not has_error:
                print "For reebill:",reebill['_id']
                has_error = True
            print "Wrong account on utilbill:",ub['account']
        #if not ub.has_key('sequence'):
            #if not has_error:
                #print "For reebill:",reebill['_id']
                #has_error = True
            #print "Utility bill missing sequence"
        #elif ub['sequence'] != reebill['_id']['sequence']:
            #if not has_error:
                #print "For reebill:",reebill['_id']
                #has_error = True
            #print "Wrong sequence on utilbill:",ub['sequence']
        #if not ub.has_key('version'):
            #if not has_error:
                #print "For reebill:",reebill['_id']
                #has_error = True
            #print "Utility bill missing version"
        #elif ub['version'] != reebill['_id']['version']:
            #if not has_error:
                #print "For reebill:",reebill['_id']
                #has_error = True
            #print "Wrong version on utilbill:",ub['version']

print "Total number of utilbills checked:",i
