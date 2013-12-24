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
import unittest
pp = pprint.PrettyPrinter(indent=1).pprint

class MockStatePayment():
    def __init__(self,credit,thedate):
        self.customer=2
        self.credit=credit
        self.date_received=thedate
        self.date_applied=thedate
        self.description="Some Payment"

class MockStateReebill():
    def __init__(self,account, sequence, version):
        self.customer=2
        self.sequence=sequence
        self.issued=1
        self.issue_date=date(2011,12,15)
        self.version=version

class MockDao():
    def load_reebills_for(self, account, version):
        return [example_data.get_reebill(account,x,version=(x-1)) for x in (1,2,3)]

class MockStateDB():
    def payments(self, session, account):
        return [MockStatePayment(x['credit'], x['thedate']) for x in ({'credit':400.13,
                                                                       'thedate':date(2011,12,11)},
                                                                      {'credit':13.17,
                                                                       'thedate':date(2011,12,12)})]
    def listAccounts(self, session):
        return ['10003','10004']
    def get_reebill(self, session, account, sequence, version):
        return MockStateReebill(None,1,0)

class ExporterTest(unittest.TestCase):

    def test_reebill_details_dataset(self):
        dao=MockDao()
        statedb=MockStateDB()
        exporter = Exporter(statedb, dao)
        dataset=exporter.get_export_reebill_details_dataset(None, None, None)

        correct_data=[['10003', 1, 0, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2011-12-15', '2011-11-12', '2011-12-14', 980.33, 743.4900000000001, 236.84, 1027.79, 10, '2011-12-11', 400.13, 0, 1027.79, 118.42, 12.34, 1146.21, '', 118.42, 118.42, 188.20197727, 1.2584352376926542],
           ['10003', 1, 0, None, None, None, None, None, None, None, None, None, None, '2011-12-12', 13.17, None, None, None, None, None, None, None, None, None, None],
           ['10003', 2, 1, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2011-12-15', '2011-11-12', '2011-12-14', 980.33, 743.4900000000001, 236.84, 1027.79, 10, None, None, 0, 1027.79, 118.42, 12.34, 1146.21, '', 118.42, 236.84, 188.20197727, 1.2584352376926542],
           ['10003', 3, 2, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2011-12-15', '2011-11-12', '2011-12-14', 980.33, 743.4900000000001, 236.84, 1027.79, 10, None, None, 0, 1027.79, 118.42, 12.34, 1146.21, '', 118.42, 355.26, 188.20197727, 1.2584352376926542],
           ['10004', 1, 0, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2011-12-15', '2011-11-12', '2011-12-14', 980.33, 743.4900000000001, 236.84, 1027.79, 10, '2011-12-11', 400.13, 0, 1027.79, 118.42, 12.34, 1146.21, '', 118.42, 118.42, 188.20197727, 1.2584352376926542],
           ['10004', 1, 0, None, None, None, None, None, None, None, None, None, None, '2011-12-12', 13.17, None, None, None, None, None, None, None, None, None, None],
           ['10004', 2, 1, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2011-12-15', '2011-11-12', '2011-12-14', 980.33, 743.4900000000001, 236.84, 1027.79, 10, None, None, 0, 1027.79, 118.42, 12.34, 1146.21, '', 118.42, 236.84, 188.20197727, 1.2584352376926542],
           ['10004', 3, 2, u'Managing Member Monroe Towers  Silver Spring MD 20910', u'Monroe Towers  Washington DC 20010', '2011-12-15', '2011-11-12', '2011-12-14', 980.33, 743.4900000000001, 236.84, 1027.79, 10, None, None, 0, 1027.79, 118.42, 12.34, 1146.21, '', 118.42, 355.26, 188.20197727, 1.2584352376926542]]

        for indx,row in enumerate(dataset):
            self.assertEqual(row, dataset[indx])

    def test_