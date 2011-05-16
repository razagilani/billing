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
from lxml import etree
import lxml
import copy

from skyliner.xml_utils import XMLUtils

import json

# used for processing fixed point monetary decimal numbers
from decimal import *

from collections import namedtuple

from recordtype import recordtype


# TODO: the xpath functions return a special kind of string. Probably want to convert it before returning int
class Bill(object):
    """
    A container for bill data.  Business logic is purposefully externalized.
    """
   

    # TODO: don't construct with billref when this container is capable of providing non-xml data to persist
    def __init__(self, billref):
        super(Bill,self).__init__()
        self.inputtree = lxml.etree.parse(billref)

    def xml(self):
        return lxml.etree.tostring(self.inputtree, pretty_print=True)

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    #TODO function to return a single element vs list - that will clean up lots of code
    #TODO refactor to external utility class

    def xpath(self, xpath):
        """ Returns all of the results from dereferencing the XPath. """
        return self.inputtree.xpath(xpath, namespaces={"ub":"bill",})

    @property
    def account(self):
        return self.xpath("/ub:bill/@account")[0]

    # TODO rename to sequnce
    @property
    def id(self):
        return self.xpath("/ub:bill/@id")[0]

    # TODO rename to sequnce
    @id.setter
    def id(self, id):
        self.xpath("/ub:bill/@id")[0] = id


    @property
    def total_due(self,rounding=None):
        total_due = self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text
        if rounding is None:
            return Decimal(total_due)
        
        return Decimal(total_due).quantize(Decimal(".00"), rounding)

    # TODO convenience method - get due_date from rebill()
    @property
    def due_date(self):
        return datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:duedate")[0].text, "%Y-%m-%d").date()

    # TODO convenience method - get issue_date from rebill()
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
        #addressee = self.xpath("string(/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee/text())")
        # another way, figure out which is better for the bigger picture. Errors must be handled.
        addressee = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee")[0].text
        street = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:street")[0].text
        city = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:city")[0].text
        state = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:state")[0].text
        country = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:country")[0].text
        postalcode = self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:postalcode")[0].text
        return {"addressee":addressee, "street":street, "city":city, "state":state, "country":country, "postalcode": postalcode}

    @billing_address.setter
    def billing_address(self, billing_address):
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee")[0].text = billing_address.get("addressee")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:street")[0].text = billing_address.get("street")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:city")[0].text = billing_address.get("city")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:state")[0].text = billing_address.get("state")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:country")[0].text = billing_address.get("country")
        self.xpath("/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:postalcode")[0].text = billing_address.get("postalcode")

    # convenience method
    # TODO acquire these periods from the function rebill() vs access the xml here
    @property
    def rebill_periods(self):
        begin = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text, "%Y-%m-%d").date()
        end = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text, "%Y-%m-%d").date()
        return {"begin":begin, "end":end}

    @rebill_periods.setter
    # TODO acquire these periods from the function rebill() vs access the xml here
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

    # TODO convert to namedtuple
    @property
    def utilbill_summary_charges(self):
        """
        Returns a dictionary keyed by service whose values are a dictionary containing the keys 'hypotheticalecharges', 
        'actualecharges', 'revalue', 'recharges', 'resavings'
        """
        utilbill_summary_charges = {}
        for service in self.xpath("/ub:bill/ub:utilbill/@service" ):
            begin = datetime.strptime(self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:billperiodbegin" % service)[0].text, "%Y-%m-%d").date()
            end = datetime.strptime(self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:billperiodend" % service)[0].text, "%Y-%m-%d").date()
            hypotheticalecharges = self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:hypotheticalecharges" % service)[0].text
            actualecharges = self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:actualecharges" % service)[0].text
            revalue = self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:revalue" % service)[0].text
            recharges = self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:recharges" % service)[0].text
            resavings = self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:resavings" % service)[0].text

            # TODO optional quantization?
            hypotheticalecharges = Decimal(hypotheticalecharges).quantize(Decimal('.00'))
            actualecharges = Decimal(actualecharges).quantize(Decimal('.00'))
            revalue = Decimal(revalue).quantize(Decimal('.00'))
            recharges = Decimal(recharges).quantize(Decimal('.00'))
            resavings = Decimal(resavings).quantize(Decimal('.00'))

            utilbill_summary_charges[service] = {
                'begin': begin,
                'end': end,
                'hypotheticalecharges':hypotheticalecharges,
                'actualecharges': actualecharges,
                'revalue': revalue,
                'recharges': recharges,
                'resavings': resavings,
            } 

        return utilbill_summary_charges

    # TODO convert to namedtuple
    @utilbill_summary_charges.setter
    def utilbill_summary_charges(self, summary_charges):
        """
        Sets a dictionary keyed by service whose values are a dictionary containing the keys 'hypotheticalecharges', 
        'actualecharges', 'revalue', 'recharges', 'resavings' into the bill xml
        """
        # TODO: create xml elements if missing
        for service, charges in summary_charges.items():
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:billperiodbegin" % service)[0].text = charges['begin'].strftime("%Y-%m-%d") if charges['begin'] is not None else None
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:billperiodend" % service)[0].text = charges['end'].strftime("%Y-%m-%d") if charges['end'] is not None else None
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:hypotheticalecharges" % service)[0].text = str(charges['hypotheticalecharges'])
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:actualecharges" % service)[0].text = str(charges['actualecharges'])
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:revalue" % service)[0].text = str(charges['revalue'])
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:recharges" % service)[0].text = str(charges['recharges'])
            self.xpath("/ub:bill/ub:utilbill[@service='%s']/ub:resavings" % service)[0].text = str(charges['resavings'])


    # convert to recordtype
    @property
    def measured_usage(self):

        measured_usages = {}

        Meter = recordtype("meter", ["identifier", "estimated","priorreaddate", "presentreaddate", "registers"])

        # TODO: track meter effective times here
        # inclusions/exclusions have been flattened from xsd
        Register = recordtype("register", ["rsbinding", "shadow", "type", "identifier", "description", "inclusions","exclusions", "units", "total", "priorreading", "presentreading", "factor"])
        Effective = recordtype("effective", ["description", "times", "weekdays", "holidays"])
        Holiday = recordtype("holiday", ["description", "date"])
        Weekday = recordtype("weekday", ["fromhour", "tohour", "weekday"])

        for service in self.xpath("/ub:bill/ub:measuredusage/@service"):

            measured_usages[service] = []

            for meter in self.xpath("/ub:bill/ub:measuredusage[@service='"+service+"']/ub:meter"):
                
                meter_identifier = meter.find("ub:identifier", namespaces={'ub':'bill'})
                meter_identifier = meter_identifier.text if meter_identifier is not None else None

                estimated = meter.find("ub:estimated", namespaces={'ub':'bill'})
                estimated = estimated.text if estimated is not None else None
                estimated = False if estimated is not None and estimated.lower() == 'false' \
                    else True if estimated is not None and estimated.lower() == 'true' else None

                priorreaddate = meter.find("ub:priorreaddate", namespaces={'ub':'bill'})
                priorreaddate = priorreaddate.text if priorreaddate is not None else None
                priorreaddate = datetime.strptime(priorreaddate, "%Y-%m-%d").date() if priorreaddate is not None else None

                presentreaddate = meter.find("ub:presentreaddate", namespaces={'ub':'bill'})
                presentreaddate = presentreaddate.text if presentreaddate is not None else None
                presentreaddate = datetime.strptime(presentreaddate, "%Y-%m-%d").date() if presentreaddate is not None else None

                meter_record = Meter(meter_identifier, estimated, priorreaddate, presentreaddate, [])

                for register in meter.findall("ub:register", namespaces={'ub':'bill'} ):

                    rsbinding = register.get("rsbinding")
                    shadow = register.get("shadow")
                    regtype = register.get("type")

                    identifier = register.find("ub:identifier", namespaces={'ub':'bill'})
                    identifier = identifier.text if identifier is not None else None

                    description = register.find("ub:description", namespaces={'ub':'bill'})
                    description = description.text if description is not None else None

                    units = register.find("ub:units", namespaces={'ub':'bill'})
                    units = units.text if units is not None else None

                    priorreading = register.find("ub:priorreading", namespaces={'ub':'bill'})
                    priorreading = priorreading.text if priorreading is not None else None

                    presentreading = register.find("ub:presentreading", namespaces={'ub':'bill'})
                    presentreading = presentreading.text if presentreading is not None else None

                    factor = register.find("ub:factor", namespaces={'ub':'bill'})
                    factor = factor.text if factor is not None else None

                    # TODO optional quantize
                    total = register.find("ub:total", namespaces={'ub':'bill'})
                    total = Decimal(total.text).quantize(Decimal(str(.00))) if total is not None else None

                    shadow_register = meter.find("ub:register[@shadow='true'][ub:identifier='"+identifier+"']",namespaces={'ub':'bill'})
                    shadow_total = shadow_register.find("ub:total", namespaces={'ub':'bill'})
                    shadow_total = Decimal(shadow_total.text).quantize(Decimal(str(.00))) if shadow_total is not None else None

                    #recordtype("register", ["rsbinding", "shadow", "type", "identifier", "description", "inclusions","exclusions", "units", "total", "priorreading", "presentreading", "factor"])
                    meter_record.registers.append(Register(rsbinding, shadow, regtype, identifier, description, [], [], units, total, priorreading, presentreading, factor))

                    """
                    measured_usages[service] = {
                        "identifier": identifier,
                        "description": description,
                        "utility_total": total,
                        "shadow_total": shadow_total,
                        "total": total + shadow_total,
                        "units": units
                    }
                    """

                measured_usages[service].append(meter_record)

        return measured_usages


    #STOPPED HERE 
    #@measured_usages.setter


    # TODO rename to rebill, and send entire grove
    @property
    def rebill_summary(self):

        begin = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text, "%Y-%m-%d").date()
        end = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text, "%Y-%m-%d").date()
        priorbalance = self.xpath("/ub:bill/ub:rebill/ub:priorbalance")[0].text
        paymentreceived = self.xpath("/ub:bill/ub:rebill/ub:paymentreceived")[0].text
        totaladjustment = self.xpath("/ub:bill/ub:rebill/ub:totaladjustment")[0].text
        balanceforward = self.xpath("/ub:bill/ub:rebill/ub:balanceforward")[0].text
        hypotheticalecharges = self.xpath("/ub:bill/ub:rebill/ub:hypotheticalecharges")[0].text
        actualecharges = self.xpath("/ub:bill/ub:rebill/ub:actualecharges")[0].text
        revalue = self.xpath("/ub:bill/ub:rebill/ub:revalue")[0].text
        resavings = self.xpath("/ub:bill/ub:rebill/ub:resavings")[0].text
        recharges = self.xpath("/ub:bill/ub:rebill/ub:recharges")[0].text
        totaldue = self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text
        duedate = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:duedate")[0].text, "%Y-%m-%d").date()
        issued = datetime.strptime(self.xpath("/ub:bill/ub:rebill/ub:issued")[0].text, "%Y-%m-%d").date()
        message = self.xpath("/ub:bill/ub:rebill/ub:message")[0].text

        # TODO optional quantization?
        priorbalance = Decimal(priorbalance).quantize(Decimal('.00'))
        paymentreceived = Decimal(paymentreceived).quantize(Decimal('.00'))
        totaladjustment = Decimal(totaladjustment).quantize(Decimal('.00'))
        revalue = Decimal(revalue).quantize(Decimal('.00'))
        recharges = Decimal(recharges).quantize(Decimal('.00'))
        resavings = Decimal(resavings).quantize(Decimal('.00'))
        balanceforward = Decimal(balanceforward).quantize(Decimal('.00'))
        totaldue = Decimal(totaldue).quantize(Decimal('.00'))

        Rebill = recordtype("rebill",
            ['begin', 'end', 'priorbalance', 'paymentreceived', 'totaladjustment', 'balanceforward',
            'hypotheticalecharges', 'actualecharges', 'revalue', 'resavings', 'recharges', 'totaldue', 'duedate', 'issued', 'message']
        )

        return Rebill(begin, end, priorbalance, paymentreceived, totaladjustment, balanceforward, 
            hypotheticalecharges, actualecharges, revalue, resavings, recharges, totaldue, duedate, issued, message)

    @rebill_summary.setter
    def rebill_summary(self, r):

        self.xpath("/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = r.begin.strftime("%Y-%m-%d") if r.begin is not None else None
        self.xpath("/ub:bill/ub:rebill/ub:billperiodend")[0].text = r.end.strftime("%Y-%m-%d") if r.end is not None else None
        self.xpath("/ub:bill/ub:rebill/ub:priorbalance")[0].text = str(r.priorbalance)
        self.xpath("/ub:bill/ub:rebill/ub:paymentreceived")[0].text = str(r.paymentreceived)
        self.xpath("/ub:bill/ub:rebill/ub:totaladjustment")[0].text = str(r.totaladjustment)
        self.xpath("/ub:bill/ub:rebill/ub:balanceforward")[0].text = str(r.balanceforward)
        self.xpath("/ub:bill/ub:rebill/ub:hypotheticalecharges")[0].text = str(r.hypotheticalecharges)
        self.xpath("/ub:bill/ub:rebill/ub:actualecharges")[0].text = str(r.actualecharges)
        self.xpath("/ub:bill/ub:rebill/ub:revalue")[0].text = str(r.revalue)
        self.xpath("/ub:bill/ub:rebill/ub:resavings")[0].text = str(r.resavings)
        self.xpath("/ub:bill/ub:rebill/ub:recharges")[0].text = str(r.recharges)
        self.xpath("/ub:bill/ub:rebill/ub:totaldue")[0].text = str(r.totaldue)
        self.xpath("/ub:bill/ub:rebill/ub:duedate")[0].text = r.duedate.strftime("%Y-%m-%d") if r.duedate is not None else None
        self.xpath("/ub:bill/ub:rebill/ub:issued")[0].text = r.issued.strftime("%Y-%m-%d") if r.issued is not None else None
        self.xpath("/ub:bill/ub:rebill/ub:message")[0].text = r.message

    @property
    def actual_charges(self):
        """
        Return by service, actual charges grouped by chargegroup including chargegroup totals.
        """
        return self.charge_items('actual')

    @actual_charges.setter
    def actual_charges(self, charge_items):
        """
        Set the actual charges into XML
        """
        return self.set_charge_items('actual', charge_items)

    @property
    def hypothetical_charges(self):
        """
        Return by service, hypothetical charges grouped by chargegroup including chargegroup totals.
        """
        return self.charge_items('hypothetical')

    @hypothetical_charges.setter
    def hypothetical_charges(self, charge_items):
        """
        Set the hypothetical charges into XML
        """
        return self.set_charge_items('hypothetical', charge_items)

    def set_charge_items(self, charges_type, charge_items):

        # get each service name, and associated chargegroups
        for service in charge_items:
            # TODO: create the service in XML if it does not exist
            for chargegroup in charge_items[service]['chargegroups']:
                # TODO: create the chargeroup in XML if it does not exist

                # lookup the charge_type (hypothetical or actual) charges in the chargegroup
                charges_elem = self.xpath("/ub:bill/ub:details[@service='%s']/ub:chargegroup[@type='%s']/ub:charges[@type='%s']" % (service, chargegroup, charges_type))[0]

                # remove all charges_type children
                charges_elem.clear()
                # add the attr back since clear clears everything
                charges_elem.set('type', charges_type)

                for charge in charge_items[service]['chargegroups'][chargegroup]['charges']:
                    rsbinding = charge['rsbinding']
                    description = charge['description']
                    rate = charge['rate']
                    rate_units = charge['rate_units']
                    quantity = charge['quantity']
                    quantity_units = charge['quantity_units']
                    total = charge['total']
                    processingnote = charge['processingnote'] if 'processingnote' in charge else None

                    # append new charge to charges
                    charge_elem = charges_elem.makeelement("{bill}charge", rsbinding=rsbinding)
                    charges_elem.append(charge_elem)

                    # append new description to charge
                    description_elem = charge_elem.makeelement("{bill}description")
                    description_elem.text = description
                    charge_elem.append(description_elem)

                    # append new quantity and units to charge
                    quantity_elem = charge_elem.makeelement("{bill}quantity")
                    quantity_elem.text = str(quantity)
                    quantity_elem.set('units', quantity_units)
                    charge_elem.append(quantity_elem)

                    # append new rate units to charge
                    rate_elem = charge_elem.makeelement("{bill}rate")
                    rate_elem.text = str(rate)
                    rate_elem.set('units', rate_units)
                    charge_elem.append(rate_elem)

                    # append new total to charge
                    total_elem = charge_elem.makeelement("{bill}total")
                    total_elem.text = str(total)
                    charge_elem.append(total_elem)

                    # append new processing notes to charge
                    note_elem = charge_elem.makeelement("{bill}processingnote")
                    note_elem.text = processingnote
                    charge_elem.append(note_elem)

                charges_total = charge_items[service]['chargegroups'][chargegroup]['total']

                charges_total_elem = charges_elem.makeelement("{bill}total")
                charges_total_elem.text = str(charges_total)
                charges_elem.append(charges_total_elem)

            grand_total = charge_items[service]['total']

            # TODO and the details total should by dynamically created too
            grand_total_elem = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='%s']" % (service, charges_type))[0]
            grand_total_elem.text = str(grand_total)

    # Should all dollar quantities be treated as Decimal?  Probably, but how will this impact serialization to JSON?
    def charge_items(self, charges_type):
        """
        Return ci_type charge items by service with charges grouped by chargegroup including chargegroup and grand totals.
        """
        charge_items = {} 

        # this is really pedantic, but incrementally building the xpath makes the code much clearer

        # get each type of service present
        for detail_service in self.xpath("/ub:bill/ub:details/@service"):

            # convert lxml object to a string to act as dict key
            detail_service = str(detail_service)
            
            charge_items[detail_service] = {}
            
            grand_total = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='%s']" % (detail_service, charges_type))[0].text

            charge_items[detail_service]['chargegroups'] = {}
            charge_items[detail_service]['total'] = Decimal(grand_total)
            #.quantize(Decimal('.0000'))

            # get chargegroup types for that service
            for cg_type in self.xpath("/ub:bill/ub:details[@service='%s']/ub:chargegroup/@type" % detail_service):

                # convert lxml object to a string to act as dict key
                cg_type = str(cg_type)

                charge_items[detail_service]['chargegroups'][cg_type] = {}

                # get the charges of charges_type from the chargegroup
                for charges in self.xpath("/ub:bill/ub:details[@service='%s']/ub:chargegroup[@type='%s']/ub:charges[@type='%s']" % (detail_service, cg_type, charges_type)):

                    charge_items[detail_service]['chargegroups'][cg_type]['charges'] = []

                    charge_items[detail_service]['chargegroups'][cg_type]['total'] = Decimal(charges.find("ub:total", namespaces={"ub":"bill"}).text)
                    #.quantize(Decimal('.0000'))
                    
                    for charge in charges.findall("ub:charge", namespaces={"ub":"bill"}):

                        rsbinding = charge.get('rsbinding')

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
                            quantity = Decimal(quantity)
                            #.quantize(Decimal('.00'))
                        elif (quantity_units.lower() == 'dollars'):
                            quantity = Decimal(quantity)
                            #.quantize(Decimal('.00'))
                        elif (quantity_units.lower() == 'kwh'):
                            quantity = Decimal(quantity)
                            #.quantize(Decimal('.0'))

                        rate = charge.find("ub:rate", namespaces={'ub':'bill'})
                        rate = rate.text if rate is not None else None
                        
                        # TODO review lxml api for a better method to access attributes
                        rate_units = charge.xpath("ub:rate/@units", namespaces={'ub':'bill'})
                        if (len(rate_units)):
                            rate_units = rate_units[0]
                        else:
                            rate_units = ""

                        total = charge.find("ub:total", namespaces={'ub':'bill'})
                        total = Decimal(total.text) if total is not None else None
                        #.quantize(Decimal('.0000'))

                        processingnote = charge.find("ub:processingnote", namespaces={'ub':'bill'})
                        processingnote = processingnote.text if processingnote is not None else None

                        charge_items[detail_service]['chargegroups'][cg_type]['charges'].append({
                            'rsbinding': rsbinding,
                            'description': description,
                            'quantity': quantity,
                            'quantity_units': quantity_units,
                            'rate': rate,
                            'rate_units': rate_units,
                            'total': total,
                            'processingnote': processingnote
                        })

        return charge_items




    @property
    def hypotheticalecharges(self):
        """
        Return hypothetical energy charge totals on a per service basis
        """
        return self.echarges('hypothetical')


    @property
    def actualecharges(self):
        """
        Return actual energy charge totals on a per service basis
        """
        return self.echarges('actual')


    def echarges(self, charges_type):

        echarges = {}
        for detail_service in self.xpath("/ub:bill/ub:details/@service"):
            echarges[detail_service] = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='%s']" % (detail_service, charges_type))[0].text
            # convert it to decimal
            echarges[detail_service] = Decimal(echarges[detail_service])

        return echarges

    @property
    def hypothetical_details(self):
        """
        Used by render bill.  Does not include chargegroups or chargegroup totals.
        TODO: eliminate this since the consumer of this method can use others for the same data.
        """
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


    #TODO convenience method, depend on hypothetical_charges_details vs access xml directy here
    # or just make consumer depend on the main function instead
    @property
    def hypothetical_totals(self):
        hypothetical_totals = {}
        for service in self.xpath("/ub:bill/ub:details/@service"):
            total = self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='hypothetical']" % service)[0].text
            hypothetical_totals[service] = Decimal(total).quantize(Decimal('.00'))

        return hypothetical_totals

    @hypothetical_totals.setter
    def hypothetical_totals(self, totals):
        for service in totals:
            self.xpath("/ub:bill/ub:details[@service='%s']/ub:total[@type='hypothetical']" % service)[0].text = str(totals[service])


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

    #print bill.account
    #print bill.id

    #print bill.service_address
    #bill.service_address = bill.service_address
    #print bill.service_address 

    #print bill.rebill_periods
    #bill.rebill_periods = bill.rebill_periods
    #print bill.rebill_periods

    #print bill.utilbill_periods
    #utilbill_periods = bill.utilbill_periods
    #print [utilbill_periods[service] for service in utilbill_periods]

    #print bill.due_date

    #print bill.statistics

    #print bill.motd

    #print bill.measured_usage

    #print bill.hypothetical_details

    #print bill.hypothetical_charges

    #r = bill.rebill_summary
    #print r
    #bill.rebill_summary = r
    #print bill.rebill_summary

    #t = bill.hypothetical_totals
    #print t
    #bill.hypothetical_totals = t

    m = bill.measured_usage
    print m






    #XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), outputbill, user, password)
