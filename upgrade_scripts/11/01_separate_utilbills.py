#!/usr/bin/env python
from copy import deepcopy
from datetime import datetime
import pprint
import sys
import operator
import traceback
import pymongo
from bson.objectid import ObjectId
from billing.dictutils import dict_merge, subdict
from billing.processing.state import StateDB
from billing.mongo import ReebillDAO
from billing.processing.session_contextmanager import DBSession
from billing.exceptions import NotUniqueException
pp = pprint.PrettyPrinter().pprint

# config:
host = 'localhost'
db = 'skyline-dev' # mongo
statedb = 'skyline_dev' # mysql
user = 'dev'
password = 'dev'

con = pymongo.Connection(host, 27017)
reebills_col = con[db]['reebills']
utilbills_col = con[db]['utilbills']

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

def get_utilbills(reebill, include_editable, include_frozen):
    '''Returns a list of (internal, external editable, external frozen) pairs
    for each utility bill subdocument of the reebill document.

    An editable utility bill document is included if include_editable is True.
    A frozen utility bill document is included iff include_frozen is True. '''
    result = []
    for utilbill in reebill['utilbills']:
        internal = {
            'hypothetical_chargegroups': utilbill['hypothetical_chargegroups'],
            'hypothetical_total': utilbill['hypothetical_total'],
            'ree_value': utilbill['ree_value'],
            'ree_charges': utilbill['ree_charges'],
            'ree_savings': utilbill['ree_savings'],

            # all shadow registers in a flat list, not in a meter
            'shadow_registers': reduce(operator.add,
                [[subdict(r, ['shadow'], invert=True) for r in
                        meter['registers'] if r['shadow']]
                for meter in utilbill['meters']]
            ),

            # NOTE "id" field will be added when saved
        }

        editable = {
            '_id': ObjectId(),

            # NOTE the key names that have changed
            'account': reebill['_id']['account'],
            'utility': utilbill['utility_name'],
            'service': utilbill['service'],
            'start': utilbill['period_begin'],
            'end': utilbill['period_end'],
            'chargegroups': utilbill['actual_chargegroups'],
            'total': utilbill['actual_total'],
            'rate_structure_binding': utilbill['rate_structure_binding'],
            'service_address': utilbill.get('serviceaddress', {}),
            'billing_address': utilbill.get('billingaddress', {}),

            # meters['registers'] should contain only the non-shadow meters
            # of the internal utilbill (overwrite the 'registers' list of
            # the original meters dict with a filtered version, and remove
            # the 'shadow' key)
            'meters': [
                dict_merge(meter, {
                    'registers': [subdict(r, ['shadow'], invert=True) for r
                            in meter['registers'] if not r['shadow']]
                }, overwrite=True)
            for meter in utilbill['meters']],
        }

        frozen = deepcopy(editable)
        frozen.update({
            '_id': ObjectId(),

            'sequence': reebill['_id']['sequence'],
            'version': reebill['_id']['version']
        })

        result.append((
            internal,
            editable if include_editable else None,
            frozen if include_frozen else None,
        ))
    return result

def safe_save(doc, collection):
    result = collection.save(doc, safe=True)

    err = collection.get_lasterror_options()
    if err != {}:
        raise ValueError(error)

    # utilbills should always get an oid
    if collection == utilbills_col:
        assert type(result) is ObjectId

    return result

with DBSession(sdb) as session:
    for acc in sdb.listAccounts(session):
        # get sequences from mysql AND mongo (just in case some bad code is
        # depending on reebill docs that are only in mongo)
        mysql_sequences = sdb.listSequences(session, acc)
        mongo_sequences = [b['_id']['sequence'] for b in reebills_col.find({'_id.account': acc})]
        for seq in range(min(mongo_sequences + mysql_sequences),
                max(mongo_sequences + mysql_sequences) + 1):
            # get max version from mongo: it's should always be >= the version
            # from mysql, usually == (NOTE sequence 0 never exists in in MySQL)
            mysql_max_version = 0 if seq == 0 else sdb.max_version(session, acc, seq)
            mongo_max_version = max(b['_id']['version'] for b in reebills_col.find({'_id.account': acc, '_id.sequence': seq}))
            assert mongo_max_version >= mysql_max_version
            max_version = mongo_max_version
            for version in range(max_version + 1):
                cursor = reebills_col.find({'_id.account': acc, '_id.sequence':seq, '_id.version': version})
                assert cursor.count() == 1
                reebill = cursor[0]
                
                issued = sdb.is_issued(session, acc, seq, version=version, nonexistent=False)

                try:
                    if version < max_version:
                        # case 1: less-than-maximum version must be issued;
                        # there's only a frozen document for each utility bill
                        all_utilbills = get_utilbills(reebill, False, True)
                        assert issued is True
                        for internal, editable, frozen in all_utilbills:
                            assert editable is None
                            safe_save(frozen, utilbills_col)
                            internal['id'] = frozen['_id']
                    elif version == max_version and issued:
                        # case 2: maximum version issued; there's a frozen
                        # document and an editable one
                        all_utilbills = get_utilbills(reebill, True, True)
                        assert type(reebill['issue_date']) is datetime
                        for internal, editable, frozen in all_utilbills:
                            safe_save(editable, utilbills_col)
                            safe_save(frozen, utilbills_col)
                            internal['id'] = frozen['_id']
                    elif version == max_version and not issued:
                        # case 3: max_version unissued: there's only an
                        # editable document
                        all_utilbills = get_utilbills(reebill, True, False)
                        for internal, editable, frozen in all_utilbills:
                            safe_save(editable, utilbills_col)
                            internal['id'] = editable['_id']
                    else:
                        raise ValueError("Should not be possible")

                    # set reebill's "utilbills" section to the list of internal
                    # utility bill documents (which have been modified by
                    # adding 'id' above)
                    reebill['utilbills'] = zip(*all_utilbills)[0]
                    safe_save(reebill, reebills_col)
                except Exception as e:
                    print >> sys.stderr, acc, seq, version, e, 'ERROR:', \
                            traceback.format_exc()
                else:
                    ## no news is good news
                    #pass
                    print "upgraded", reebill['_id']


    # check that all utility bills can be loaded for each reebill
    for acc in sdb.listAccounts(session):
        for seq in sdb.listSequences(session, acc):
            max_version = sdb.max_version(session, acc, seq)
            for version in range(max_version + 1):
                print "loading", acc, seq, version
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
                            print '******************** WARNING:', e
