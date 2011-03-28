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

    @property
    def account(self):
        return self.xpath("/ub:bill/@account")[0]

    @property
    def id(self):
        return self.xpath("/ub:bill/@id")[0]

    @property
    def total_due(self,rounding=None):
        total_due = self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text
        if rounding is None:
            return Decimal(total_due)
        
        return Decimal(total_due).quantize(Decimal(".00"), rounding)

    @property
    def due_date(self):
        return datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:duedate")[0].text, "%Y-%m-%d").date()

    @property
    def issue_date(self):
        return datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:issued")[0].text, "%Y-%m-%d").date()

    @property
    def service_address(self):
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
    
    @service_address.setter
    def service_address(self, service_location):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text = service_location.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text = service_location.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text = service_location.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text = service_location.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text = service_location.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text = service_location.get("postalcode")

    @property
    def billing_address(self):
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

    @billing_address.setter
    def billing_address(self, billing_address):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text = billing_address.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text = billing_address.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text = billing_address.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text = billing_address.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:country")[0].text = billing_address.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text = billing_address.get("postalcode")

    @property
    def rebill_periods(self):
        begin = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text, "%Y-%m-%d").date()
        end = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text, "%Y-%m-%d").date()
        return {"begin":begin, "end":end}

    @rebill_periods.setter
    def rebill_periods(self, periods):
        self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = periods.get("begin").strftime("%Y-%m-%d")
        self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text = periods.get("end").strftime("%Y-%m-%d")

    @property
    def utilbill_periods(self):
        utilbill_periods = {}
        for service in self.xpath("/ub:bill/ub:utilbill/@service" ):
            utilbill_periods[service] = {
                'begin':datetime.strptime(self.xpath("/ub:bill/ub:utilbill[@service='"+service+"']/ub:billperiodbegin")[0].text, "%Y-%m-%d").date(),
                'end':datetime.strptime(self.xpath("/ub:bill/ub:utilbill[@service='"+service+"']/ub:billperiodend")[0].text, "%Y-%m-%d").date()
                }
        return utilbill_periods

    @property
    def utilbill_summary_charges(self):
        utilbill_summary_charges = {}
        for service in self.xpath("/ub:bill/ub:utilbill/@service" ):
            hypotheticalecharges = self.xpath("/ub:bill/ub:utilbill[@service='"+service+"']/ub:hypotheticalecharges")[0].text
            actualecharges = self.xpath("/ub:bill/ub:utilbill[@service='"+service+"']/ub:actualecharges")[0].text
            revalue = self.xpath("/ub:bill/ub:utilbill[@service='"+service+"']/ub:revalue")[0].text
            # TODO optional quantization?
            hypotheticalecharges = Decimal(hypotheticalecharges).quantize(Decimal('.00'))
            actualecharges = Decimal(actualecharges).quantize(Decimal('.00'))
            revalue = Decimal(revalue).quantize(Decimal('.00'))
            utilbill_summary_charges[service] = {'hypotheticalecharges':hypotheticalecharges, 'actualecharges': actualecharges, 'revalue': revalue} 
        return utilbill_summary_charges

    @property
    def measured_usage(self):
        measured_usages = {}

        for service in self.xpath("/ub:bill/ub:measuredusage/@service"):
            for meter in self.xpath("/ub:bill/ub:measuredusage[@service='"+service+"']/ub:meter"):
                for register in meter.findall("ub:register[@shadow='false']", namespaces={'ub':'bill'} ):

                    identifier = register.find("ub:identifier", namespaces={'ub':'bill'})
                    identifier = identifier.text if identifier is not None else None

                    description = register.find("ub:description", namespaces={'ub':'bill'})
                    description = description.text if description is not None else None

                    units = register.find("ub:units", namespaces={'ub':'bill'})
                    units = units.text if units is not None else None

                    # TODO optional quantize
                    total = register.find("ub:total", namespaces={'ub':'bill'})
                    total = Decimal(total.text).quantize(Decimal(str(.00))) if total is not None else None

                    shadow_register = meter.find("ub:register[@shadow='true'][ub:identifier='"+identifier+"']",namespaces={'ub':'bill'})
                    shadow_total = shadow_register.find("ub:total", namespaces={'ub':'bill'})
                    shadow_total = Decimal(shadow_total.text).quantize(Decimal(str(.00))) if shadow_total is not None else None

                    measured_usages[service] = {
                        "identifier": identifier,
                        "description": description,
                        "utility_total": total,
                        "shadow_total": shadow_total,
                        "total": total + shadow_total,
                        "units": units
                    }

        return measured_usages

    @property
    def rebill_summary(self):
        priorbalance = self.xpath("/ub:bill/ub:rebill/ub:priorbalance")[0].text
        paymentreceived = self.xpath("/ub:bill/ub:rebill/ub:paymentreceived")[0].text
        totaladjustment = self.xpath("/ub:bill/ub:rebill/ub:totaladjustment")[0].text
        savings = self.xpath("/ub:bill/ub:rebill/ub:resavings")[0].text
        renewablecharges = self.xpath("/ub:bill/ub:rebill/ub:recharges")[0].text
        balanceforward = self.xpath("/ub:bill/ub:rebill/ub:balanceforward")[0].text
        totaldue = self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text
        # TODO optional quantization?
        priorbalance = Decimal(priorbalance).quantize(Decimal('.00'))
        paymentreceived = Decimal(paymentreceived).quantize(Decimal('.00'))
        totaladjustment = Decimal(totaladjustment).quantize(Decimal('.00'))
        savings = Decimal(savings).quantize(Decimal('.00'))
        renewablecharges = Decimal(renewablecharges).quantize(Decimal('.00'))
        balanceforward = Decimal(balanceforward).quantize(Decimal('.00'))
        totaldue = Decimal(totaldue).quantize(Decimal('.00'))
        return {
            'priorbalance': priorbalance, 
            'paymentreceived': paymentreceived, 
            'totaladjustment':totaladjustment, 
            'savings': savings, 
            'renewablecharges': renewablecharges, 
            'balanceforward': balanceforward, 
            'totaldue':totaldue
        }
        
    @property
    def hypothetical_details(self):
        hypothetical_details = {}
        for service in self.xpath("/ub:bill/ub:details/@service"):
            hypothetical_details[service] = []
            for chargegroup in self.xpath("/ub:bill/ub:details[@service='"+service+"']/ub:chargegroup"):
                for charges in chargegroup.findall("ub:charges[@type='hypothetical']", namespaces={"ub":"bill"}):
                    for charge in charges.findall("ub:charge", namespaces={"ub":"bill"}):
                        
                        description = charge.find("ub:description", namespaces={'ub':'bill'})
                        description = description.text if description is not None else None

                        quantity = charge.find("ub:quantity", namespaces={'ub':'bill'})
                        quantity = quantity.text if quantity is not None else None


                        # TODO review lxml api for a better method to access attributes
                        quantity_units = charge.xpath("ub:quantity/@units", namespaces={'ub':'bill'})
                        if (len(quantity_units)):
                            quantity_units = quantity_units[0]
                        else:
                            quantity_units = ""

                        # TODO helper to quantize based on units
                        # TODO not sure we want to quantize here. think it over.
                        if (quantity_units.lower() == 'therms'):
                            quantity = Decimal(quantity).quantize(Decimal('.00'))
                        elif (quantity_units.lower() == 'dollars'):
                            quantity = Decimal(quantity).quantize(Decimal('.00'))
                        elif (quantity_units.lower() == 'kwh'):
                            quantity = Decimal(quantity).quantize(Decimal('.0'))

                        rate = charge.find("ub:rate", namespaces={'ub':'bill'})
                        rate = rate.text if rate is not None else None
                        
                        # TODO review lxml api for a better method to access attributes
                        rate_units = charge.xpath("ub:rate/@units", namespaces={'ub':'bill'})
                        if (len(rate_units)):
                            rate_units = rate_units[0]
                        else:
                            rate_units = ""

                        total = charge.find("ub:total", namespaces={'ub':'bill'})
                        total = Decimal(total.text).quantize(Decimal('.00')) if total is not None else None

                        hypothetical_details[service].append({
                            'description': description,
                            'quantity': quantity,
                            'quantity_units': quantity_units,
                            'rate': rate,
                            'rate_units': rate_units,
                            'total': total
                        })


        return hypothetical_details


    @property
    def hypothetical_totals(self):
        hypothetical_totals = {}
        for service in self.xpath("/ub:bill/ub:details/@service"):
            total = self.xpath("/ub:bill/ub:details[@service='"+service+"']/ub:total[@type='hypothetical']")[0].text
            hypothetical_totals[service] = total

        return hypothetical_totals


    @property
    def motd(self):
        motd = self.xpath("/ub:bill/ub:rebill/ub:message")[0].text
        if motd is None: motd = ""
        return motd


    @property
    def statistics(self):
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
            periods.append({"month": period.get("month"), "quantity": period.get("quantity")})

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

    print bill.account
    print bill.id

    print bill.service_address
    bill.service_address = bill.service_address
    print bill.service_address 

    print bill.rebill_periods
    bill.rebill_periods = bill.rebill_periods
    print bill.rebill_periods

    print bill.utilbill_periods
    utilbill_periods = bill.utilbill_periods
    print [utilbill_periods[service] for service in utilbill_periods]

    print bill.due_date

    print bill.statistics

    print bill.motd

    print bill.measured_usage

    print bill.hypothetical_details

    print bill.hypothetical_total

    #XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), outputbill, user, password)
