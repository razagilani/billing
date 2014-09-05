#!/usr/bin/python
from billing import init_config
init_config('tstsettings.cfg')
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
        self.billupload = BillUpload()

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



if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
