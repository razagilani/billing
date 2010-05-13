#!/usr/bin/python
"""unit tests for fetch_bill_data"""

import unittest
import minimock
from datetime import date


# test target
from skyliner import fetch_bill_data as fbd


class TestFetchBillData(unittest.TestCase):

    def setUp(self):
        # do setup here is necessary
        pass


    def testDateGenerator(self):
        i = 0
        for aDate in fbd.dateGenerator(date(2000, 01, 01), date(2000, 12, 31)):
            i = i + 1
        # 2000 is a leap year
        self.assertEqual(i, 366) 

    def testUsageDataToVirtualRegisters(self):
        results = fbd.usageDataToVirtualRegister(None, "daves", "test/test_fetch_bill_data/RegTest.xml", None, None, False)    

        
    def testTwo(self):
        pass

if __name__ == '__main__':
    unittest.main()
