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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from billing import mongo
from billing.reebill import render
from billing.processing import state
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from skyliner.sky_paths import BufferingTLSSMTPHandler
from billing.nexus_util import NexusUtil
from billing.processing.session_contextmanager import DBSession
from billing.processing import fetch_bill_data as fbd
from billing.processing.process import Process
from billing.processing.rate_structure import RateStructureDAO
from billing.processing.reebill.journal import NewReebillVersionEvent
from billing.users import UserDAO
from billing.test.fake_skyliner import FakeSplinter

# config file containing database connection info etc. 
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
        'reebill', 'reebill.cfg')

# identifier of the user who makes bill corrections
# (this must exist in the database given by the "usersdb" part of the config
# file above)
USER_ID = 'dev' # TODO change
USER_PW = 'dev'

# general email parameters
MAIL_FROM = 'reports@skylineinnovations.com'
MAIL_CREDENTIALS = ('reports@skylineinnovations.com', 'electricsh33p')
MAIL_HOST = 'smtp.gmail.com'
MAIL_PORT = 587

# email parameters for report
DEFAULT_REPORT_RECIPIENT = 'dklothe@skylineinnovations.com'
REPORT_MAIL_SUBJECT = 'Automatic Bill Corrections %s' % datetime.now().strftime('%Y-%m-%d')

# email parameters for log
DEFAULT_LOG_RECIPIENT = 'dklothe@skylineinnovations.com'
LOG_MAIL_SUBJECT = 'Bill Correction Log %s' % datetime.now().strftime('%Y-%m-%d')
LOG_MAIL_CAPACITY = 5000

LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'


class BillCorrector(object):
    def __init__(self, billdb_config, statedb_config, usersdb_config,
            journal_config, ratestructure_config, splinter_config,
            logger, report_recipient, log_recipient):
        # data accesss objects
        self.state_db = state.StateDB(**statedb_config)
        self.reebill_dao = mongo.ReebillDAO(self.state_db,
                billdb_config['host'], billdb_config['port'],
                billdb_config['database'])
        self.session = self.state_db.session()
        self.splinter = Splinter(**splinter_config)
        self.nexus_util = NexusUtil('nexus')
        self.rate_structure_dao = RateStructureDAO(**ratestructure_config)
        self.process = Process(self.state_db, self.reebill_dao,
                self.rate_structure_dao, None, self.nexus_util, self.splinter)
        self.report_recipient = report_recipient
        self.log_recipient = log_recipient

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
        '''Checks all bills and makes corrections.'''
        # record what happened in a tabular report
        self.report = tablib.Dataset(headers=['Account', 'Sequence',
                'Original Total', 'New Total'])

        with DBSession(self.state_db) as session:
            # for account in ['10001']:
            for account in sorted(self.state_db.listAccounts(session)):
                # check most recent bills first: more likely to have errors
                sequences = [s for s in
                        self.state_db.listSequences(session, account) if
                        self.state_db.is_issued(session, account, s)]
                # for sequence in [31]:
                for sequence in reversed(sequences):
                    try:
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

        try:
            self.send_report()
        except smtplib.SMTPException as e:
            self.logger.error('SMTP Error when emailing report: %s' % traceback.format_exc())

    def send_report(self):
        # if nothing got corrected, don't send an email
        if self.report.height == 0:
            return

        # construct the email text
        report_mail_text = 'Bill Corrections:\n' + self.report.html # TODO change

        # build multipart mime structure
        msg = MIMEMultipart('alternative')
        msg['From'] = MAIL_FROM
        msg['To'] = self.report_recipient
        msg['Subject'] = REPORT_MAIL_SUBJECT
        #plain_part = MIMEText('TODO put in plain text', 'text')
        html_part = MIMEText(report_mail_text, 'html')
        #msg.attach(plain_part)
        msg.attach(html_part)

        # send the email
        smtp = smtplib.SMTP(MAIL_HOST, MAIL_PORT)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(*MAIL_CREDENTIALS)
        smtp.sendmail(MAIL_FROM, self.report_recipient, msg.as_string())
        smtp.quit()

def main():
    # command-line arguments
    parser = argparse.ArgumentParser(description=('Re-check bills and make '
            'corrections when energy sold has changed.'))
    parser.add_argument('--report-to',  default=DEFAULT_REPORT_RECIPIENT,
            help='recipient(s) of report email (default: %s)' %
            DEFAULT_REPORT_RECIPIENT)
    parser.add_argument('--log-to',  default=DEFAULT_LOG_RECIPIENT,
            help='recipient(s) of log email (default: %s)' %
            DEFAULT_LOG_RECIPIENT)
    args = parser.parse_args()


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
    email_handler = BufferingTLSSMTPHandler((MAIL_HOST, MAIL_PORT), MAIL_FROM,
            args.log_to, LOG_MAIL_SUBJECT, LOG_MAIL_CAPACITY,
            credentials=MAIL_CREDENTIALS, secure=())
    email_handler.setLevel(logging.DEBUG)
    email_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(email_handler)

    try:
        logger.info('Starting automatic bill correction')
        corrector = BillCorrector(billdb_config, statedb_config,
                usersdb_config, journal_config, ratestructure_config,
                splinter_config, logger, args.report_to, args.log_to)
        corrector.go()
    except Exception as e:
        print >> sys.stderr, '%s\n%s' % (e, traceback.format_exc())
        logger.critical("Error during automatic bill correction: %s\n%s"
                % (e, traceback.format_exc()))

if __name__ == '__main__':
    main()
