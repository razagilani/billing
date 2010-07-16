#!/usr/bin/python
"""unit tests for bill_tool.py"""

import unittest
import minimock
from skyliner import splinter
from datetime import date, datetime
from amara import bindery
from IPython.Debugger import Tracer; debug_here = Tracer()
import os


# test target
from billing.processing.bill_tool import BillTool


class TestBillTool(unittest.TestCase):

    def setUp(self):
        # do setup here as necessary
        pass

    def test_roll_bill_1(self):
        """ Test rolling a previous bill into the next bill"""
        prevBill = "test/test_bill_tool/roll_bill_1_pre.xml"
        nextBill = "test/test_bill_tool/roll_bill_1_in.xml"
        correctBill = "test/test_bill_tool/roll_bill_1_post.xml"

        tool = BillTool() 
        tool.roll_bill(prevBill, nextBill, 19.99)

        self.assertEquals(open(nextBill, "r").read(), open(correctBill, "r").read(), "Bill roll failed because bill roll logic is not implemented!")
        

        os.remove(newBill)

if __name__ == '__main__':
    unittest.main()
