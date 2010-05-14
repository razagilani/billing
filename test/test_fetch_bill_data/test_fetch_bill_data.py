#!/usr/bin/python
"""unit tests for fetch_bill_data"""

import unittest
import minimock
from datetime import date
from amara import bindery


# test target
from skyliner import fetch_bill_data as fbd


def getRegister(rregisters, identifier):
    return [reg for reg in rregisters if reg.identifier == identifier]

class TestFetchBillData(unittest.TestCase):

    def setUp(self):
        # do setup here as necessary
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

    def testBindRegister(self):
        dom = bindery.parse("test/test_fetch_bill_data/RegTest.xml")
        registers = fbd.bindRegisters(dom)
        # parse only the shadow registers
        self.assertEqual(5, len(registers), "Expected five shadow registers")

        # for each register, make sure they have the right inclusion/exclusions

        register = getRegister(registers, "T37110")
        # only one register with this identifier should exist
        self.assertEqual(1, len(register), "Duplicate or missing register")
        register = register[0]
        # 24/7 register
        for aDate in fbd.dateGenerator(date(2009, 12, 27), date(2010,1, 4)):
            self.assertEqual([(0,23)],register.validHours(aDate))
        
        register = getRegister(registers, "D11")
        # only one register with this identifier should exist
        self.assertEqual(1, len(register), "Duplicate or missing register")
        register = register[0]
        # D11 is an off peak register running all day on weekends and from 12 to 8 on weekdays
        for aDate in fbd.dateGenerator(date(2010, 11, 21), date(2010, 11, 26)):
            # surprise, holiday!
            if (aDate == date(2010,11,25)):
                self.assertEqual([(0,23)], register.validHours(aDate))
                continue
            if (aDate == date(2010,11,21)):
                self.assertEqual([(0,23)], register.validHours(aDate))
                continue
            self.assertEqual([(0,7)],register.validHours(aDate))

        # D08 is an intermediate register never running on weekends and running twice a day from 8 to 12 noon and 8 to 12 midnight
        register = getRegister(registers, "D08")
        self.assertEqual(1, len(register), "Duplicate or missing register")
        register = register[0]
        for aDate in fbd.dateGenerator(date(2010, 11, 20), date(2011, 1, 2)):
            # weekends - intermediate registers are not in effect
            if (aDate == date(2010, 11, 20) or aDate == date(2010, 11, 21) 
                or aDate == date(2010, 11, 27) or aDate == date(2010, 11, 28)
                or aDate == date(2010, 12, 4) or aDate == date(2010, 12, 5)
                or aDate == date(2010, 12, 11) or aDate == date(2010, 12, 12)
                or aDate == date(2010, 12, 18) or aDate == date(2010, 12, 19)
                or aDate == date(2010, 12, 25) or aDate == date(2010, 12, 26)
                or aDate == date(2011, 1, 2)
                ):
                self.assertEqual([], register.validHours(aDate))
                continue
            # holidays - intermediate registers are not in effect
            if (aDate == date(2010, 11, 25) or aDate == date(2010, 12, 25) or aDate == date(2011, 1, 1)):
                self.assertEqual([], register.validHours(aDate))
                continue
                
            # otherwise this register accumulates twice a day
            self.assertEqual([(8, 11),(20,23)], register.validHours(aDate))
            



if __name__ == '__main__':
    unittest.main()
