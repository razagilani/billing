'''Unit tests for core.billupload.BillUpload.
These tests should not connect to a network or database.
'''
from StringIO import StringIO
import unittest

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from mock import Mock
from boto.s3.bucket import Bucket

from billing import init_model
from billing.core.model import UtilBill, UtilBillLoader
from billing.core.bill_file_handler import BillFileHandler
from test import init_test_config

init_test_config()


class BillUploadTest(unittest.TestCase):

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
        self.bu = BillFileHandler(connection, bucket_name, self.utilbill_loader,
                             url_format)
        init_model()

    def test_compute_hexdigest(self):
        self.assertEqual(self.bu.compute_hexdigest(StringIO('asdf')),
            'f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b')

    def test_get_s3_url(self):
        ub = Mock(autospec=UtilBill)
        the_hash = 'f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        ub.sha256_hexdigest = the_hash
        expected = 'https://example.com/%s/utilbill/%s' % (self.bucket.name,
                                                          the_hash)
        self.assertEqual(expected, self.bu.get_s3_url(ub))

    def test_utilbill_key_name(self):
        ub = Mock()
        ub.sha256_hexdigest = 'f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        expected = 'utilbill/' + ub.sha256_hexdigest
        self.assertEqual(self.bu._get_key_name(ub), expected)

    def test_upload_to_s3(self):
        key_name = 'utilbill/f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        test_file = StringIO('asdf')

        utilbill = Mock(autospec=UtilBill)
        self.bu.upload_utilbill_pdf_to_s3(utilbill, test_file)

        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(test_file)

    def test_delete_utilbill_pdf_from_s3_one_utilbill(self):
        """The UtilBill should be deleted when delete_utilbill_pdf_from_S3 is
        called, as long as there is only one UtilBill instance persisted
        having the given sha256_hexdigest"""
        sha256_hexdigest = 'ab5c23a2b20284db26ae474c1d633dd9a3d76340036ab69097cf3274cf50a937'
        ub = Mock(autospec=UtilBill)
        ub.sha256_hexdigest = sha256_hexdigest

        key_name = self.bu._get_key_name(ub)

        test_file = StringIO('test_file_data')
        self.bu.upload_utilbill_pdf_to_s3(ub, test_file)

        #Ensure we've uploaded the file
        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(test_file)

        self.utilbill_loader.count_utilbills_with_hash.return_value = 1
        self.bu.delete_utilbill_pdf_from_s3(ub)

        #Ensure the file is gone
        self.utilbill_loader.count_utilbills_with_hash.assert_called_once_with(
            sha256_hexdigest)
        self.key.delete.assert_called_once_with()

    def test_delete_utilbill_pdf_from_s3_with_two_utilbills_same_hexdigest(self):
        """The UtilBill should NOT be deleted from s3 when
        delete_utilbill_pdf_from_S3 is called, if there are two UtilBill
        instances persisted having the given sha256_hexdigest"""
        sha256_hexdigest = 'ab5c23a2b20284db26ae474c1d633dd9a3d76340036ab69097cf3274cf50a937'
        ub = Mock(autospec=UtilBill)
        ub.sha256_hexdigest = sha256_hexdigest
        key_name = self.bu._get_key_name(ub)

        test_file = StringIO('test_file_data')
        self.bu.upload_utilbill_pdf_to_s3(ub, test_file)

        #Ensure we've uploaded the file correctly
        self.bucket.new_key.assert_called_once_with(key_name)
        self.key.set_contents_from_file.assert_called_once_with(test_file)

        self.utilbill_loader.count_utilbills_with_hash.return_value = 2
        self.bu.delete_utilbill_pdf_from_s3(ub)

        #Ensure the file is *still in S3* even though we have called delete
        self.utilbill_loader.count_utilbills_with_hash.assert_called_once_with(
            sha256_hexdigest)
        self.assertEqual(0, self.key.delete.call_count)

if __name__ == '__main__':
    unittest.main()
