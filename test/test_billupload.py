from boto.s3.connection import S3Connection
from test import init_test_config
init_test_config()

from billing import init_model
from boto.exception import S3ResponseError
from StringIO import StringIO
from boto.s3.bucket import Bucket
from processing.state import UtilBill, Customer, Utility, Address
import unittest
from billing.processing.billupload import BillUpload
from billing import config
import os
import subprocess
from mock import Mock
from billing.processing.state import Session
from datetime import date
from os.path import join

class BillUploadTest(unittest.TestCase):

    # @classmethod
    # def setUpClass(cls):
    #     tmp_dir = join('/', 'tmp', 'fakes3_test')
    #     s3_args = ['fakes3', '--port', '4567', '--root', tmp_dir]
    #     cls.fakes3_process = subprocess.Popen(s3_args)
    #
    # @classmethod
    # def tearDownClass(cls):
    #     cls.fakes3_process.terminate()
    #     cls.fakes3_process.wait()

    def setUp(self):
        self.bu = BillUpload.from_config()
        init_model()

    def test_compute_hexdigest(self):
        self.assertEqual(self.bu.compute_hexdigest(StringIO('asdf')),
            'f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b')

    def test_get_amazon_bucket(self):
        bucket = self.bu._get_amazon_bucket()
        self.assertEqual(type(bucket), Bucket)
        self.assertEqual(bucket.name, config.get('bill', 'bucket'))
        self.assertEqual(bucket.connection.host, config.get('aws_s3', 'host'))

    def test_utilbill_key_name(self):
        ub = Mock()
        ub.sha256_hexdigest = 'f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        expected = 'utilbill/f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        self.assertEqual(self.bu._get_key_name(ub), expected)

    def test_upload_to_s3(self):
        key_name = 'utilbill/f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        test_data = 'asdf'

        utilbill = Mock(autospec=UtilBill)
        self.bu.upload_utilbill_pdf_to_s3(utilbill, StringIO(test_data))

        bucket = self.bu._get_amazon_bucket()
        k = bucket.new_key(key_name)
        self.assertEqual(test_data, k.get_contents_as_string())

    def test_delete_utilbill_pdf_from_s3_one_utilbill(self):
        """The UtilBill should be deleted when delete_utilbill_pdf_from_S3 is
        called, as long as there is only one UtilBill instance persisted
        having the given sha256_hexdigest"""
        fb_utility = Utility('some_utility', Address())
        ub = UtilBill(Customer('', '', 0.0, 0.0, '',
                               fb_utility, 'rate_class', Address(), Address()),
                      0, 'gas', fb_utility, 'test_rate_class', Address(),
                      Address(), period_start=date(2014, 1, 1),
                      period_end=date(2012, 1, 31))
        ub.sha256_hexdigest = 'ab5c23a2b20284db26ae474c1d633dd9a3d76340036ab69097cf3274cf50a937'

        key_name = self.bu._get_key_name(ub)

        s = Session()
        s.add(ub)
        s.flush()

        utilbill = Mock(autospec=UtilBill)
        self.bu.upload_utilbill_pdf_to_s3(utilbill, StringIO('test_file_data'))
        key_obj = self.bu._get_amazon_bucket().get_key(key_name)

        #Ensure we've uploaded the file
        self.assertEqual('test_file_data', key_obj.get_contents_as_string())

        self.bu.delete_utilbill_pdf_from_s3(ub)

        #Ensure the file is gone
        self.assertRaises(S3ResponseError, key_obj.get_contents_as_string)

    def test_delete_utilbill_pdf_from_s3_with_two_utilbills_same_hexdigest(self):
        """The UtilBill should NOT be deleted from s3 when
        delete_utilbill_pdf_from_S3 is called, if there are two UtilBill
        instances persisted having the given sha256_hexdigest"""

        s = Session()
        for x in range(2):
            fb_utility = Utility('some_utility', Address())
            ub = UtilBill(Customer('', str(x), 0.0, 0.0, '',
                                   fb_utility, 'rate_class', Address(), Address()),
                          0, 'gas', fb_utility, 'test_rate_class', Address(),
                          Address(), period_start=date(2014, 1, 1),
                          period_end=date(2012, 1, 31))
            ub.sha256_hexdigest = 'ab5c23a2b20284db26ae474c1d633dd9a3d76340036ab69097cf3274cf50a937'
            s.add(ub)
        s.flush()

        key_name = self.bu._get_key_name(ub)

        utilbill = Mock(autospec=UtilBill)
        self.bu.upload_utilbill_pdf_to_s3(utilbill, StringIO('test_file_data'))

        key_obj = self.bu._get_amazon_bucket().get_key(key_name)

        #Ensure we've uploaded the file correctly
        self.assertEqual('test_file_data', key_obj.get_contents_as_string())

        self.bu.delete_utilbill_pdf_from_s3(ub)

        #Ensure the file is *still in S3* even though we have called delete
        self.assertEqual('test_file_data', key_obj.get_contents_as_string())

    def test_upload_utilbill_pdf_to_s3(self):
        fb_utility = Utility('some_utility', Address())
        s = Session()
        ub = UtilBill(Customer('', 'test', 0.0, 0.0, '',
                               fb_utility, 'rate_class', Address(), Address()),
                      0, 'gas', fb_utility, 'test_rate_class', Address(),
                      Address(), period_start=date(2014, 1, 1),
                      period_end=date(2012, 1, 31))
        ub.sha256_hexdigest = '000000f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b'
        s.add(ub)
        s.flush()


        self.bu.upload_utilbill_pdf_to_s3(ub, StringIO('test_file_upload'))
        key_name = self.bu._get_key_name(ub)
        key_obj = self.bu._get_amazon_bucket().get_key(key_name)
        self.assertEqual('test_file_upload', key_obj.get_contents_as_string())

    def test_get_reebill_file_path(self):
        self.assertEqual(self.bu.get_reebill_file_path('tst_acct', 4),
            '/tmp/test/db-test/skyline/bills/tst_acct/tst_acct_0004.pdf')


if __name__ == '__main__':
    unittest.main()
