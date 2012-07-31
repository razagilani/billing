import pymongo
import pprint
from billing.dictutils import dict_merge, subdict
import sys
import operator
import traceback

pp = pprint.PrettyPrinter().pprint

con = pymongo.Connection('localhost', 27017)
reebills_col = con['skyline']['reebills']
utilbills_col = con['skyline']['utilbills']

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
            utilbills_col.save(ub)

        # replace utilbills list in reebill with list of internal ones
        reebill['utilbills'] = get_internal_utilbills(reebill)
        reebills_col.save(reebill)
    except KeyError as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], 'missing key:', e
    except Exception as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], 'ERROR:', traceback.format_exc()
    else:
        print reebill['_id']['account'], reebill['_id']['sequence'], \
                reebill['_id']['version']
