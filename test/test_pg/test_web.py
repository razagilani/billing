from datetime import datetime
import os
import unittest
import tempfile
from json import dumps, loads

from core import init_model
from core.model import Session, UtilityAccount, Address, UtilBill, Utility
from pg import wsgi
from pg.pg_model import PGAccount
from test import init_test_config
from test.setup_teardown import TestCaseWithSetup

# this may change
URL_PREFIX = '/utilitybills/'

class TestPGWeb(unittest.TestCase):

    maxDiff = None

    def assertJson(self, expected, actual):
        '''AssertEqual for JSON where the things being compared can be in
        either string or dict/list form.
        '''
        if isinstance(expected, basestring):
            expected = loads(expected)
        if isinstance(actual, basestring):
            actual = loads(actual)
        self.assertEqual(expected, actual)

    def setUp(self):
        #self.db_fd, wsgi.app.config['DATABASE'] = tempfile.mkstemp()
        wsgi.app.config['TESTING'] = True
        self.app = wsgi.app.test_client()

        init_test_config()
        init_model()

        s = Session()
        TestCaseWithSetup.truncate_tables(s)
        utility = Utility('Example Utility', Address())
        ua1 = UtilityAccount('Account 1', '11111', utility, None, None,
                           Address(), Address(), '1')
        ua2 = UtilityAccount('Account 2', '22222', utility, None, None,
                           Address(), Address(), '2')
        ua3 = UtilityAccount('Not PG', '33333', utility, None, None,
                           Address(), Address(), '3')
        ua1.id, ua2.id, ua3.id = 1, 2, 3
        s.add_all([ua1, ua2, ua3])
        s.add_all([PGAccount(ua1), PGAccount(ua2)])
        s.add_all([
            UtilBill(ua1, UtilBill.Complete, 'electric', utility, None,
                     None, Address(), Address(street='1 Example St.')),
            UtilBill(ua1, UtilBill.Complete, 'electric', utility, None,
                     None, Address(), Address(street='2 Example St.'))
        ])
        s.commit()

    def test_accounts(self):
        rv = self.app.get(URL_PREFIX + 'accounts')
        self.assertJson([
            {'utility_account_number': '1', 'account': '11111', 'id': 1},
            {'utility_account_number': '2', 'account': '22222', 'id': 2},
        ], rv.data)

    def test_utilbills_list(self):
        #rv = self.app.get(URL_PREFIX + 'utilitybills', data=dict(id=1))
        rv = self.app.get(URL_PREFIX + 'utilitybills?id=1')

        self.assertJson({
            'rows': [
                {'account': None,
                 'computed_total': 0.0,
                 'id': 12020,
                 'next_estimated_meter_read_date': None,
                 'pdf_url': '',
                 'period_end': None,
                 'period_start': None,
                 'processed': False,
                 'rate_class': 'None',
                 'service': 'Electric',
                 'service_address': '2 Example St., ,  ',
                 'supplier': 'None',
                 'supply_total': 0.0,
                 'total_charges': 0.0,
                 'total_energy': 0.0,
                 'utility': 'Example Utility',
                 'utility_account_number': '1'
                },
                {'account': None,
                 'computed_total': 0.0,
                 'id': 12019,
                 'next_estimated_meter_read_date': None,
                 'pdf_url': '',
                 'period_end': None,
                 'period_start': None,
                 'processed': False,
                 'rate_class': 'None',
                 'service': 'Electric',
                 'service_address': '1 Example St., ,  ',
                 'supplier': 'None',
                 'supply_total': 0.0,
                 'total_charges': 0.0,
                 'total_energy': 0.0,
                 'utility': 'Example Utility',
                 'utility_account_number': '1'
                }
        ],
            'results': 0,
        }, rv.data)

    def test_utilbill(self):
        rv = self.app.put(URL_PREFIX + 'utilitybills/?id=2', data=dict(
            id=1,
            period_start=datetime(2000,1,1).isoformat()
        ))
        self.assertJson([
        ], rv.data)

    def tearDown(self):
        TestCaseWithSetup.truncate_tables(Session())
        #os.close(self.db_fd)
        #os.unlink(wsgi.app.config['DATABASE'])

