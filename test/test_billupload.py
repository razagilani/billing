#!/usr/bin/python
import sys
from mock import Mock
import unittest
from StringIO import StringIO
import ConfigParser
import logging
import os
import shutil
import errno
from datetime import date, datetime, timedelta
from billing.processing.billupload import BillUpload

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class BillUploadTest(unittest.TestCase):
    # TODO: this should be a unit test. make it one!

    def setUp(self):
        config_file = StringIO('''
[billimages]
bill_image_directory = /tmp/test/billimages
show_reebill_images = true
[mongodb]
host = localhost
port = 27017
database = skyline
[bill]
billpath = /tmp/test/db-test/skyline/bills/
utilitybillpath = /tmp/test/db-test/skyline/utilitybills/
utility_bill_trash_directory = /tmp/test/db-test/skyline/utilitybills-deleted
collection = reebills
''')
        config = ConfigParser.RawConfigParser()
        config.readfp(config_file)
        self.billupload = BillUpload(config, logging.getLogger('billupload_test'))

        # ensure that test directory exists and is empty
        try:
            shutil.rmtree('/tmp/test')
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
        os.mkdir('/tmp/test')

        self.utilbill = Mock()
        self.utilbill.period_start = date(2012,1,1)
        self.utilbill.period_end = date(2012,2,1)
        self.utilbill.customer.account = '99999'

    def tearDown(self):
        # remove test directory
        shutil.rmtree('/tmp/test')

    def test_delete_utilbill_file(self):
        start, end = date(2012,1,1), date(2012,2,1)
        path = self.billupload.get_utilbill_file_path(self.utilbill,
                                                      extension='.pdf')

        # path should not exist yet, and the trash directory should be empty
        assert not os.access(path, os.F_OK)
        for root, dirs, files in os.walk(self.billupload.utilbill_trash_dir):
            assert (dirs, files) == ([], [])

        # create parent directories of bill file, then create bill file itself
        # with some text in it
        os.makedirs(os.path.split(path)[0])
        with open(path, 'w') as bill_file:
            bill_file.write('this is a test')

        # delete the file, and get the path it was moved to
        new_path = self.billupload.delete_utilbill_file(self.utilbill)

        # now the file should not exist at its original path
        self.assertFalse(os.access(path, os.F_OK))

        # but there should now be one file in the trash path, and its path
        # should be 'new_path'
        self.assertEqual(1,
                len(list(os.walk(self.billupload.utilbill_trash_dir))))
        for root, dirs, files in os.walk(self.billupload.utilbill_trash_dir):
            self.assertEqual([], dirs)
            self.assertEqual(1, len(files))
            self.assertEqual(new_path, os.path.join(root, files[0]))

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
