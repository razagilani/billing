#!/usr/bin/env python
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

#host = 'localhost'
#db = 'skyline-stage' # mongo
#statedb = 'skyline_stage' # mysql
#user = 'stage'
#password = 'stage'


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
                'service': utilbill['service'], # TODO maybe combine "service" (i.e. fuel type) and utility name?
                'start': utilbill['period_begin'],
                'end': utilbill['period_end'],
            },

            'chargegroups': utilbill['actual_chargegroups'],
            'total': utilbill['actual_total'], # NOTE key name has changed
            'rate_structure_binding': utilbill['rate_structure_binding'],
            'service_address': utilbill['serviceaddress'], # NOTE key name has changed
            'billing_address': utilbill['billingaddress'], # NOTE key name has changed

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
        utilbills.append(new_utilbill)

        # issued reebills also have frozen copy of each utility bill with a
        # "sequence" and "version" in it
        if 'issue_date' in reebill:
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
    try:
        # create external utilbills
        for ub in get_external_utilbills(reebill):
            ## add MongoEngine type fields
            #ub['_cls'] = 'UtilBill'
            #ub['_types'] = ['UtilBill']

            utilbills_col.save(ub)

        # replace utilbills list in reebill with list of internal ones
        reebill['utilbills'] = get_internal_utilbills(reebill)
        reebills_col.save(reebill)
    except KeyError as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], \
                'missing key:', e
        reebills_col.remove(reebill)
    except Exception as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], \
                'ERROR:', traceback.format_exc()
        reebills_col.remove(reebill)
    else:
        print reebill['_id']['account'], reebill['_id']['sequence'], \
                reebill['_id']['version']


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
            for version in range(sdb.max_version(session, acc, seq)):
                try:
                    dao.load_reebill(acc, seq)
                except:
                    #import ipdb; ipdb.set_trace()
                    dao.load_reebill(acc, seq)
