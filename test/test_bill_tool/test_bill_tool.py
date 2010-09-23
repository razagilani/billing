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
        prevBill = os.path.join("test", "test_bill_tool", "roll_bill_1_pre.xml")
        nextBill = os.path.join("test", "test_bill_tool", "roll_bill_1_in.xml")
        correctBill = os.path.join("test", "test_bill_tool", "roll_bill_1_post.xml")

        BillTool().roll_bill(prevBill, nextBill, 19.99)

        etree_in = etree.parse(nextBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "Bill roll failed because " + nextBill + " does not match " + correctBill)
        
        os.remove(nextBill)

    def test_hypothetical_charge_summation(self):
        """ For all of the hypothetical charges in <ub:details/>, test that they properly roll up into """
        """ <ub:utilbill/> and <ub:rebill/>"""

        unprocessedBill = os.path.join("test", "test_bill_tool", "hypo_charge_summation_1_pre.xml")
        resultantBill = os.path.join("test", "test_bill_tool", "hypo_charge_summation_1_in.xml")
        correctBill = os.path.join("test", "test_bill_tool", "hypo_charge_summation_1_post.xml")

        BillTool().sum_hypothetical_charges(unprocessedBill, resultantBill)

        etree_in = etree.parse(resultantBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "Hypothetical charges did not totalize properly because " + 
            resultantBill + " does not match " + correctBill + "\n" + reason)

        os.remove(resultantBill)

    def test_actual_charge_summation(self):
        """ For all of the actual charges in <ub:details/>, test that they properly roll up into """
        """ <ub:utilbill/> and <ub:rebill/>"""

        unprocessedBill = os.path.join("test", "test_bill_tool", "actual_charge_summation_1_pre.xml")
        resultantBill = os.path.join("test", "test_bill_tool", "actual_charge_summation_1_in.xml")
        correctBill = os.path.join("test", "test_bill_tool", "actual_charge_summation_1_post.xml")

        BillTool().sum_actual_charges(unprocessedBill, resultantBill)

        etree_in = etree.parse(resultantBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "Actual charges did not totalize properly because " + 
            resultantBill + " does not match " + correctBill + "\n" + reason)

        os.remove(resultantBill)

    # test the computation of value, savings and charges for renewable energy
    def test_compute_re(self):
        """ for all utilbills, the revalue, charges and savings need to be calculated.  Then they must be """
        """ summed up for the same elements in rebill """

        unprocessedBill = os.path.join("test", "test_bill_tool", "rebill_summation_1_pre.xml")
        resultantBill = os.path.join("test", "test_bill_tool", "rebill_summation_1_in.xml")
        correctBill = os.path.join("test", "test_bill_tool", "rebill_summation_1_post.xml")
        
        BillTool().compute_re(unprocessedBill, resultantBill, 0.15)

        etree_in = etree.parse(resultantBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "Dollar amounts did not sum up correctly " + 
            resultantBill + " does not match " + correctBill + "\n" + reason)

        os.remove(resultantBill)


    # test the totalization of the rebill section
    def test_totalize(self):
        """ for the rebill's total adjustment, balanceforward, recharges and currentcharges """ 
        """ check the total due computes properly. """

        unprocessedBill = os.path.join("test", "test_bill_tool", "totalize_1_pre.xml")
        resultantBill = os.path.join("test", "test_bill_tool", "totalize_1_in.xml")
        correctBill = os.path.join("test", "test_bill_tool", "totalize_1_post.xml")


        BillTool().totalize(unprocessedBill, resultantBill)

        etree_in = etree.parse(resultantBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "totaldue did not sum up correctly " + 
            resultantBill + " does not match " + correctBill + "\n" + reason)

        os.remove(resultantBill)


if __name__ == '__main__':
    unittest.main()
