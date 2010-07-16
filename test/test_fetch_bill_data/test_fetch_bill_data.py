#!/usr/bin/python
"""unit tests for fetch_bill_data"""

import unittest
import minimock
from skyliner import splinter
from datetime import date, datetime
from amara import bindery
from IPython.Debugger import Tracer; debug_here = Tracer()
import os


# test target
from skyliner import fetch_bill_data as fbd


def getRegister(rregisters, identifier):
    return [reg for reg in rregisters if reg.identifier == identifier]

class TestFetchBillData(unittest.TestCase):

    def setUp(self):
        # do setup here as necessary
        minimock.mock('splinter.Splinter', mock_obj=SplinterMock)
        pass


    def testDateGenerator(self):
        i = 0
        for aDate in fbd.dateGenerator(date(2000, 01, 01), date(2000, 12, 31)):
            i = i + 1
        # 2000 is a leap year
        self.assertEqual(i, 366) 

    def testUsageDataToVirtualRegisters1(self):
        dom = bindery.parse("test/test_fetch_bill_data/bill_reg_test_1_pre.xml")

        # test the weekend
        results = fbd.usageDataToVirtualRegister(
                "fictitious install", 
                dom, 
                "http://no.whe.re", 
                datetime(2010, 5, 1), 
                datetime(2010, 5, 2), 
                True
            )
        # save intermediate results
        open("test/test_fetch_bill_data/bill_reg_test_1_in.xml", 'w').write(results.xml_encode())

        self.assertEquals(open("test/test_fetch_bill_data/bill_reg_test_1_in.xml", "rU").read(), 
            open("test/test_fetch_bill_data/bill_reg_test_1_post.xml", "rU").read(), "Virtual registers did not populate as expected.")

        # clean up intermediate results
        os.remove("test/test_fetch_bill_data/bill_reg_test_1_in.xml")
        
        #for register in results.xml_select(u'//ub:register[@shadow=\'true\']/ub:identifier | //ub:register[@shadow=\'true\']/ub:total'):
            #register.xml_write()

    def testUsageDataToVirtualRegisters2(self):
        dom = bindery.parse("test/test_fetch_bill_data/bill_reg_test_2_pre.xml")

        # Test a Monday with peak/int/shoulder TOU in electric
        results = fbd.usageDataToVirtualRegister(
                "fictitious install", 
                dom, 
                "http://no.whe.re", 
                datetime(2010, 5, 3), 
                datetime(2010, 5, 3), 
                True
            )
        # save intermediate results for debugging
        open("test/test_fetch_bill_data/bill_reg_test_2_in.xml", 'w').write(results.xml_encode())
        self.assertEquals(open("test/test_fetch_bill_data/bill_reg_test_2_in.xml", "rU").read(),
            open("test/test_fetch_bill_data/bill_reg_test_2_post.xml", "rU").read(), "Virtual registers did not populate as expected.")

        # clean up intermediate results
        os.remove("test/test_fetch_bill_data/bill_reg_test_2_in.xml")


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
            

class SplinterMock():
    """Mock object for Splinter only doesn't do much"""
    def __init__(self, server_root):
        """Thanks for the server root, not gonna do anything with it"""

    def get_install_obj_for(self, install_name):
        """Thanks for the name, here is another mock"""
        return SkyInstallMock()

class SkyInstallMock():
    """Mock object to cover a single call to a SkyInstall"""
    def get_energy_consumed_by_service(self, 
                                       day, 
                                       service_type,
                                       hour_range=(0, 24)):
        """Return a verifiable amount of energy in BTUs: 100K BTU's per hour"""
        x = 0
        for hour in range(hour_range[0], hour_range[1]):
            x = x + 100000
        return x


if __name__ == '__main__':
    unittest.main()
