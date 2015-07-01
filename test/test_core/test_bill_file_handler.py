"""Unit tests for core.bill_file_handler.BillFileHandler.
These tests should not connect to a network or database.
"""
from StringIO import StringIO
import unittest

from boto.s3.bucket import Bucket
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from mock import Mock

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from test import init_test_config
init_test_config()

from core.model import UtilBill
from core.bill_file_handler import BillFileHandler
from core.utilbill_loader import UtilBillLoader
from exc import MissingFileError, DuplicateFileError


class BillFileHandlerTest(unittest.TestCase):

    def setUp(self):
        bucket_name = 'test-bucket'
        connection = Mock(autospec=S3Connection)
        self.bucket = Mock(autospec=Bucket)
        self.bucket.name = bucket_name
        connection.get_bucket.return_value = self.bucket
        self.key = Mock(autospec=Key)
        self.bucket.new_key.return_value = self.key
        self.bucket.get_key.return_value = self.key

        self.utilbill_loader = Mock(autospec=UtilBillLoader)
        self.utilbill_loader.count_utilbills_with_hash.return_value = 0

        url_format = 'https://example.com/%(bucket_name)s/%(key_name)s'
        self.bfh = BillFileHandler(connection, bucket_name,
                                   self.utilbill_loader, url_format)

        self.file = StringIO('test_file_data')
        self.file_hash = \
            'ab5c23a2b20284db26ae474c1d633dd9a3d76340036ab69097cf3274cf50a937'
        self.key_name = self.file_hash + '.pdf'
        self.utilbill = Mock(autospec=UtilBill)
        self.utilbill.sha256_hexdigest = self.file_hash
        self.utilbill.state = UtilBill.Complete

    def test_compute_hexdigest(self):
        self.assertEqual(self.file_hash, self.bfh.compute_hexdigest(self.file))

    def test_get_s3_url(self):
        self.utilbill.state = UtilBill.Complete
        expected = 'https://example.com/%s/%s' % (
            self.bucket.name, self.file_hash + '.pdf')
        self.assertEqual(expected, self.bfh.get_url(self.utilbill))

        self.utilbill.state = UtilBill.Estimated
        self.assertEqual('', self.bfh.get_url(self.utilbill))

    def test_check_file_exists(self):
        # success
        self.bfh.check_file_exists(self.utilbill)
        self.bucket.get_key.assert_called_once_with(self.key_name)

        # failure
        self.bucket.reset_mock()
        self.bucket.get_key.return_value = None
        with self.assertRaises(MissingFileError):
            self.bfh.check_file_exists(self.utilbill)
        self.bucket.get_key.assert_called_once_with(self.key_name)

    def test_url_for_missing_files(self):
        # it doesn't matter what the URL is, only that it gets returned
        # without an error
        self.utilbill.sha256_hexdigest = ''
        self.bfh.get_url(self.utilbill)
        self.utilbill.sha256_hexdigest = None
        self.bfh.get_url(self.utilbill)

    def test_upload_to_s3(self):
        self.bfh.upload_file_for_utilbill(self.utilbill, self.file)

        self.bucket.new_key.assert_called_once_with(self.key_name)
        self.key.set_contents_from_file.assert_called_once_with(self.file)

    def test_delete_utilbill_pdf_from_s3_one_utilbill(self):
        """The UtilBill should be deleted when delete_utilbill_pdf_from_S3 is
        called, as long as there is only one UtilBill instance persisted
        having the given sha256_hexdigest"""
        key_name = self.bfh.get_key_name_for_utilbill(self.utilbill)

        self.bfh.upload_file_for_utilbill(self.utilbill, self.file)

        #Ensure we've uploaded the file
        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(self.file)

        self.utilbill_loader.count_utilbills_with_hash.return_value = 1
        self.bfh.delete_file(self.utilbill)

        #Ensure the file is gone
        self.utilbill_loader.count_utilbills_with_hash.assert_with(
            self.file_hash)
        self.key.delete.assert_called_once_with()

    def test_delete_utilbill_pdf_from_s3_with_two_utilbills_same_hexdigest(self):
        """The UtilBill should NOT be deleted from s3 when
        delete_utilbill_pdf_from_S3 is called, if there are two UtilBill
        instances persisted having the given sha256_hexdigest"""
        key_name = self.bfh.get_key_name_for_utilbill(self.utilbill)

        self.bfh.upload_file_for_utilbill(self.utilbill, self.file)

        #Ensure we've uploaded the file correctly
        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(self.file)

        self.utilbill_loader.count_utilbills_with_hash.return_value = 2
        self.bfh.delete_file(self.utilbill)

        #Ensure the file is *still in S3* even though we have called delete
        self.utilbill_loader.count_utilbills_with_hash.assert_called_with(
            self.file_hash)
        self.assertEqual(0, self.key.delete.call_count)

    def test_delete_missing_file(self):
        """Test that no exception is raised when trying to delete a file that
        is already missing--we saw this happen in production.

        This situation could be caused by rolling back a database transaction
        when an error happened while trying to delete a bill, after the file was
        deleted, leaving the database pointing to a nonexistent key.
        """
        self.bfh.upload_file_for_utilbill(self.utilbill, self.file)
        self.utilbill_loader.count_utilbills_with_hash.return_value = 1
        self.bucket.get_key.return_value = None

        # no exception raised here
        self.bfh.delete_file(self.utilbill)

    def test_upload_duplicate_file(self):
        self.utilbill_loader.count_utilbills_with_hash.return_value = 1

        # both uploading methods should raise an exception if there is already
        # a file with the given hash
        with self.assertRaises(DuplicateFileError):
            self.bfh.upload_file(self.file)
        with self.assertRaises(DuplicateFileError):
            self.bfh.upload_file_for_utilbill(self.utilbill, self.file)

    def test_write_copy_to_file(self):
        self.key.get_contents_to_file = lambda f: f.write('data')

        output_file = StringIO()
        self.bfh.write_copy_to_file(self.utilbill, output_file)

        output_file.seek(0)
        self.assertEqual('data', output_file.read())
