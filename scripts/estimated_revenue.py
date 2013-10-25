#!/usr/bin/env python
'''Script to generate a "estimated revenue report" 

This should be run by cron to generate a static JSON file, which can be loaded
and returned for display in an Ext-JS grid in the browser.

'''
import os
import sys
import errno
import traceback
import datetime
import argparse
import logging
from billing.processing import mongo
from billing.processing import state
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner import sky_handlers
from billing.util.nexus_util import NexusUtil
from billing.util import json_util
from billing.util import dateutils
from billing.util.dateutils import date_to_datetime
from billing.processing.session_contextmanager import DBSession
from billing.processing import rate_structure as rs
from billing.processing.billupload import BillUpload
from billing.processing.estimated_revenue import EstimatedRevenue
from billing.util import monthmath
from StringIO import StringIO



OUTPUT_FILE_NAME = 'estimated_revenue_report.json'
OUTPUT_XLS_FILE_NAME = 'estimated_revenue_report.xls'
LOG_FILE_NAME = 'estimated_revenue.log'
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

# For BillUpload
# default name of log file (config file can override this)
BILL_UPLOAD_LOG_FILE_NAME = 'bill_upload.log'

#def estimated_revenue_report(self, start, limit, **kwargs):
def generate_report(logger, billdb_config, statedb_config, splinter_config,
        oltp_url, reportoutputdir, output_file_name, output_xls_file_name, nexushost, skip_oltp=False):
    '''Handles AJAX request for data to fill estimated revenue report
    grid.''' 

    logger.info('Begin generating estimated revenue report')

    # objects for database access
    state_db = state.StateDB(**statedb_config)
    session = state_db.session()

    reebill_dao = mongo.ReebillDAO(state_db,
            pymongo.Connection(billdb_config['host'],
            int(billdb_config['port']))[billdb_config['database']])
    ratestructure_dao = rs.RateStructureDAO(billdb_config['host'], billdb_config['port'], billdb_config['database'],
        reebill_dao)

    # not needed to run estimated revenue report
    billUpload = None

    # create a NexusUtil
    # TODO: support the integrate skyline_backend option
    nexus_util = NexusUtil(nexushost)

    splinter = Splinter(oltp_url, **splinter_config)

    with DBSession(state_db) as session:
        #start, limit = int(start), int(limit)
        er = EstimatedRevenue(state_db, reebill_dao,
                ratestructure_dao, billUpload, nexus_util,
                splinter)
        data = er.report(session)

        # build list of rows from report data
        rows = []
        for account in sorted(data.keys(),
                # 'total' first
                cmp=lambda x,y: -1 if x == 'total' else 1 if y == 'total' else cmp(x,y)):
            row = {'account': 'Total' if account == 'total' else account}
            for month in data[account].keys():
                # show error message instead of value if there was one
                if 'error' in data[account][month]:
                    value = 'ERROR: %s' % data[account][month]['error']
                elif 'value' in data[account][month]:
                    value = '%.2f' % data[account][month]['value']

                row.update({
                    'revenue_%s_months_ago' % (monthmath.current_utc() - month): {
                        'value': value,
                        'estimated': data[account][month].get('estimated', False)
                    }
                })
            rows.append(row)

        # write the dictionary to the file
        with open(os.path.join(reportoutputdir, output_file_name), 'w') as output_file:
            logger.info('Generating estimated revenue report %s' %
                    os.path.join(reportoutputdir, output_file_name))
            output_file.write(json_util.dumps({'rows':rows}))
            output_file.flush()


        # create the xls representation
        with open(os.path.join(reportoutputdir, output_xls_file_name), 'w') as output_xls_file:
            logger.info('Generating estimated revenue report %s' %
                    os.path.join(reportoutputdir, output_xls_file_name))
            buf = StringIO()
            er.write_report_xls(session, buf)
            output_xls_file.write(buf.getvalue())
            output_xls_file.flush()



