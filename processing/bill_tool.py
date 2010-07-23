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

from urlparse import urlparse

# for xml processing
from lxml import etree


# for testing
import StringIO

class BillTool():
    """ Class with a variety of utility procedures for processing bills """
    
    def __init__(self):
        pass

    def get_elem(self, tree, xpath):
        return tree.xpath(xpath, namespaces={"ub":"bill"})

    def roll_bill(self, prevbill, nextbill, amountPaid, user=None, password=None):

        # Bind to XML bill
        tree = etree.parse(prevbill)
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
            message.clear()

        # next period begin is prev period end
        # ToDo business logic specific dates are selected here
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = \
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodend")[0].text
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:billperiodend")[0].clear()

        # compute payments 
        totalDue = self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:totaldue")[0].text = "0.00"
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:priorbalance")[0].text = totalDue
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:paymentreceived")[0].text = str(amountPaid)
        self.get_elem(tree, "/ub:bill/ub:rebill/ub:balanceforward")[0].text = str(float(totalDue) - amountPaid)


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
        print meters
        for meter in meters:
            self.get_elem(meter, "ub:priorreaddate")[0].text = self.get_elem(meter, "ub:presentreaddate")[0].text
            self.get_elem(meter, "ub:presentreaddate")[0].clear()

        registerTotals = self.get_elem(tree, "/ub:bill/ub:measuredusage/ub:meter/ub:register/ub:total")
        for registerTotal in registerTotals:
            registerTotal.text = "0"

        #print etree.tostring(tree, pretty_print=True)

        
        # roll the bill

        # determine URI scheme
        parts = urlparse(nextbill)

        xml = etree.tostring(tree, pretty_print=True)

        # nice then to factor out and put into a common lib
        if (parts.scheme == 'http'): 
            # http scheme URL, PUT to eXistDB

            con = httplib.HTTP(parts.netloc)
            con.putrequest('PUT', '%s' % nextbill)
            con.putheader('Content-Type', 'text/xml')

            if (user and password):
                auth = 'Basic ' + string.strip(base64.encodestring(user + ':' + password))
                con.putheader('Authorization', auth )

            clen = len(xml) 
            con.putheader('Content-Length', `clen`)
            con.endheaders() 
            con.send(xml)
        else:
            # if not http specifier, assume just a plain filename was passed in.
            billFile = open(nextbill, "w")
            billFile.write(xml)
            billFile.close()

def main(options):
    """
    """
    pass

if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-p", "--prevbill", dest="prevbill", help="Previous bill to be rolled", metavar="FILE")
    parser.add_option("-n", "--nextbill", dest="nextbill", help="Next bill to be targeted", metavar="FILE")
    parser.add_option("-u", "--user", dest="user", default='prod', help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password", help="Bill database user account name.")

    (options, args) = parser.parse_args()

    if (options.prevbill == None):
        print "Previous bill must be specified."
        exit()

    if (options.nextbill == None):
        print "Next bill must be specified"
        exit()

    roll_bill(options.prevbill, options.nextbill, options.amountpaid, options.user, options.password,)
