'''Unit tests for core.bill_file_handler.BillFileHandler.
These tests should not connect to a network or database.
'''
from StringIO import StringIO
import unittest

from boto.s3.bucket import Bucket
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from mock import Mock

from billing.core.model import UtilBill, UtilBillLoader
from billing.core.bill_file_handler import BillFileHandler


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

        url_format = 'https://example.com/%(bucket_name)s/%(key_name)s'
        self.bfh = BillFileHandler(connection, bucket_name,
                                   self.utilbill_loader, url_format)

        self.file = StringIO('test_file_data')
        self.file_hash = \
            'ab5c23a2b20284db26ae474c1d633dd9a3d76340036ab69097cf3274cf50a937'

    def test_compute_hexdigest(self):
        self.assertEqual(self.file_hash, self.bfh.compute_hexdigest(self.file))

    def test_get_s3_url(self):
        ub = Mock(autospec=UtilBill)
        ub.sha256_hexdigest = self.file_hash
        ub.state = UtilBill.Complete
        expected = 'https://example.com/%s/utilbill/%s' % (self.bucket.name,
                                                          self.file_hash)
        self.assertEqual(expected, self.bfh.get_s3_url(ub))

        ub.state = UtilBill.Estimated
        self.assertEqual('', self.bfh.get_s3_url(ub))

    def test_utilbill_key_name(self):
        ub = Mock()
        ub.sha256_hexdigest = self.file_hash
        expected = 'utilbill/' + ub.sha256_hexdigest
        self.assertEqual(self.bfh._get_key_name(ub), expected)

    def test_upload_to_s3(self):
        key_name = 'utilbill/' + self.file_hash

        utilbill = Mock(autospec=UtilBill)
        self.bfh.upload_utilbill_pdf_to_s3(utilbill, self.file)

        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(self.file)

    def test_delete_utilbill_pdf_from_s3_one_utilbill(self):
        """The UtilBill should be deleted when delete_utilbill_pdf_from_S3 is
        called, as long as there is only one UtilBill instance persisted
        having the given sha256_hexdigest"""
        ub = Mock(autospec=UtilBill)
        ub.sha256_hexdigest = self.file_hash

        key_name = self.bfh._get_key_name(ub)

        self.bfh.upload_utilbill_pdf_to_s3(ub, self.file)

        #Ensure we've uploaded the file
        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(self.file)

        self.utilbill_loader.count_utilbills_with_hash.return_value = 1
        self.bfh.delete_utilbill_pdf_from_s3(ub)

        #Ensure the file is gone
        self.utilbill_loader.count_utilbills_with_hash.assert_called_once_with(
            self.file_hash)
        self.key.delete.assert_called_once_with()

    def test_delete_utilbill_pdf_from_s3_with_two_utilbills_same_hexdigest(self):
        """The UtilBill should NOT be deleted from s3 when
        delete_utilbill_pdf_from_S3 is called, if there are two UtilBill
        instances persisted having the given sha256_hexdigest"""
        ub = Mock(autospec=UtilBill)
        ub.sha256_hexdigest = self.file_hash
        key_name = self.bfh._get_key_name(ub)

        self.bfh.upload_utilbill_pdf_to_s3(ub, self.file)

        #Ensure we've uploaded the file correctly
        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(self.file)

        self.utilbill_loader.count_utilbills_with_hash.return_value = 2
        self.bfh.delete_utilbill_pdf_from_s3(ub)

        #Ensure the file is *still in S3* even though we have called delete
        self.utilbill_loader.count_utilbills_with_hash.assert_called_once_with(
            self.file_hash)
        self.assertEqual(0, self.key.delete.call_count)

if __name__ == '__main__':
    unittest.main()
