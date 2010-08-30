#!/usr/bin/python
"""
File: bill_tool.py
Description: Various utility procedures to process bills
Usage: See command line synopsis
"""

#
# runtime support
#
import sys
import os  
from optparse import OptionParser

# for xml processing
from lxml import etree

from skyliner.xml_utils import XMLUtils

# for testing
#import StringIO

class BillTool():
    """ Class with a variety of utility procedures for processing bills """
    
    def __init__(self):
        pass

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    def get_elem(self, tree, xpath):
        return tree.xpath(xpath, namespaces={"ub":"bill"})

    def sum_utilbill_rebill(self, unprocessedBill, targetBill, discount_rate = None, user=None, password=None):

        tree = etree.parse(unprocessedBill)

        # obtain all of the utilbill groves 
        utilbills = self.get_elem(tree, "/ub:bill/ub:utilbill")
        for utilbill in utilbills:

            # determine the difference between the hypothetical and actual energy charges to determine revalue
            self.get_elem(utilbill, "ub:revalue")[0].text = \
            str(self.get_elem(utilbill, "ub:hypotheticalecharges - ub:actualecharges"))

            self.get_elem(utilbill, "ub:recharges")[0].text = \
            str(float(self.get_elem(utilbill, "ub:revalue")[0].text) * (1.0 - discount_rate))

            self.get_elem(utilbill, "ub:resavings")[0].text = \
            str(float(self.get_elem(utilbill, "ub:revalue")[0].text) * discount_rate)

        # write bill back out
        xml = etree.tostring(tree, pretty_print=True)
        XMLUtils().save_xml_file(xml, targetBill, user, password)

    def sum_hypothetical_charges(self, unprocessedBill, targetBill, user=None, password=None):
        """ Sums up all hypothetical charges.  For each set of hypothetical charges, """
        """ /ub:bill/ub:details/ub:chargegroup/ub:charges[@type="hypothetical"]/ub:total = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="hypothetical"]/ub:charge/ub:total """
        """ For each set of services, /ub:bill/ub:details/ub:total[@type="hypothetical"] = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="hypothetical"]/ub:total) """
        """ Each /ub:bill/ub:utilbill/ub:hypotheticalecharges = /ub:bill/ub:details/ub:total """
        """ /ub:bill/ub:rebill/ub:hypotheticalecharges = sum(/ub:bill/ub:utilbill/ub:hypotheticalecharges) """

        tree = etree.parse(unprocessedBill)


        # get the child groves for each set of hypothetical charges and total them up
        all_hypothetical_charges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type=\"hypothetical\"]")
        for hypothetical_charges in all_hypothetical_charges:
            # and set the subtotal for for each hypothetical set of charges
            self.get_elem(hypothetical_charges, "ub:total")[0].text = \
            "{0:.2f}".format(self.get_elem(hypothetical_charges, "sum(ub:charge/ub:total)"))

        # for each utility details, sum up the hypothetical charges totals 
        details = self.get_elem(tree, "/ub:bill/ub:details")
        for detail in details:
            total = "{0:.2f}".format(self.get_elem(detail, "sum(ub:chargegroup/ub:charges[@type=\"hypothetical\"]/ub:total)"))
            self.get_elem(detail, "ub:total[@type=\"hypothetical\"]")[0].text = total 
            # now that the utility details are totalized, hypothetical values are put into the utilibill summary
            service_type = detail.attrib["service"]
            self.get_elem(tree, "/ub:bill/ub:utilbill[@service=\""+service_type+"\"]/ub:hypotheticalecharges")[0].text = total
        
        # finally, these hypothetical energy charges get rolled up into rebill

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:hypotheticalecharges")[0].text = \
        "{0:.2f}".format(self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:hypotheticalecharges)"))

        xml = etree.tostring(tree, pretty_print=True)

        XMLUtils().save_xml_file(xml, targetBill, user, password)

    def sum_actual_charges(self, unprocessedBill, targetBill, user=None, password=None):
        """ Sums up all actual charges.  For each set of actual charges, """
        """ /ub:bill/ub:details/ub:chargegroup/ub:charges[@type="actual"]/ub:total = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="actual"]/ub:charge/ub:total """
        """ For each set of services, /ub:bill/ub:details/ub:total[@type="actual"] = """
        """ sum(/ub:bill/ub:details/ub:chargegroup/ub:charges[@type="actual"]/ub:total) """
        """ Each /ub:bill/ub:utilbill/ub:actualecharges = /ub:bill/ub:details/ub:total """
        """ /ub:bill/ub:rebill/ub:actualecharges = sum(/ub:bill/ub:utilbill/ub:actualecharges) """

        tree = etree.parse(unprocessedBill)


        # get the child groves for each set of actual charges and total them up
        all_actual_charges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type=\"actual\"]")
        for actual_charges in all_actual_charges:
            # and set the subtotal for for each actual set of charges
            self.get_elem(actual_charges, "ub:total")[0].text = \
            "{0:.2f}".format(self.get_elem(actual_charges, "sum(ub:charge/ub:total)"))

        # for each utility details, sum up the actual charges totals 
        details = self.get_elem(tree, "/ub:bill/ub:details")
        for detail in details:
            total = "{0:.2f}".format(self.get_elem(detail, "sum(ub:chargegroup/ub:charges[@type=\"actual\"]/ub:total)"))
            self.get_elem(detail, "ub:total[@type=\"actual\"]")[0].text = total 
            # now that the utility details are totalized, actual values are put into the utilibill summary
            service_type = detail.attrib["service"]
            self.get_elem(tree, "/ub:bill/ub:utilbill[@service=\""+service_type+"\"]/ub:actualecharges")[0].text = total
        
        # finally, these actual energy charges get rolled up into rebill

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:actualecharges")[0].text = \
        "{0:.2f}".format(self.get_elem(tree, "sum(/ub:bill/ub:utilbill/ub:actualecharges)"))

        xml = etree.tostring(tree, pretty_print=True)

        XMLUtils().save_xml_file(xml, targetBill, user, password)



    def roll_bill(self, inputbill, outputbill, amountPaid, user=None, password=None):


        # Bind to XML bill
        tree = etree.parse(inputbill)
        #print etree.tostring(tree, pretty_print=True)

        # increment bill id
        bill = self.get_elem(tree, "/ub:bill")[0]
        newId = int(bill.get("id"))
        bill.set("id", str(newId+1))

        # process /ub:bill/ub:rebill

        self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaladjustment")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:hypotheticalecharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:actualecharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:revalue")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:recharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:resavings")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:currentcharges")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:duedate")[0].clear()
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:issued")[0].clear()

        message = self.get_elem(tree, "/ub:bill/ub:rebill/ub:message")
        if(len(message)):
            message[0].clear()

        # next period begin is prev period end
        # ToDo business logic specific dates are selected here
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = \
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodend")[0].text
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodend")[0].clear()

        # compute payments 
        # TODO if ub:totalDue element does not exist, or has no value, raise exception
        totalDue = self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:priorbalance")[0].text = totalDue
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:paymentreceived")[0].text = str(amountPaid)
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:balanceforward")[0].text = "{0:.2f}".format(float(totalDue) - float(amountPaid))


        # process /ub:bill/ub:utilbill
        utilbills = self.get_elem(tree, "/ub:bill/ub:utilbill")

        # process each utility service and clear values
        for utilbill in utilbills:
            # utility billing periods are utility specific
            # ToDo business logic specific dates are selected here
            self.get_elem(utilbill, "ub:billperiodbegin")[0].text = self.get_elem(utilbill, "ub:billperiodend")[0].text
            self.get_elem(utilbill, "ub:billperiodend")[0].clear()
            self.get_elem(utilbill, "ub:hypotheticalecharges")[0].text = "0.00"
            self.get_elem(utilbill, "ub:actualecharges")[0].text = "0.00"
            self.get_elem(utilbill, "ub:revalue")[0].text = "0.00"
            self.get_elem(utilbill, "ub:recharges")[0].text = "0.00"
            self.get_elem(utilbill, "ub:resavings")[0].text = "0.00"

        # process /ub:bill/ub:details/

        subtotals = self.get_elem(tree, "/ub:bill/ub:details/ub:total")
        for subtotal in subtotals:
            # set text to "" since we don't want to clobber the element attributes
            subtotal.text = "0.00"


        # remove cdata but preserve unit attributes (.clear() clears attrs) -  last period actual charge values 
        actualCharges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type='actual']")
        for actualCharge in actualCharges:
            quantities = self.get_elem(actualCharge, "ub:charge/ub:quantity")
            for quantity in quantities:
                quantity.text = ""
            rates = self.get_elem(actualCharge, "ub:charge/ub:rate")
            for rate in rates:
                rate.text = ""
            totals = self.get_elem(actualCharge, "ub:charge/ub:total")
            for total in totals: 
                total.text = "0.00"
            # clear chargegroup totals
            totals = self.get_elem(actualCharge, "ub:total")
            for total in totals:
                total.text = "0.00"

        # remove the hypothetical charges since they will be recreated from the actual charges
        hypotheticalCharges = self.get_elem(tree, "/ub:bill/ub:details/ub:chargegroup/ub:charges[@type='hypothetical']")

        for hypotheticalCharge in hypotheticalCharges:
            hypotheticalCharge.getparent().remove(hypotheticalCharge)


        # reset measured usage

        # set meter read date
        # ToDo: utility specific behavior
        meters = self.get_elem(tree, "/ub:bill/ub:measuredusage/ub:meter")

        for meter in meters:
            self.get_elem(meter, "ub:priorreaddate")[0].text = self.get_elem(meter, "ub:presentreaddate")[0].text
            self.get_elem(meter, "ub:presentreaddate")[0].clear()

        registerTotals = self.get_elem(tree, "/ub:bill/ub:measuredusage/ub:meter/ub:register/ub:total")
        for registerTotal in registerTotals:
            registerTotal.text = "0"

        
        xml = etree.tostring(tree, pretty_print=True)

        XMLUtils().save_xml_file(xml, outputbill, user, password)


