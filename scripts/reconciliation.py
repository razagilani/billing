#!/usr/bin/python
'''Script to generate a "reconciliation report" comparing energy quantities in
reebills to the same quantities in OLAP.

This should be run by cron to generate a static JSON file, which can be loaded
by BillToolBridge and returned for display in an Ext-JS grid in the browser.'''
import os
import traceback
import datetime
from billing import mongo
from billing.reebill import render
from billing.processing import state
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from billing.nexus_util import NexusUtil
from billing import json_util
from billing import dateutils

def close_enough(x,y):
    # TODO figure out what's really close enough
    x = float(x)
    y = float(y)
    if y == 0:
        return abs(x) < .001
    return abs(x - y) / y < .001

# setup
billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}
statedb_config = {
    'host': 'tyrell',
    'password': 'dev',
    'database': 'skyline_dev',
    'user': 'dev'
}
reebill_dao = mongo.ReebillDAO(billdb_config)
state_db = state.StateDB(statedb_config)
session = state_db.session()
splinter = Splinter('http://duino-drop.appspot.com/', "tyrell", 'dev')
monguru = Monguru('tyrell', 'dev')

# it's a bad idea to build a huge string in memory, but i need to avoid putting
# a comma after the last object in the array, and i can't un-write the comma if
# i'm writing to a file (and i can't know what the last item of the array is
# going to be in advance because i'm only including items that have an error or
# a difference from olap)
result = '['

accounts = sorted(state_db.listAccounts(session))
# TODO it would be faster to do this sorting in MySQL instead of Python when
# this list gets long
for account in accounts:
    install = splinter.get_install_obj_for(NexusUtil().olap_id(account))
    sequences = state_db.listSequences(session, account)
    for sequence in sequences:
        print 'reconciliation report for %s-%s' % (account, sequence)
        reebill = reebill_dao.load_reebill(account, sequence)
        try:
            # get energy from the bill
            bill_therms = reebill.total_renewable_energy
            
            # OLTP is more accurate but way too slow to generate this report in a reasonable time
            #oltp_therms = sum(install.get_energy_consumed_by_service(
                    #day, 'service type is ignored!', [0,23]) for day
                    #in dateutils.date_generator(reebill.period_begin,
                    #reebill.period_end))
            
            # now get energy from OLAP: start by adding up energy
            # sold for each day, whether billable or not (assuming
            # that periods of missing data from OLTP will have
            # contributed 0 to the OLAP aggregate)
            olap_btu = 0
            for day in dateutils.date_generator(reebill.period_begin,
                    reebill.period_end):
                olap_btu += monguru.get_data_for_day(install,
                        day).energy_sold

            # now find out how much energy was unbillable by
            # subtracting energy sold during all unbillable
            # annotations from the previous total
            for anno in [anno for anno in install.get_annotations() if
                    anno.unbillable]:
                # i think annotation datetimes are in whole hours
                # and their ends are exclusive
                for hour in sky_handlers.cross_range(anno._from, anno._to):
                    hourly_doc = monguru.get_data_for_hour(install, hour)
                    olap_btu -= hourly_doc.energy_sold
            olap_therms = olap_btu / 100000
        except Exception as error:
            result += json_util.dumps({
                'success': False,
                'account': account,
                'sequence': sequence,
                'timestamp': datetime.datetime.utcnow(),
                'error': '%s\n%s' % (error, traceback.format_exc())
            })
            result +=',\n'
        else:
            if close_enough(bill_therms, olap_therms):
                continue
            result += json_util.dumps({
                'success': True,
                'account': account,
                'sequence': sequence,
                'timestamp': datetime.datetime.utcnow(),
                'bill_therms': bill_therms,
                'olap_therms': olap_therms
            })
            result += ',\n'

result = result[:-2] # remove final ',\n'
result += ']'

# file where the report goes: json format
with open(os.path.join(os.path.dirname(os.path.realpath('billing')), 'reebill',
        'reconciliation_report.json'), 'w') as output_file:
    output_file.write(result)
