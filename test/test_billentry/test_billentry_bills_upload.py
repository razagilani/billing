import billentry
from billentry.billentry_model import BillEntryUser, Role
from core import init_model
from StringIO import StringIO
from unittest import TestCase
from core.model import Session, UtilBill, Utility, UtilityAccount, Address
from exc import MissingFileError
from test import init_test_config, clear_db
from test.setup_teardown import FakeS3Manager, create_utilbill_processor


class TestUploadBills(TestCase):

    URL_PREFIX = '/utilitybills/'

    @classmethod
    def setUpClass(cls):
        init_test_config()
        init_model()

        # these objects don't change during the tests, so they should be
        # created only once.
        FakeS3Manager.start()
        cls.utilbill_processor = create_utilbill_processor()
        cls.billupload = cls.utilbill_processor.bill_file_handler
        cls.app = billentry.app.test_client()

    @classmethod
    def tearDownClass(cls):
        FakeS3Manager.stop()

    def setUp(self):
        clear_db()
        s = Session()
        s.flush()
        self.admin_role = Role('admin', 'admin role for bill entry app')
        self.user1 = BillEntryUser(email='1@example.com', password='password')
        self.user1.id = 1
        self.user2 = BillEntryUser(email='2@example.com', password='password')
        self.user2.id = 2
        self.user3 = BillEntryUser(email='3@example.com', password='password')
        self.user3.id = 3
        self.utility = Utility(name='Empty Utility')
        self.utility.id = 1
        self.utility_account = UtilityAccount('Account 1', '1111',
                                              self.utility, None,
                                         None, Address(), Address(), '1')
        s.add_all([self.user1, self.user2, self.user3, self.admin_role,
            self.utility, self.utility_account])
        self.user2.roles = [self.admin_role]
        self.user3.roles = [self.admin_role]

    def tearDown(self):
        clear_db()

    def test_upload_utility_bill(self):
        s = Session()
        data = {'email':'1@example.com', 'password': 'password'}
        # post request for user login with for user2, member of no role
        self.app.post('/userlogin',
                      content_type='multipart/form-data', data=data)

        file1 = StringIO('fake PDF')
        file1_hash = '396bb98e4ca497a698daa2a3c066cdac7730bd744cd7feb4cc4e3366452d99fd.pdf'

        rv = self.app.post(self.URL_PREFIX + 'uploadfile', data=dict(file=(file1, 'fake.pdf')))
        # this should result in a status_code of '403 permission denied'
        # as only members of 'admin' role are allowed  access to upload
        # utility bill files and user1 is not a member of admin role
        self.assertEqual(403, rv.status_code)
        self.assertRaises(MissingFileError, self.billupload.file_exists, file1_hash)

        data = {'email':'2@example.com', 'password': 'password'}
        # post request for user login for user2, a member of admin role

        self.app.post('/userlogin',
                      content_type='multipart/form-data', data=data)

        file1 = StringIO('fake PDF')
        rv = self.app.post(self.URL_PREFIX + 'uploadfile', data=dict(file=(file1, 'fake.pdf')))
        # this should succeed with 200 as user1 is member of Admin Role
        self.assertEqual(200, rv.status_code)
        self.assertTrue(self.billupload.file_exists(file1_hash))

        # data = {'email':'3@example.com', 'password': 'password'}
        # # post request for user login for user2, a member of admin role
        #
        # self.app.post('/userlogin',
        #               content_type='multipart/form-data', data=data)

        file2 = StringIO('another fake PDF')
        file2_hash = '26dcbde01927edd35b546b91d689709c3c25ba85a948fb42210fff4ec0db4b11.pdf'
        rv = self.app.post(self.URL_PREFIX + 'uploadfile', data=dict(file=(file2, 'fake.pdf')))
        # this should succeed with 200 as user2 is member of Admin Role
        self.assertEqual(200, rv.status_code)
        self.assertTrue(self.billupload.file_exists(file2_hash))

        data = {'guid': '0b8ff51d-84a9-40bf-b97cf693ff00f4ed',
                'utility': 1,
                'utility_account_number': '2051.065106',
                'sa_addressee': 'College Park Car Wash',
                'sa_street': '7106 Ridgewood Ave',
                'sa_city': 'Chevy Chase',
                'sa_state': 'MD',
                'sa_postal_code': '20815-5148'
        }
        stored_hash1 = '396bb98e4ca497a698daa2a3c066cdac7730bd744cd7feb4cc4e3366452d99fd'
        stored_hash2 = '26dcbde01927edd35b546b91d689709c3c25ba85a948fb42210fff4ec0db4b11'
        rv = self.app.post(self.URL_PREFIX + 'uploadbill', data=data)
        self.assertEqual(200, rv.status_code)
        utilbill = s.query(UtilBill).filter_by(sha256_hexdigest=stored_hash1).all()
        self.assertEqual(len(utilbill), 1)
        utilbill = s.query(UtilBill).filter_by(sha256_hexdigest=stored_hash2).all()
        self.assertEqual(len(utilbill), 1)





