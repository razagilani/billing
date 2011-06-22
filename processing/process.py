#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""

#
# runtime support
#
import sys
import os  
from optparse import OptionParser

import datetime

# for xml processing
from lxml import etree
import copy

from billing import bill

from skyliner.xml_utils import XMLUtils

# for testing
#import StringIO

# used for processing fixed point monetary decimal numbers
from decimal import *
from billing import bill

import pprint

class Process(object):
    """ Class with a variety of utility procedures for processing bills """
    
    def __init__(self):
        pass

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    #TODO function to return a single element vs list - that will clean up lots of code
    #TODO refactor to external utility class
    def get_elem(self, tree, xpath):
        return tree.xpath(xpath, namespaces={"ub":"bill"})


    # TODO convert to property access
    # TODO rename to sum_bill
    # compute the value, charges and savings of renewable energy
    def sumbill(self, prior_bill, unprocessedBill, targetBill, discount_rate = None, user=None, password=None):
        # TODO discount_rate should be a decimal so that it doesn't have to be converted below.

        prior_bill = bill.Bill(prior_bill)
        the_bill = bill.Bill(unprocessedBill)

        # get data from the bill
        ub_summary_charges = the_bill.utilbill_summary_charges;
        rebill_summary = the_bill.rebill_summary

        # get the total actual energy charges per service
        actualecharges = the_bill.actualecharges

        # get the total hypothetical energy charges per service
        hypotheticalecharges = the_bill.hypotheticalecharges

        # eventually track total revalue
        rebill_summary['revalue'] = Decimal("0.00")
        rebill_summary['recharges'] = Decimal("0.00")
        rebill_summary['resavings'] = Decimal("0.00")
        rebill_summary['actualecharges'] = Decimal("0.00")
        rebill_summary['hypotheticalecharges'] = Decimal("0.00")

        for (service, charges) in ub_summary_charges.items():
            # grab the charges totals and update the summary rollup of them
            charges['hypotheticalecharges'] = hypotheticalecharges[service]
            charges['actualecharges'] = actualecharges[service]

            charges['revalue'] = charges['hypotheticalecharges'] - charges['actualecharges']
            charges['recharges'] = (charges['revalue'] * Decimal(str(1.0 -float(discount_rate)))).quantize(Decimal('.00'), rounding=ROUND_DOWN)
            charges['resavings'] = (charges['revalue'] * Decimal(str(float(discount_rate)))).quantize(Decimal('.00'), rounding=ROUND_UP)

            # accumulate charges across all services
            # eventually track total revalue
            rebill_summary['revalue'] += charges['revalue']
            rebill_summary['recharges'] += charges['recharges']
            rebill_summary['resavings'] += charges['resavings']

            rebill_summary['actualecharges'] += charges['actualecharges']
            rebill_summary['hypotheticalecharges'] += charges['hypotheticalecharges']

        # from old roll bill
        #r.balanceforward = r.priorbalance - r.paymentreceived
        rebill_summary.priorbalance = prior_bill.rebill_summary.totaldue
        rebill_summary['balanceforward'] = rebill_summary['priorbalance'] - rebill_summary['paymentreceived']

        rebill_summary['totaldue'] = rebill_summary['totaladjustment'] + rebill_summary['balanceforward'] + rebill_summary['recharges']

        # set data into the bill
        the_bill.rebill_summary = rebill_summary
        the_bill.utilbill_summary_charges = ub_summary_charges

        XMLUtils().save_xml_file(the_bill.xml(), targetBill, user, password)

    # TODO cover method that accepts charges_type of hypo or actual
    def sum_hypothetical_charges(self, unprocessedBill, targetBill, user=None, password=None):
        """ 
        After a rate structure has been bound, sum up the totals, by chargegroup.
        """

        the_bill = bill.Bill(unprocessedBill)

        hypothetical_charges = the_bill.hypothetical_charges
       
        for service, cg_items in hypothetical_charges.items():
            # cg_items contains mnt of chargegroups and a grand total

            # the grand total
            cg_items.total = Decimal("0.00")


            for chargegroup in cg_items.chargegroups:

                for charge in chargegroup.charges:

                    chargegroup.total += charge.total

                    # summarize the service
                    cg_items.total += charge.total

        # set the newly totalized charges
        the_bill.hypothetical_charges = hypothetical_charges

        XMLUtils().save_xml_file(the_bill.xml(), targetBill, user, password)

    def sum_actual_charges(self, unprocessedBill, targetBill, user=None, password=None):
        """ 
        After a rate structure has been bound, sum up the totals, by chargegroup.
        """

        the_bill = bill.Bill(unprocessedBill)

        actual_charges = the_bill.actual_charges
       
        for service, cg_items in actual_charges.items():
            # cg_items contains mnt of chargegroups and a grand total

            # the grand total
            cg_items.total = Decimal("0.00")

            for chargegroup in cg_items.chargegroups:

                for charge in chargegroup.charges:

                    chargegroup.total += charge.total

                    # summarize the service
                    cg_items.total += charge.total

        # set the newly totalized charges
        the_bill.actual_charges = actual_charges

        XMLUtils().save_xml_file(the_bill.xml(), targetBill, user, password)

    def copy_actual_charges(self, unprocessedBill, targetBill, user=None, password=None):
        the_bill = bill.Bill(unprocessedBill)

        #TODO: this actually deletes all existing hypothetical charges.  This is ok unless for some reason the set of hypothetical charges could be larger than the actual
        actual_charges = the_bill.actual_charges
        the_bill.hypothetical_charges = actual_charges

        XMLUtils().save_xml_file(the_bill.xml(), targetBill, user, password)

    def pay_bill(self, source_bill, target_bill, amountPaid, user=None, password=None):
        """
        Accepts the prior bill, so that the total due can be obtained.
        Sets the payment in the targetbill.
        Prior bills can be recomputed, which may change the past total due.
        Therefore current bills must pull that value forward.
        """

        #prior = bill.Bill(prior_bill)
        pay = bill.Bill(source_bill)

        pay_rebill = pay.rebill_summary

        # do this in sumBill
        #pay_rebill.priorbalance = prior.rebill_summary.totaldue
        pay_rebill.paymentreceived = Decimal(amountPaid)

        # set rebill back to bill
        pay.rebill_summary = pay_rebill

        XMLUtils().save_xml_file(pay.xml(), target_bill, user, password)


    def roll_bill(self, inputbill, targetBill, user=None, password=None):
        """
        Create rebill for next period, based on prior bill.
        This is acheived by accessing xml document for prior bill, and resetting select values.
        """

        the_bill = bill.Bill(inputbill)

        # increment sequence
        the_bill.id = int(the_bill.id)+1

        # get the rebill and zero it out
        r = the_bill.rebill_summary

        # process rebill

        r.begin = datetime.datetime.max
        r.begin = None
        r.end = None
        r.totaladjustment = Decimal("0.00")
        r.hypotheticalecharges = Decimal("0.00")
        r.actualecharges = Decimal("0.00")
        r.revalue = Decimal("0.00")
        r.recharges = Decimal("0.00")
        r.resavings = Decimal("0.00")
        r.duedate = None
        r.issued = None
        r.message = None

        # compute payments
        # moved to pay bill
        #r.priorbalance = r.totaldue
        r.totaldue = Decimal("0.00")
        #r.paymentreceived = Decimal(amountPaid)
        #r.balanceforward = r.priorbalance - r.paymentreceived

        # set rebill back to bill
        the_bill.rebill_summary = r

        # get utilbill summaries and zero them out
        ub_summary_charges = the_bill.utilbill_summary_charges
        for (service, charges) in ub_summary_charges.items():
            # utility billing periods are utility specific
            # TODO business logic specific dates are selected here
            charges.begin = charges.end
            charges.end = None

            charges.hypotheticalecharges = Decimal("0.00")
            charges.actualecharges = Decimal("0.00")
            charges.revalue = Decimal("0.00")
            charges.recharges = Decimal("0.00")
            charges.resavings = Decimal("0.00")

        # set the utilbill summaries back into bill
        the_bill.utilbill_summary_charges = ub_summary_charges

        # process /ub:bill/ub:details/

        # zero out details totals

        def zero_charges(details):

            for service, detail in details.items():

                print "got detail.total %s " % detail.total
                detail.total = Decimal("0.00")
                print "set detail.total %s " % detail.total

                for chargegroup in detail.chargegroups:
                    #TODO: zero out a chargegroup total when one exists

                    for charge in chargegroup.charges:
                        if hasattr(charge, "rate"): charge.rate = None 
                        if hasattr(charge, "quantity"): charge.quantity = None 
                        charge.total = Decimal("0.00")
            return details

        the_bill.actual_details = zero_charges(the_bill.actual_details)
        the_bill.hypothetical_details = zero_charges(the_bill.hypothetical_details)
       
        # reset measured usage
        measured_usage = the_bill.measured_usage

        for service, meters in measured_usage.items():
            for meter in meters:
                meter.priorreaddate = meter.presentreaddate
                meter.presentreaddate = None
                for register in meter.registers:
                    register.total = Decimal("0")
                    register.presentreading = Decimal("0")

        the_bill.measured_usage = measured_usage


        # zero out statistics section
        statistics = the_bill.statistics

        statistics.conventionalconsumed = None
        statistics.renewableconsumed = None
        statistics.renewableutilization = None
        statistics.conventionalutilization = None
        statistics.renewableproduced = None
        statistics.co2offset = None
        statistics.totalsavings = None
        statistics.totalrenewableconsumed = None
        statistics.totalrenewableproduced = None
        statistics.totaltrees = None
        statistics.totalco2offset = None

        the_bill.statistics = statistics

        # leave consumption trend alone since we want to carry it forward until it is based on the cubes
        # at which time we can just recreate the whole trend

        XMLUtils().save_xml_file(the_bill.xml(), targetBill, user, password)


    def commit_rebill(self, inputbill, targetBill, account, sequence, user=None, password=None):
        pass


    def bindrs(self, inputbill, outputbill, rsdb, hypothetical, user=None, password=None):
        """ This function binds a rate structure against the actual and hypothetical charges found """
        """ in a bill. If and RSI specifies information no in the bill, it is added to the bill.   """
        """ If the bill specifies information in a charge that is not in the RSI, the charge is """
        """ left untouched."""
        """ """

        import yaml
        import rate_structure

        # given a bill that has its actual or shadow registers populated, apply a rate structure.

        # load XML bill
        tree = etree.parse(inputbill)

        # grab the account id so that ratestructures are customer dependent
        account = self.get_elem(tree, "/ub:bill/@account")[0]
        id = self.get_elem(tree, "/ub:bill/@id")[0]

        # TODO: much of the code below to be refactored when register definitions are 
        # placed in the rate structure


        # obtain utilbill groves to determine what services are present
        # identify the per service rate structures for each utilbill
        for utilbill in tree.findall("{bill}utilbill"):

            # get name of the utility
            rsbinding_utilbill = utilbill.get("rsbinding")

            # get service
            service = utilbill.get("service")

            # get name of the rate structure
            # rateschedule rsbinding is deprecated
            #rsbinding_rateschedule = self.get_elem(tree, "/ub:bill/ub:details[@service='" + 
            #    service + "']/ub:rateschedule/@rsbinding")[0]

            # now load the rate structure and configure it
            # load all the documents contained within the single specified RS file
            # old style yaml files
            #for rs in yaml.load_all(file(rsdb + os.sep + os.path.join(rsbinding_utilbill, os.path.join(account, id)) + ".yaml")):

                # print "*** Loaded Rate Structure for " + service
                # print rs
            
            rs = yaml.load(file(os.path.join(rsdb, rsbinding_utilbill, account, id+".yaml")))
            # TODO: Check ratestructure valid date ranges
            rs = rate_structure.RateStructure(rs)
            #rs.configure()

            # acquire actual meter registers for this service
            actual_registers = self.get_elem(utilbill, "/ub:bill/ub:measuredusage[@service='" + 
                service + "']/ub:meter/ub:register[@shadow='false']")

            # each service has a number of actual utility registers
            for actual_register in actual_registers:

                # each register has a binding to a register declared in the rate structure
                rsbinding_register = actual_register.get("rsbinding")

                # actual register quantity, with shadow register value optionally added
                register_quantity = 0.0

                # acquire shadow register and track its value
                register_quantity += float(actual_register.find("{bill}total").text)

                if (hypothetical):
                    # acquire shadow register and add its value to the actual register to sum re and ce
                    shadow_reg_total = self.get_elem(actual_register,"../ub:register[@shadow='true' and @rsbinding='"
                        +rsbinding_register+"']/ub:total")[0]
                    register_quantity += float(shadow_reg_total.text)

                # populate rate structure with meter quantities read from XML
                rs.__dict__[rsbinding_register].quantity = register_quantity

            # now that the rate structure is loaded, configured and populated with registers
            # bind to the charge items in the bill

            # if hypothetical, then treat the hypothetical charges. If not, process actual
            charges = None
            if (hypothetical):
                charges = self.get_elem(utilbill, "/ub:bill/ub:details[@service='"
                    + service+"']/ub:chargegroup/ub:charges[@type='hypothetical']/ub:charge")
                # TODO: create the hypothetical charges from the actual charges 
            else:
                charges = self.get_elem(utilbill, "/ub:bill/ub:details[@service='"
                    + service + "']/ub:chargegroup/ub:charges[@type='actual']/ub:charge")
            
            # process each individual charge and bind it to the rate structure
            for charge in charges:
                print etree.tostring(charge)
                # a charge may not have a binding because it is not meant to be bound
                charge_binding = charge.get("rsbinding")
                if (charge_binding is None):
                    print "*** No rsbinding for " + etree.tostring(charge)
                    continue

                # obtain the rate structure item that is bound to this charge
                rsi = rs.__dict__[charge_binding]
                # flag the rsi so we can know which RSIs were not processed
                rsi.bound = True

                # if there is a description present in the rate structure, override the value in xml
                # if there is no description in the RSI, leave the one in XML
                if (rsi.description is not None):
                    description = charge.find("{bill}description")
                    if (description is None):
                        # description element missing, so insert one
                        description = etree.Element("{bill}description")
                        # description is always first child
                        charge.insert(0, description)
                        print "*** updated charge with description because it was absent in the bill and present in the RSI"
                    description.text = rsi.description

                # if the quantity is present in the rate structure, override value in XML
                if (rsi.quantity is not None):
                    quantity = charge.find("{bill}quantity")
                    if (quantity is None):
                        # quantity element is missing, so insert one
                        attribs = {}
                        if (rsi.quantityunits is not None):
                            attribs["units"] = rsi.quantityunits
                            
                        quantity = etree.Element("{bill}quantity", attribs)
                        # quantity is next sibling of description
                        if (charge.find("{bill}description") is not None):
                            charge.insert(1, quantity)
                        else:
                            charge.insert(0, quantity)
                        print "*** updated charge with quantity because it was absent in the bill and present in the RSI"
                    quantity.text = str(rsi.quantity)

                # if the rate is present in the rate structure, override value in XML
                if (rsi.rate is not None):
                    rate = charge.find("{bill}rate")
                    if (rate is None):
                        # rate element missing, so insert one
                        attribs = {}
                        if (rsi.rateunits is not None):
                            attribs["units"] = rsi.rateunits
                        rate = etree.Element("{bill}rate", attribs)
                        # insert as preceding sibling to the last element which is total
                        total = charge.find("{bill}total")
                        if (total is not None):
                            total.addprevious(rate)
                        else:
                            charge.append(rate)
                        print "*** updated charge with rate because it was absent in the bill and present in the RSI"
                    # wrap rsi.rate in a Decimal to avoid exponential formatting of very small rate values
                    rate.text = str(Decimal(str(rsi.rate)))

                total = charge.find("{bill}total")
                if (total is None):
                    # total element is missing, so create one
                    total = etree.Element("{bill}total")
                    # total is always last child
                    charge.append(total)
                    print "*** updated charge with total because it was absent in the bill and present in the RSI"
                total.text = str(rsi.total)




            for rsi in rs.rates:
                if (hasattr(rsi, 'bound') == False):
                    print "*** RSI was not bound " + str(rsi)


        XMLUtils().save_xml_file(etree.tostring(tree, pretty_print=True), outputbill, user, password)

    def calculate_statistics(self, input_bill, output_bill, user=None, password=None):
        """ Period Statistics for the input bill period are determined here from the total energy usage """
        """ contained in the registers. Cumulative statistics are determined by adding period statistics """
        """ to the past cumulative statistics """ 

        # the trailing bill where totals are obtained
        prev_bill = bill.Bill(input_bill)

        # the current bill where accumulated values are stored
        next_bill = bill.Bill(output_bill)

        # determine the renewable and conventional energy across all services by converting all registers to BTUs
        # TODO these conversions should be treated in a utility class
        def normalize(units, total):
            if (units.lower() == "kwh"):
                # 1 kWh = 3413 BTU
                return total * 3413 
            elif (units.lower() == "therms"):
                # 1 therm = 100000 BTUs
                return total * 100000
            else:
                raise Exception("Units '" + units + "' not supported")


        # total renewable energy
        re = 0
        # total conventional energy
        ce = 0

        # CO2 is fuel dependent
        co2 = 0
        # TODO these conversions should be treated in a utility class
        def calcco2(units, total):
            if (units.lower() == "kwh"):
                return total * Decimal("1.297")
            elif (units.lower() == "therms"):
                return total * Decimal("13.46")
            else:
                raise Exception("Units '" + units + "' not supported")

        # obtain all the registers, for all the services, that are of type 'total'
        #registers = self.get_elem(outputtree, "/ub:bill/ub:measuredusage/ub:meter/ub:register[@type=\"total\"]")
        #if not len(registers): print "Make sure total type registers exist!"

        for service, meters in next_bill.measured_usage.items():
            for meter in meters:
                for register in meter.registers:

                    units = register.units
                    total = register.total

                    if register.shadow is True:
                        re += normalize(units, total)
                        co2 += calcco2(units, total)
                    else:
                        ce += normalize(units, total)
                        
        next_stats = next_bill.statistics
        prev_stats = prev_bill.statistics

        # determine re to ce utilization ratio
        re_utilization = Decimal(str(re / (re + ce))).quantize(Decimal('.00'), rounding=ROUND_UP)
        ce_utilization = Decimal(str(ce / (re + ce))).quantize(Decimal('.00'), rounding=ROUND_DOWN)

        # update utilization stats
        next_stats.renewableutilization = re_utilization
        next_stats.conventionalutilization = ce_utilization

        # determine cumulative savings

        # update cumulative savings
        next_stats.totalsavings = prev_stats.totalsavings + next_bill.rebill_summary.resavings

        # set renewable consumed
        next_stats.renewableconsumed = re

        next_stats.totalrenewableconsumed = prev_stats.renewableconsumed + re

        # set conventional consumed
        next_stats.conventionalconsumed = ce

        next_stats.totalconventionalconsumed = prev_stats.conventionalconsumed + ce

        # set CO2 in XML
        next_stats.co2offset = co2

        # determine and set cumulative CO2
        next_stats.totalco2offset =  prev_stats.totalco2offset + co2

        # externalize this calculation to utilities
        next_stats.totaltrees = next_stats.totalco2offset/1300
        

        # determine re consumption trend
        # last day of re bill period is taken to be the month of consumption (This is ultimately utility dependent - 
        # especially when graphing ce from the utilty bill)
        billdate = next_bill.rebill_summary.end

        # determine current month (this needs to be quantized according to some logic)
        month = billdate.strftime("%b")

        for period in next_stats.consumptiontrend:
            if(period.month == month):
                period.quantity = re/100000

        next_bill.statistics = next_stats

        XMLUtils().save_xml_file(next_bill.xml(), output_bill, user, password)


    def calculate_reperiod(self, inputbill, outputbill, user=None, password=None):
        """ Set the Renewable Energy bill Period """

        inputtree = etree.parse(inputbill)
        outputtree = etree.parse(outputbill)

        # TODO: refactor out xml code to depend on bill.py
        utilbill_begin_periods = self.get_elem(inputtree, "/ub:bill/ub:utilbill/ub:billperiodbegin")
        utilbill_end_periods = self.get_elem(inputtree, "/ub:bill/ub:utilbill/ub:billperiodend")

        rebill_periodbegindate = datetime.datetime.max
        for period in utilbill_begin_periods:
            candidate_date = datetime.datetime.strptime(period.text, "%Y-%m-%d")
            # find minimum date
            if (candidate_date < rebill_periodbegindate):
                rebill_periodbegindate = candidate_date

        rebill_periodenddate = datetime.datetime.min 
        for period in utilbill_end_periods:
            # find maximum date
            candidate_date = datetime.datetime.strptime(period.text, "%Y-%m-%d")
            if (candidate_date > rebill_periodenddate):
                rebill_periodenddate = candidate_date

        rebillperiodbegin = self.get_elem(outputtree, "/ub:bill/ub:rebill/ub:billperiodbegin")[0].text = rebill_periodbegindate.strftime("%Y-%m-%d")
        rebillperiodend = self.get_elem(outputtree, "/ub:bill/ub:rebill/ub:billperiodend")[0].text = rebill_periodenddate.strftime("%Y-%m-%d")

        XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), outputbill, user, password)

    def issue(self, inputbill, outputbill, issuedate=None, user=None, password=None):
        """ Set the Renewable Energy bill Period """

        inputtree = etree.parse(inputbill)
        outputtree = etree.parse(outputbill)

        if issuedate is None:
            issuedate = datetime.date.today()
        else:
            issuedate = datetime.datetime.strptime(issuedate, "%Y-%m-%d")
        # TODO: parameterize for dependence on customer 
        duedate = issuedate + datetime.timedelta(days=30)

        # TODO: refactor out xml code to depend on bill.py
        self.get_elem(outputtree, "/ub:bill/ub:rebill/ub:issued")[0].text = issuedate.strftime("%Y-%m-%d")
        self.get_elem(outputtree, "/ub:bill/ub:rebill/ub:duedate")[0].text = duedate.strftime("%Y-%m-%d")

        XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), outputbill, user, password)