def main(options):
    """
    """
    pass

if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-i", "--inputbill", dest="inputbill", help="Previous bill to acted on", metavar="FILE")
    parser.add_option("-o", "--outputbill", dest="outputbill", help="Next bill to be targeted", metavar="FILE")
    parser.add_option("-a", "--amountpaid", dest="amountpaid", help="Amount paid on previous bill")
    parser.add_option("-u", "--user", dest="user", default='prod', help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password", help="Bill database user account name.")
    parser.add_option("--roll", dest="roll", action="store_true", help="Roll the bill to the next period.")
    parser.add_option("--sumhypothetical", action="store_true", dest="sumhypothetical", help="Summarize hypothetical charges.")
    parser.add_option("--sumactual", action="store_true", dest="sumactual", help="Summarize actual charges.")

    (options, args) = parser.parse_args()

    if (options.inputbill == None):
        print "Input bill must be specified."
        exit()

    if (options.outputbill == None):
        print "Output bill must be specified"
        exit()

    if (options.roll == None and options.sumhypothetical == None and options.sumactual == None):
        print "Specify operation"

    if (options.roll):
        if (options.amountpaid == None):
            print "Specify --amountpaid"
        else:
            BillTool().roll_bill(options.inputbill, options.outputbill, options.amountpaid, options.user, options.password)

    if (options.sumhypothetical):
            BillTool().sum_hypothetical_charges(options.inputbill, options.outputbill, options.user, options.password)

    if (options.sumactual):
            BillTool().sum_actual_charges(options.inputbill, options.outputbill, options.user, options.password)
