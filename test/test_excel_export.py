#!/usr/bin/env python2
from billing.processing.excel_export import Exporter
from datetime import date, datetime, timedelta
from billing.util import dateutils
from billing.test.setup_teardown import TestCaseWithSetup
from billing.test import example_data
from billing.processing.session_contextmanager import DBSession
from StringIO import StringIO
from billing.processing.state import StateDB, ReeBill, Customer, UtilBill
import billing.processing.fetch_bill_data as fbd
from skyliner.mock_skyliner import MockSplinter
from skyliner.sky_handlers import cross_range
from billing.processing import mongo
import random
import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ExporterTest(TestCaseWithSetup):

    def test_reebill_details_dataset(self):
        accounts = ['99999', '99998', '99997']

        # create mock skyliner objects
        monguru = self.splinter.get_monguru()

        with DBSession(self.state_db) as session:
            for account in accounts:
                # create 2 utility bills and 2 reebills
                self.process.upload_utility_bill(session, account, 'gas',
                         date(2013,1,1), date(2013,2,1),
                         StringIO('January 2013'), 'January.pdf', total=300,
                         state=UtilBill.Complete)
                customer = self.state_db.get_customer(session, account)
                utilbill1 = session.query(UtilBill).filter_by(customer = customer).one()

                self.process.create_first_reebill(session, utilbill1)
                reebill1 = self.reebill_dao.load_reebill(account, 1)
                install = self.splinter.get_install_obj_for(account)
                fbd.fetch_oltp_data(self.splinter, install.name, reebill1)
                self.process.compute_reebill(session,reebill1)
                self.process.issue(session, account, 1)

                self.process.upload_utility_bill(session, account, 'gas',
                         date(2013,2,1), date(2013,3,1),
                         StringIO('February 2013'), 'February.pdf', total=500,
                         state=UtilBill.Complete)
                self.process.create_next_reebill(session,account)
                reebill2 = self.reebill_dao.load_reebill(account, 2)
                fbd.fetch_oltp_data(self.splinter, install.name, reebill2.reebill_dict )
                self.process.compute_reebill(session,reebill2)
                self.process.issue(session, account, 2)



        exporter = Exporter(self.state_db, self.reebill_dao)
        dataset=exporter.get_export_reebill_details_dataset(session, None, None)
        pp(dataset.__dict__)