def main():
    # command-line arguments
    parser = argparse.ArgumentParser(description='Generate estimated revenue report.')
    parser.add_argument('--statedbhost',  default='localhost',
            help='statedb host (default: localhost)')
    parser.add_argument('--billdbhost',  default='localhost',
            help='billdb host (default: localhost)')
    parser.add_argument('--oltphost',  default='localhost',
            help='oltp host (default: localhost)')
    parser.add_argument('--olaphost',  default='localhost',
            help='olap host (default: localhost)')
    parser.add_argument('--statedb', default='skyline_dev',
            help='name of state database (default: skyline_dev)')
    parser.add_argument('--stateuser', default='dev',
            help='username for state database (default: dev)')
    parser.add_argument('--statepw', default='dev',
            help='name of state database (default: dev)')
    parser.add_argument('--billdb', default='skyline',
            help='name of bill database (default: skyline)')
    parser.add_argument('--olapdb',  default='dev',
            help='name of OLAP database (default: dev)')
    parser.add_argument('--skip-oltp',  action='store_true',
            help="Don't include OLTP data (much faster)")
    parser.add_argument('--nexushost', default='nexus',
            help="Name of nexus host")
    parser.add_argument('--reportoutputdir', default='',
            help="Directory to write static report file.")
    parser.add_argument('--logoutputdir', default='',
            help="Directory to write static report file.")
    args = parser.parse_args()

    # set up config dicionaries for data access objects used in generate_report
    billdb_config = {
        'database': args.billdb,
        'host': args.billdbhost,
        'port': '27017'
    }
    statedb_config = {
        'host': args.statedbhost,
        'password': args.statepw,
        'database': args.statedb,
        'user': args.stateuser
    }
    oltp_url = 'http://duino-drop.appspot.com/'
    splinter_config = {
        'skykit_host': args.oltphost,
        'skykit_db': args.olapdb,
        'olap_cache_host': args.olaphost,
        'olap_cache_db': args.olapdb,
        'monguru_options': {
            'olap_cache_host': args.olaphost,
            'olap_cache_db': args.olapdb,
            'cartographer_options': {
                'olap_cache_host': args.olaphost,
                'olap_cache_db': args.olapdb,
                'measure_collection': 'skymap',
                'install_collection': 'skykit_installs',
                'nexus_db': 'nexus',
                'nexus_collection': 'skyline',
            },
        },
        'cartographer_options': {
            'olap_cache_host': args.olaphost,
            'olap_cache_db': args.olapdb,
            'measure_collection': 'skymap',
            'install_collection': 'skykit_installs',
            'nexus_db': 'nexus',
            'nexus_collection': 'skyline',
        },
    }

    # log file goes in billing/reebill (where reebill.log also goes)
    log_file_path = os.path.join(args.logoutputdir, LOG_FILE_NAME)

    # delete old log file
    try:
        os.remove(log_file_path)
    except OSError as oserr:
        if oserr.errno != errno.ENOENT:
            raise
    # set up logger
    logger = logging.getLogger('estimated revenue_report')
    formatter = logging.Formatter(LOG_FORMAT)
    handler = logging.FileHandler(log_file_path)
    handler.setFormatter(formatter)
    logger.addHandler(handler) 
    logger.setLevel(logging.DEBUG)
    
    try:
        # write the json string to a file: it goes in billing/reebill
        generate_report(logger, billdb_config, statedb_config,
                splinter_config, oltp_url, 
                args.reportoutputdir, OUTPUT_FILE_NAME, OUTPUT_XLS_FILE_NAME, 
                args.nexushost, skip_oltp=args.skip_oltp)
    except Exception as e:
        print >> sys.stderr, '%s\n%s' % (e, traceback.format_exc())
        logger.critical("Couldn't generate estimated revenue report: %s\n%s"
                % (e, traceback.format_exc()))

if __name__ == '__main__':
    main()
