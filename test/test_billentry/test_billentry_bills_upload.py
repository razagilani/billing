import billentry
from core import init_model
from StringIO import StringIO
from unittest import TestCase
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

    def tearDown(self):
        clear_db()

    def test_upload_bills(self):
        file = StringIO('fake PDF')
        file_hash = '396bb98e4ca497a698daa2a3c066cdac7730bd744cd7feb4cc4e3366452d99fd.pdf'
        self.app.post(self.URL_PREFIX + 'uploadfile', data=dict(file=(file, 'fake.pdf')))
        self.assertTrue(self.billupload.file_exists(file_hash))
