import os
import unittest
import tempfile
from json import dumps

from core import init_model
from core.model import Session, UtilityAccount, Address
from pg import wsgi
from pg.pg_model import PGAccount
from test import init_test_config
from test.setup_teardown import TestCaseWithSetup


class TestPGWeb(unittest.TestCase):

    def setUp(self):
        #self.db_fd, wsgi.app.config['DATABASE'] = tempfile.mkstemp()
        wsgi.app.config['TESTING'] = True
        self.app = wsgi.app.test_client()

        init_test_config()
        init_model()

        s = Session()
        TestCaseWithSetup.truncate_tables(s)
        ua1 = UtilityAccount('Account 1', '11111', None, None, None,
                           Address(), Address(), '1')
        ua2 = UtilityAccount('Account 2', '22222', None, None, None,
                           Address(), Address(), '2')
        ua3 = UtilityAccount('Not PG', '33333', None, None, None,
                           Address(), Address(), '3')
        ua1.id, ua2.id, ua3.id = 1, 2, 3
        s.add_all([ua1, ua2, ua3])
        s.add_all([PGAccount(ua1), PGAccount(ua2)])
        s.commit()

    def test_accounts(self):
        rv = self.app.get('/utilitybills/accounts')
        self.assertEqual(dumps([
            {'utility_account_number': '1', 'account': '11111', 'id': 1},
            {'utility_account_number': '2', 'account': '22222', 'id': 2},
        ]), rv.data)

    def tearDown(self):
        TestCaseWithSetup.truncate_tables(Session())
        #os.close(self.db_fd)
        #os.unlink(wsgi.app.config['DATABASE'])

