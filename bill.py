#!/usr/bin/python
"""
File: bill.py
Description: Represent pythonically, the bill XML instance
Usage: See command line synopsis
"""
#
# runtime support
#
import sys
import os  
from optparse import OptionParser

from datetime import datetime

# for xml processing
#from lxml import etree
import lxml
import copy

from skyliner.xml_utils import XMLUtils

import json

# used for processing fixed point monetary decimal numbers
from decimal import *



class Bill(object):
   
    def __init__(self, billref):
        super(Bill,self).__init__()
        self.inputtree = lxml.etree.parse(billref)

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    #TODO function to return a single element vs list - that will clean up lots of code
    #TODO refactor to external utility class

    def xpath(self, xpath):
        """ Returns all of the results from dereferencing the XPath. """
        return self.inputtree.xpath(xpath, namespaces={"ub":"bill",})

    def get_account(self):
        return self.xpath("/ub:bill/@account")[0]

    def get_id(self):
        return self.xpath("/ub:bill/@id")[0]

    def get_total_due(self,rounding=None):
        total_due = self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text
        if rounding is None:
            return Decimal(total_due)
        
        return Decimal(total_due).quantize(Decimal(".00"), rounding)

    def get_due_date(self):
        return datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:duedate")[0].text, "%Y-%m-%d").date()

    def get_issue_date(self):
        return datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:issued")[0].text, "%Y-%m-%d").date()

    def get_service_location(self):
        # convenient bulletproof method that returns the desired type. Errors need not be handled.
        #addressee = self.xpath("string(/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee/text())")
        # another way, figure out which is better for the bigger picture. Errors must be handled.
        addressee = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text
        street = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text
        city = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text
        state = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text
        country = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text
        postalcode = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text
        return {"addressee":addressee, "street":street, "city":city, "state":state, "country":country, "postalcode": postalcode}

    def set_service_location(self, service_location):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text = service_location.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text = service_location.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text = service_location.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text = service_location.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text = service_location.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text = service_location.get("postalcode")

    def get_billing_address(self):
        # convenient bulletproof method that returns the desired type. Errors need not be handled.
        #addressee = self.xpath("string(/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee/text())")
        # another way, figure out which is better for the bigger picture. Errors must be handled.
        addressee = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text
        street = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text
        city = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text
        state = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text
        country = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text
        postalcode = self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text
        return {"addressee":addressee, "street":street, "city":city, "state":state, "country":country, "postalcode": postalcode}

    def set_billing_address(self, billing_address):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text = billing_address.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text = billing_address.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text = billing_address.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text = billing_address.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text = billing_address.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text = billing_address.get("postalcode")

    def get_rebill_periods(self):
        begin = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text, "%Y-%m-%d").date()
        end = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text, "%Y-%m-%d").date()
        return {"begin":begin, "end":end}

    def set_rebill_periods(self, periods):
        self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = periods.get("begin").strftime("%Y-%m-%d")
        self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text = periods.get("end").strftime("%Y-%m-%d")

    def get_utilbill_beginperiods(self):
        periods = []
        for period in self.xpath("/ub:bill/ub:utilbill/ub:billperiodbegin"):
            periods.append(datetime.strptime(period.text, "%Y-%m-%d").date())
        return periods

    def get_utilbill_endperiods(self):
        periods = []
        for period in self.xpath("/ub:bill/ub:utilbill/ub:billperiodend"):
            periods.append(datetime.strptime(period.text, "%Y-%m-%d").date())
        return periods

    def get_statistics(self):
        renewableUtilization = self.xpath("/ub:bill/ub:statistics/ub:renewableutilization")[0].text
        conventionalUtilization = self.xpath("/ub:bill/ub:statistics/ub:conventionalutilization")[0].text
        periodRenewableConsumed = self.xpath("/ub:bill/ub:statistics/ub:renewableconsumed")[0].text
        periodPoundsCO2Offset = self.xpath("/ub:bill/ub:statistics/ub:co2offset")[0].text
        totalDollarSavings = self.xpath("/ub:bill/ub:statistics/ub:totalsavings")[0].text
        totalRenewableEnergyConsumed = self.xpath("/ub:bill/ub:statistics/ub:totalrenewableconsumed")[0].text
        totalCO2Offset = self.xpath("/ub:bill/ub:statistics/ub:totalco2offset")[0].text
        totalTrees = self.xpath("/ub:bill/ub:statistics/ub:totaltrees")[0].text


        periods = []
        for period in (self.xpath("/ub:bill/ub:statistics/ub:consumptiontrend/ub:period")):
            periods.append({"month": str(period.get("month")), "quantity": float(period.get("quantity"))})
            

        # TODO: rounding rules
        return {
            "renewable_utilization": renewableUtilization, 
            "conventional_utilization": conventionalUtilization,
            "period_renewable_consumed": periodRenewableConsumed,
            "period_pounds_co2_offset": periodPoundsCO2Offset,
            "total_dollar_savings": totalDollarSavings,
            "total_renewable_energy_consumed": totalRenewableEnergyConsumed,
            "total_co2_offset": totalCO2Offset,
            "total_trees": totalTrees,
            "consumption_trend": periods,
        }



if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-i", "--inputbill", dest="inputbill", help="Construct with bill", metavar="FILE")

    (options, args) = parser.parse_args()

    if (options.inputbill == None):
        print "Input bill must be specified."
        exit()

    bill = Bill(options.inputbill)
    print bill.get_service_location() 
    bill.set_service_location(bill.get_service_location())
    print bill.get_service_location() 

    print bill.get_rebill_periods()
    bill.set_rebill_periods(bill.get_rebill_periods())
    print bill.get_rebill_periods()

    print bill.get_utilbill_beginperiods()
    print bill.get_utilbill_endperiods()

    print bill.get_total_due(ROUND_UP)

    print bill.get_due_date()

    print bill.get_statistics()


    #XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), outputbill, user, password)
