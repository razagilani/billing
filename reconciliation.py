#!/usr/bin/python
'''Script to generate a "reconciliation report" comparing energy quantities in
reebills to the same quantities in OLAP.

This should be run by cron to generate a static JSON file, which can be loaded
by BillToolBridge and returned for display in an Ext-JS grid in the browser.

With our current configuration, the command to run it is:
python/var/local/reebill-prod/lib/python2.6/site-packages/billing/reconciliation.py --statedb skyline_prod --stateuser prod --statepw AXUPU4XGMSN --billdb skyline-prod
'''
import os
import sys
import errno
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
    # TODO 25207215 figure out what's really close enough
    x = float(x)
    y = float(y)
    if y == 0:
        return abs(x) < .001
    return abs(x - y) / y < .001

def generate_report(logger, billdb_config, statedb_config, splinter_config,
        monguru_config):
    '''Saves JSON data for reconciliation report in the file 'OUTPUT_FILE'.'''
    # objects for database access
    reebill_dao = mongo.ReebillDAO(billdb_config)
    state_db = state.StateDB(statedb_config)
    session = state_db.session()
    splinter = Splinter(splinter_config['url'], splinter_config['host'],
            splinter_config['db'])
    monguru = Monguru(monguru_config['host'], monguru_config['db'])

    # save output in billing/reebill
    output_file_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), '..', 'reebill', OUTPUT_FILE_NAME)
    logger.info('Generating reconciliation report at %s' % output_file_path)

    # it's a bad idea to build a huge string in memory, but i need to avoid putting
    # a comma after the last object in the array, and i can't un-write the comma if
    # i'm writing to a file (and i can't know what the last item of the array is
    # going to be in advance because i'm only including items that have an error or
    # a difference from olap)
    # TODO 25207303: fix this if it becomes a problem when the number of bills gets
    # really large. if the file is not being written all at once, it should be
    # written in a separate location while it's incomplete and then moved to
    # replace the existing file when it's done, so BillToolBridge never tries
    # to load an incomplete file.
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

            bill_error, oltp_error, olap_error = None, None, None

            try:
                # get energy from the bill
                bill_therms = reebill.total_renewable_energy
                result_dict.update({ 'bill_therms': bill_therms })

                # find the date to start getting data from OLAP: in some cases
                # the date when OLAP data begins is later than the beginning of
                # the first billing period, but in general it should be earlier
                # (because data collection starts during the sales process, and
                # after the installation is done, there's a delay before we
                # declare it billable). if we billed the customer for a period
                # during which we were unable to measure the energy some of the
                # time, the right thing to do would be to omit all energy that
                # we couldn't measure. if that's what we did, the energy on the
                # bill will be the same as the total metered energy starting
                # from the date of first billable data. (note that if date of
                # earliest data comes after the bill's end date, the bill's
                # energy better be 0 or our bill is very wrong.)
                start_date = max(reebill.period_begin,
                        install.install_commissioned.date())
                
            except Exception as e:
                bill_error = e
                logger.error('%s-%s: %s\n%s' % (account, sequence, e, traceback.format_exc()))
                
            # get energy from OLTP (very slow but more accurate and less
            # error-prone than OLAP)
            try:
                oltp_btu = sum(install.get_billable_energy(day, [0,23]) for
                        day in dateutils.date_generator(start_date,
                        reebill.period_end))
                oltp_therms = oltp_btu / 100000
                
            except Exception as e:
                oltp_error = e
                logger.error('%s-%s: %s\n%s' % (account, sequence, e, traceback.format_exc()))

            # get energy from OLAP: add up energy sold for each day, whether
            # billable or not (assuming that periods of missing data from OLTP
            # will have contributed 0 to the OLAP aggregate)
            try:
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
            except Exception as e:
                olap_error = e
                logger.error('%s-%s: %s\n%s' % (account, sequence, e, traceback.format_exc()))
            
            error_messages = []
            if bill_error is not None:
                error_messages.append('Bill error: '+str(bill_error))
            if oltp_error is not None:
                error_messages.append('OLTP error: '+str(oltp_error))
            if olap_error is not None:
                error_messages.append('OLAP error: '+str(olap_error))

            if error_messages == []:
                # no errors: log bill as OK or include it in report if its
                # energy doesn't match OLTP
                if close_enough(bill_therms, oltp_therms):
                    logger.info('%s-%s is OK' % (account, sequence))
                else:
                    result_dict.update({
                        'olap_therms': olap_therms,
                        'oltp_therms': oltp_therms
                    })
                    logger.warning('%s-%s differs from OLTP' % (account, sequence))
            else:
                # put errors in report
                result_dict.update({ 'errors': '. '.join(error_messages)+'.' })
            result += json_util.dumps(result_dict) + ',\n'

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

    # set up config dicionaries for data access objects used in generate_report
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
        'user': args.stateuser
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
    print billdb_config, statedb_config

    # log file goes in billing/reebill (where reebill.log also goes)
    log_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
            '..', 'reebill', LOG_FILE_NAME)
    # delete old log file
    try:
        os.remove(log_file_path)
    except OSError as oserr:
        if oserr.errno != errno.ENOENT:
            raise
    # set up logger
    logger = logging.getLogger('reconciliation_report')
    formatter = logging.Formatter(LOG_FORMAT)
    handler = logging.FileHandler(log_file_path)
    handler.setFormatter(formatter)
    logger.addHandler(handler) 
    logger.setLevel(logging.DEBUG)

    try:
        generate_report(logger, billdb_config, statedb_config, splinter_config,
                monguru_config)
    except Exception as e:
        print >> sys.stderr, '%s\n%s' % (e, traceback.format_exc())
        logger.critical("Couldn't generate reconciliation report: %s\n%s"
                % (e, traceback.format_exc()))

if __name__ == '__main__':
    main()
