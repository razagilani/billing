#!/usr/bin/python
import sys
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

    def setUp(self):
        print 'setUp'

        config_file = StringIO('''
[billimages]
bill_image_directory = /tmp/test/billimages
show_reebill_images = true
[billdb]
billpath = /tmp/test/db-test/skyline/bills/
database = skyline
utilitybillpath = /tmp/test/db-test/skyline/utilitybills/
collection = reebills
host = localhost
port = 27017
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

    def tearDown(self):
        # remove test directory
        shutil.rmtree('/tmp/test')

    def test_move_utilbill_file(self):
        account = '99999'
        start, end = date(2012,1,1), date(2012,2,1)
        new_start, new_end = date(2012,1,2), date(2012,2,2)
        path = self.billupload.get_utilbill_file_path(account, start, end,
                extension='pdf')
        new_path = self.billupload.get_utilbill_file_path(account, new_start,
                new_end, extension='pdf')

        # neither old path nor new path should exist yet
        assert not any([os.access(path, os.F_OK), os.access(new_path, os.F_OK)])

        # create parent directories of bill file, then create bill file itself
        # with some text in it
        os.makedirs(os.path.split(path)[0])
        with open(path, 'w') as bill_file:
            bill_file.write('this is a test')

        # move the file
        self.billupload.move_utilbill_file(account, start, end, new_start,
                new_end)

        # new file should exist and be readable and old should not
        self.assertTrue(os.access(new_path, os.R_OK))
        self.assertFalse(os.access(path, os.F_OK))

        # new file should also be findable with extension and without
        self.assertEqual(new_path,
                self.billupload.get_utilbill_file_path(account, new_start,
                new_end))
        self.assertEqual(new_path,
                self.billupload.get_utilbill_file_path(account, new_start,
                new_end, extension='pdf'))

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
