import pymongo
import pprint
from billing.dictutils import dict_merge
import sys

pp = pprint.PrettyPrinter().pprint

con = pymongo.Connection('localhost', 27017)
reebills_col = con['skyline']['reebills']
utilbills_col = con['skyline']['utilbills']

def get_new_utilbills(reebill):
    utilbills = []
    for utilbill in reebill['utilbills']:
        new_utilbill = {
                '_id': {
                    'account': reebill['_id']['account'],
                    'service': utilbill['service'], # TODO maybe combine "service" (i.e. fuel type) and utility name?
                    'utility': utilbill['utility_name'],
                    'start': utilbill['period_begin'],
                    'end': utilbill['period_end'],
                },

                'chargegroups': utilbill['actual_chargegroups'],
                'total': utilbill['actual_chargegroups'], # NOTE key name has changed
                'rate_structure_binding': utilbill['rate_structure_binding'],
                'service_address': utilbill['serviceaddress'], # NOTE key name has changed
                'billing_address': utilbill['billingaddress'], # NOTE key name has changed

                # meters['registers'] should contain only the non-shadow meters of
                # the internal utilbill (overwrite the 'registers' list of the
                # original meters dict with a filtered version)
                'meters': [
                    dict_merge(meter, {
                        'registers': [r for r in meter['registers'] if not r['shadow']]
                    }, overwrite=True)
                for meter in utilbill['meters']],
        }
        utilbills.append(new_utilbill)
    return utilbills

for reebill in reebills_col.find():#{'_id.account':'10023', '_id.sequence':5}):
    try:
        new_utilbills = get_new_utilbills(reebill)
        for new_utilbill in new_utilbills:
            utilbills_col.save(new_utilbill)
    except Exception as e:
        print >> sys.stderr, reebill['_id']['account'], \
                reebill['_id']['sequence'], reebill['_id']['version'], 'ERROR:', e
    else:
        print reebill['_id']['account'], reebill['_id']['sequence'], \
                reebill['_id']['version']
