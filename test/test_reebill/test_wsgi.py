from test.setup_teardown import TestCaseWithSetup, clear_db
from test.testing_utils import TestCase, ReebillRestTestClient
from test import init_test_config
from core import init_model


def setUpModule():
    init_test_config()
    init_model()


class AccountsResourceTest(TestCase):

    def setUp(self):
        clear_db()
        TestCaseWithSetup.insert_data()
        self.app = ReebillRestTestClient()

    def tearDown(self):
        clear_db()

    def test_put(self):
        self.app.put('/accounts/1')
        self.res.handle_put()