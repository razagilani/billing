#!/usr/bin/python
"""unit tests for fetch_bill_data"""

import unittest
import minimock
from datetime import date
from amara import bindery


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

    def testUsageDataToVirtualRegisters2(self):
        dom = bindery.parse("test/test_fetch_bill_data/TestBill.xml")
        results = fbd.usageDataToVirtualRegister("daves", dom, "test/test_fetch_bill_data/RegTest.xml", date(2010, 3 , 1), date(2010, 3, 5), True)
        # ToDo: Mock energy data access and Test results
        results.xml_write()
        self.assertEqual(1,2)

    def testUsageDataToVirtualRegisters1(self):
        dom = bindery.parse("test/test_fetch_bill_data/TestBill.xml")
        results = fbd.usageDataToVirtualRegister("daves", dom, "test/test_fetch_bill_data/RegTest.xml", None, None, True)
        # ToDo: Mock energy data access and Test results
        results.xml_write()
        self.assertEqual(1,2)

if __name__ == '__main__':
    unittest.main()
