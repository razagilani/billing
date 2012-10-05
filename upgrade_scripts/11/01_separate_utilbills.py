#!/usr/bin/env python
from datetime import datetime
import pymongo
import pprint
from billing.dictutils import dict_merge, subdict
import sys
import operator
import traceback
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

def get_external_utilbills(reebill):
    utilbills = []
    for utilbill in reebill['utilbills']:
        new_utilbill = {
            '_id': {
                'account': reebill['_id']['account'],
                'utility': utilbill['utility_name'],
                'service': utilbill['service'],
                'start': utilbill['period_begin'],
                'end': utilbill['period_end'],
            },

            # NOTE the key names that have changed
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

        # issued reebills also have frozen copy of each utility bill with a
        # "sequence" and "version" in it
        if reebill['issue_date'] is not None:
            new_utilbill['_id'].update({
                'sequence': reebill['_id']['sequence'],
                'version': reebill['_id']['version']
            })
        utilbills.append(new_utilbill)

    return utilbills

def get_internal_utilbills(reebill):
    utilbills = []
    for utilbill in reebill['utilbills']:
        new_utilbill = {
            'utility': utilbill['utility_name'],
            'service': utilbill['service'],
            'start': utilbill['period_begin'],
            'end': utilbill['period_end'],

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
        }

        utilbills.append(new_utilbill)
    return utilbills

for reebill in reebills_col.find():#{'_id.account':'10023', '_id.sequence':5}):
    # data fixes; TODO remove
    if reebill['_id']['account'] == '10001' \
            and reebill['_id']['sequence'] == 25 \
            and reebill['_id']['version'] == 0:
        reebill['issue_date'] = datetime(2012,5,24)
        print '************** fixed 10001-25-0'
    if reebill['_id']['account'] == '10017' \
            and reebill['_id']['sequence'] == 2 \
            and reebill['_id']['version'] == 0:
        # this may not be the right fix, but unlike making the bill issued, it
        # can be done in Mongo
        reebill['issue_date'] = None
        print '************** fixed 10017-2-0'
    if reebill['_id']['account'] == '10025' \
            and reebill['_id']['sequence'] == 1 \
            and reebill['_id']['version'] == 0:
        # this may not be the right fix, but unlike making the bill issued, it
        # can be done in Mongo
        reebill['issue_date'] = datetime(2012,5,22)
        print '************** fixed 10025-1-0'

    try:
        # create external utilbills
        for ub in get_external_utilbills(reebill):
            utilbills_col.save(ub, safe=True)
            if utilbills_col.get_lasterror_options() != {}:
                raise ValueError(utilbills_col.get_lasterror_options())

        # replace utilbills list in reebill with list of internal ones
        reebill['utilbills'] = get_internal_utilbills(reebill)
        reebills_col.save(reebill, safe=True)
        if reebills_col.get_lasterror_options() != {}:
            raise ValueError
    except KeyError as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], \
                'missing key:', e
    except Exception as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], \
                'ERROR:', traceback.format_exc()
    else:
        ## no news is good news
        #pass
        print "upgraded", reebill['_id']


# check that all utility bills can be loaded for each reebill
from billing.processing.state import StateDB
from billing.mongo import ReebillDAO
from billing.session_contextmanager import DBSession
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
with DBSession(sdb) as session:
    for acc in sdb.listAccounts(session):
        for seq in sdb.listSequences(session, acc):
            for version in range(sdb.max_version(session, acc, seq) + 1):
                try:
                    print "loading", acc, seq, version
                    dao.load_reebill(acc, seq, version)
                except:
                    import ipdb; ipdb.set_trace()
                    dao.load_reebill(acc, seq, version)
