#!/usr/bin/python
"""unit tests for bill_tool.py"""

import unittest
import minimock
import shutil
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
    def test_sumbill(self):
        """ for all utilbills, the revalue, charges and savings need to be calculated.  Then they must be """
        """ summed up for the same elements in rebill """

        unprocessedBill = os.path.join("test", "test_bill_tool", "rebill_summation_1_pre.xml")
        resultantBill = os.path.join("test", "test_bill_tool", "rebill_summation_1_in.xml")
        correctBill = os.path.join("test", "test_bill_tool", "rebill_summation_1_post.xml")
        
        BillTool().sumbill(unprocessedBill, resultantBill, 0.15)

        etree_in = etree.parse(resultantBill)
        etree_post = etree.parse(correctBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "Dollar amounts did not sum up correctly " + 
            resultantBill + " does not match " + correctBill + "\n" + reason)

        os.remove(resultantBill)

    # test the computation of statistics
    def test_calcstats(self):
        """ Verify that the stats from a prior bill calculate right in the context of the next bill.  """

        # the previous bill from which cumulative statistics are calculated
        priorBill = os.path.join("test", "test_bill_tool", "calc_stats_prior.xml")

        # the current bill with the previous bill's statistics section (carried from roll operation)
        unprocessedBill = os.path.join("test", "test_bill_tool", "calc_stats_pre.xml")

        # calculate statistics will update this one
        resultantBill = os.path.join("test", "test_bill_tool", "calc_stats_in.xml")

        # copy to the _in.xml file because calculate_statistics updates an existing file
        # _in.xml files are not versioned
        shutil.copyfile(unprocessedBill, resultantBill)

        # and we expect this one
        correctBill = os.path.join("test", "test_bill_tool", "calc_stats_post.xml")
        


        BillTool().calculate_statistics(priorBill, resultantBill)

        etree_post = etree.parse(correctBill)
        etree_in = etree.parse(resultantBill)

        (result, reason) = XMLUtils().compare_xml(etree_in, etree_post)

        self.assertEquals(result, True, "calculate statistics failed " + 
            resultantBill + " does not match " + correctBill + "\n" + reason)

        os.remove(resultantBill)


if __name__ == '__main__':
    unittest.main()
