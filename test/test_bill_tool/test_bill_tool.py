#!/usr/bin/python
"""unit tests for bill_tool.py"""

import unittest
import minimock
from skyliner import splinter
from datetime import date, datetime
from IPython.Debugger import Tracer; debug_here = Tracer()
import os
from lxml import etree
from skyliner.xml_utils import XMLUtils

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

        BillTool().roll_bill(prevBill, nextBill, 19.99)

        etree_in = etree.parse(nextBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "Bill roll failed because " + nextBill + " does not match " + correctBill)
        

        os.remove(nextBill)
        

if __name__ == '__main__':
    unittest.main()
