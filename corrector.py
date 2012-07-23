#!/usr/bin/python
'''This script checks all existing issued reebills against the latest OLTP data
and makes a correction if necessary.'''
import os
import sys
import errno
import traceback
from datetime import datetime
import argparse
import logging
from copy import deepcopy
import mongoengine
import tablib
import ConfigParser
from billing import mongo
from billing.reebill import render
from billing.processing import state
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner.sky_paths import BufferingTLSSMTPHandler
from billing.nexus_util import NexusUtil
from billing.session_contextmanager import DBSession
from billing.processing import fetch_bill_data as fbd
from billing.processing.process import Process
from billing.processing.rate_structure import RateStructureDAO
from billing.reebill.journal import NewReebillVersionEvent
from billing.users import UserDAO
from billing.test.fake_skyliner import FakeSplinter

# config file containing database connection info etc. 
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
        'reebill', 'reebill.cfg')

# identifier of the user who makes bill corrections
# (this must exist in the database given by the "usersdb" part of the config
# file above)
USER_ID = 'jwatson'
USER_PW = 'solarbeetu'

LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

# email reporting parameters
EMAIL_HOST_TUPLE = ('smtp.gmail.com', 587)
EMAIL_FROM_ADDR = 'reports@skylineinnovations.com'
EMAIL_TO_ADDR = 'dklothe@skylineinnovations.com'
EMAIL_SUBJECT = 'Bill Correction Log %s' % datetime.now().strftime('%Y-%m-%d')
EMAIL_CAPACITY = 5000
EMAIL_CREDENTIALS = ('reports@skylineinnovations.com', 'electricsh33p')

class BillCorrector(object):
    def __init__(self, billdb_config, statedb_config, usersdb_config,
            journal_config, ratestructure_config, splinter_config,
            logger):
        # data accesss objects
        self.state_db = state.StateDB(**statedb_config)
        self.reebill_dao = mongo.ReebillDAO(self.state_db,
                billdb_config['host'], billdb_config['port'],
                billdb_config['database'])
        self.session = self.state_db.session()
        self.splinter = Splinter(**splinter_config)
        self.nexus_util = NexusUtil()
        self.rate_structure_dao = RateStructureDAO(**ratestructure_config)
        self.process = Process(self.state_db, self.reebill_dao,
                self.rate_structure_dao, None, self.nexus_util, self.splinter)

        # get user that will correct the bills
        user_dao = UserDAO(**usersdb_config)
        self.user = user_dao.load_user(USER_ID, USER_PW)
        if self.user is None:
            raise Exception('User authentication failed: %s/%s' % (USER_ID,
                    USER_PW))

        # configure journal
        mongoengine.connect(journal_config['database'],
                host=journal_config['host'], port=int(journal_config['port']),
                alias='journal')

        self.logger = logger

    def go(self):
        # record what happened in a tabular report
        self.report = tablib.Dataset(headers=['Account', 'Sequence',
                'Original Total', 'New Total'])

        with DBSession(self.state_db) as session:
            #for account in sorted(self.state_db.listAccounts(session)):
            for account in ['10001']:
                # check most recent bills first: more likely to have errors
                sequences = [s for s in
                        self.state_db.listSequences(session, account) if
                        self.state_db.is_issued(session, account, s)]
                #for sequence in reversed(sequences):
                for sequence in [31]:
                    try:
                        raise Exception('here is an error');
                        # load reebill and duplicate it
                        original = self.reebill_dao.load_reebill(account, sequence)
                        copy = deepcopy(original)

                        # re-bind & recompute the copy
                        fbd.fetch_oltp_data(self.splinter,
                                self.nexus_util.olap_id(account), copy,
                                verbose=True)
                        predecessor = self.reebill_dao.load_reebill(account,
                                sequence - 1, version=0)
                        self.process.compute_bill(session, predecessor, copy)

                        # compare copy to original
                        if copy.total == original.total:
                            self.logger.info('%s-%s OK' % (account, sequence))
                        else:
                            # make the correction
                            # TODO this duplicates the bind & compute process
                            # above, but avoids code duplication; new_version()
                            # could be refactored to prevent this, or we could make
                            # fetch_oltp_data() fast enough that it won't matter
                            new_reebill = self.process.new_version(session,
                                    account, sequence)

                            # journal it
                            NewReebillVersionEvent.save_instance(user=self.user,
                                    account=account, sequence=sequence,
                                    version=new_reebill.version)

                            # log it
                            self.logger.warning(('%s-%s wrong: total corrected'
                                    ' from %s to %s') % (account, sequence,
                                    original.total, new_reebill.total))

                            # add to report
                            self.report.append((account, sequence, original.total,
                                new.total))
                    except Exception as e:
                        self.logger.error('Could not check %s-%s: %s' %
                                (account, sequence, traceback.format_exc()))
                        self.report.append((account, sequence, 'Error (could not check)', ''))

        self.send_report()

    def send_report(self):
        # TODO send email with this table in it
        # (from reports@skylineinnovations.com)
        print self.report.html

def main():
    # load config dictionaries from the main reebill config file
    config = ConfigParser.RawConfigParser()
    config.read(CONFIG_FILE_PATH)
    billdb_config = dict(config.items('billdb'))
    statedb_config = dict(config.items('statedb'))
    ratestructure_config = dict(config.items('rsdb'))
    splinter_config = {
        'raw_data_url': config.get('skyline_backend', 'oltp_url'),
        'skykit_host': config.get('skyline_backend', 'olap_host'),
        'skykit_db': config.get('skyline_backend', 'olap_database'),
        'olap_cache_host': config.get('skyline_backend', 'olap_host'),
        'olap_cache_db': config.get('skyline_backend', 'olap_database')
    }
    usersdb_config = dict(config.items('usersdb'))
    journal_config = dict(config.items('journaldb'))

    # set up logger. log is not the same as report: log is detailed and
    # contains technical info, but report just says which bills got corrected.
    log_file_path = 'reebill_corrector.log'
    try:
        os.remove(log_file_path)
    except OSError as oserr:
        if oserr.errno != errno.ENOENT:
            raise
    logger = logging.getLogger('reebill-corrector')
    formatter = logging.Formatter(LOG_FORMAT)
    handler = logging.FileHandler(log_file_path)
    handler.setFormatter(formatter)
    logger.addHandler(handler) 
    logger.setLevel(logging.INFO)

    # logging handler to send emails
    email_handler = BufferingTLSSMTPHandler(EMAIL_HOST_TUPLE, EMAIL_FROM_ADDR,
            EMAIL_TO_ADDR, EMAIL_SUBJECT, EMAIL_CAPACITY,
            credentials=EMAIL_CREDENTIALS, secure=())
    email_handler.setLevel(logging.DEBUG)
    email_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(email_handler)

    try:
        logger.info('Starting automatic bill correction')
        corrector = BillCorrector(billdb_config, statedb_config,
                usersdb_config, journal_config, ratestructure_config,
                splinter_config, logger)
        corrector.go()
    except Exception as e:
        print >> sys.stderr, '%s\n%s' % (e, traceback.format_exc())
        logger.critical("Error during automatic bill correction: %s\n%s"
                % (e, traceback.format_exc()))

if __name__ == '__main__':
    main()
