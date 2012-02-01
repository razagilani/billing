#!/usr/bin/python
'''Script to generate a "reconciliation report" comparing energy quantities in
reebills to the same quantities in OLAP.

This should be run by cron to generate a static JSON file, which can be loaded
by BillToolBridge and returned for display in an Ext-JS grid in the browser.'''
import os
import traceback
import datetime
import argparse
import logging
from billing import mongo
from billing.reebill import render
from billing.processing import state
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner import sky_handlers
from billing.nexus_util import NexusUtil
from billing import json_util
from billing import dateutils

OUTPUT_FILE_NAME = 'reconciliation_report.json'
LOG_FILE_NAME = 'reconciliation.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

def close_enough(x,y):
    # TODO figure out what's really close enough
    x = float(x)
    y = float(y)
    if y == 0:
        return abs(x) < .001
    return abs(x - y) / y < .001

def generate_report(billdb_config, statedb_config, splinter_config,
        monguru_config):
    '''Saves JSON data for reconciliation report in the file 'OUTPUT_FILE'.'''

    # logging setup
    logger = logging.getLogger('reconciliation_report')
    formatter = logging.Formatter(LOG_FORMAT)
    log_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
            LOG_FILE_NAME)
    handler = logging.FileHandler(log_file_path)
    handler.setFormatter(formatter)
    logger.addHandler(handler) 
    logger.setLevel(logging.DEBUG)

    # objects for database access
    reebill_dao = mongo.ReebillDAO(billdb_config)
    state_db = state.StateDB(statedb_config)
    session = state_db.session()
    splinter = Splinter(splinter_config['url'], splinter_config['host'],
            splinter_config['db'])
    monguru = Monguru(monguru_config['host'], monguru_config['db'])

    output_file_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), OUTPUT_FILE_NAME)
    logger.info('Generating reconciliation report at %s' % output_file_path)

    # it's a bad idea to build a huge string in memory, but i need to avoid putting
    # a comma after the last object in the array, and i can't un-write the comma if
    # i'm writing to a file (and i can't know what the last item of the array is
    # going to be in advance because i'm only including items that have an error or
    # a difference from olap)
    # TODO: fix this if it becomes a problem when the number of bills gets really
    # large
    result = '['

    # get account numbers of all customers in sorted order
    # TODO: it would be faster to do this sorting in MySQL instead of Python when
    # the list of accounts gets long
    accounts = sorted(state_db.listAccounts(session))
    for account in accounts:
        install = splinter.get_install_obj_for(NexusUtil().olap_id(account))
        sequences = state_db.listSequences(session, account)
        for sequence in sequences:
            reebill = reebill_dao.load_reebill(account, sequence)

            result_dict = {
                'account': account,
                'sequence': sequence,
                'timestamp': datetime.datetime.utcnow(),
            }
            try:
                # get energy from the bill
                bill_therms = reebill.total_renewable_energy
                result_dict.update({
                    'bill_therms': bill_therms
                })
                
                # OLTP is more accurate but way too slow to generate this report in
                # a reasonable time
                # TODO: maybe switch over to OLTP when it becomes faster (because
                # OLTP is more accurate and it's what we actually use to create
                # bills)
                #oltp_therms = sum(install.get_energy_consumed_by_service(
                        #day, 'service type is ignored!', [0,23]) for day
                        #in dateutils.date_generator(reebill.period_begin,
                        #reebill.period_end))
                
                # find the date to start getting data from OLAP: in some cases the
                # date when OLAP data begins is later than the beginning of the
                # first billing period. if we billed the customer for a period
                # containing during which we were unable to measure the energy some
                # of the time, the right thing to do would be to omit all energy
                # that we couldn't measure. if that's what we did, the energy on
                # the bill will be the same as the total metered energy starting
                # from the date when data is first available. (note that if date of
                # earliest data comes after the bill's end date, the bill's energy
                # better be 0 or our bill is very wrong.)
                start_date = max(reebill.period_begin, install.install_completed.date())
                
                # now get energy from OLAP: start by adding up energy
                # sold for each day, whether billable or not (assuming
                # that periods of missing data from OLTP will have
                # contributed 0 to the OLAP aggregate)
                olap_btu = 0
                for day in dateutils.date_generator(start_date, reebill.period_end):
                    olap_btu += monguru.get_data_for_day(install, day).energy_sold

                # now find out how much energy was unbillable by
                # subtracting energy sold during all unbillable
                # annotations from the previous total
                for anno in [anno for anno in install.get_annotations() if
                        anno.unbillable]:
                    # i think annotation datetimes are in whole hours
                    # and their ends are exclusive
                    for hour in sky_handlers.cross_range(anno._from, anno._to):
                        hourly_doc = monguru.get_data_for_hour(install, hour.date(), hour.hour)
                        olap_btu -= hourly_doc.energy_sold
                olap_therms = olap_btu / 100000
            except Exception as error:
                result_dict.update({
                    #'error': '%s\n%s' % (error, traceback.format_exc())
                    'error': str(error)
                })
                logger.error('%s-%s: %s\n%s' % (account, sequence, error, traceback.format_exc()))
                result += json_util.dumps(result_dict) + ',\n'
            else:
                if close_enough(bill_therms, olap_therms):
                    logger.info('%s-%s is OK' % (account, sequence))
                else:
                    result_dict.update({
                        'olap_therms': olap_therms
                    })
                    result += json_util.dumps(result_dict) + ',\n'
                    logger.warning('%s-%s differs from OLAP' % (account, sequence))

    result = result[:-2] # remove final ',\n'
    result += ']'

    # write the json string to a file
    with open(os.path.join(os.path.dirname(os.path.realpath('billing')), 'reebill',
            output_file_path), 'w') as output_file:
        output_file.write(result)

def main():
    # command-line arguments
    parser = argparse.ArgumentParser(description='Generate reconciliation report.')
    parser.add_argument('--host',  default='localhost',
            help='host for all databases (default: localhost)')
    parser.add_argument('--statedb', default='skyline_dev',
            help='name of state database (default: skyline_dev)')
    parser.add_argument('--stateuser', default='dev',
            help='username for state database (default: dev)')
    parser.add_argument('--statepw', default='dev',
            help='name of state database (default: dev)')
    parser.add_argument('--billdb', default='skyline_dev',
            help='name of bill database (default: skyline_dev)')
    parser.add_argument('--olapdb',  default='dev',
            help='name of OLAP database (default: dev)')
    args = parser.parse_args()

    # setup
    billdb_config = {
        'database': args.billdb,
        'collection': 'reebills',
        'host': args.host,
        'port': '27017'
    }
    statedb_config = {
        'host': args.host,
        'password': args.statepw,
        'database': args.statedb,
        'user': 'dev'
    }
    splinter_config = {
        'url': 'http://duino-drop.appspot.com/',
        'host': args.host,
        'db': args.olapdb
    }
    monguru_config = {
        'host': args.host,
        'db': args.olapdb
    }

    generate_report(billdb_config, statedb_config, splinter_config,
            monguru_config)

if __name__ == '__main__':
    main()
