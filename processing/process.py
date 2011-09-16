#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""

#
# runtime support
#
import sys
sys.stdout = sys.stderr
import os  
from optparse import OptionParser

import datetime

# for xml processing
from lxml import etree
import copy

from billing import bill

from billing.xml_utils import XMLUtils

# for testing
#import StringIO

# used for processing fixed point monetary decimal numbers
from decimal import *
from billing import bill

import pprint

import yaml
import rate_structure
from billing.processing import state
from billing.mongo import MongoReebill

class Process(object):
    """ Class with a variety of utility procedures for processing bills """

    config = None
    
    def __init__(self, config, state_db, reebill_dao):
        self.config = config
        self.state_db = state_db
        self.reebill_dao = reebill_dao

    #TODO better function name to reflect the return types of XPath - not just elements, but sums, etc...
    #TODO function to return a single element vs list - that will clean up lots of code
    #TODO refactor to external utility class
    def get_elem(self, tree, xpath):
        return tree.xpath(xpath, namespaces={"ub":"bill"})


    # compute the value, charges and savings of renewable energy
    def sum_bill(self, prior_reebill, present_reebill):

        # get discount rate
        discount_rate = Decimal(str(self.state_db.discount_rate(present_reebill.account)))

        # reset ree_charges, ree_value, ree_savings so we can accumulate across all services
        present_reebill.ree_value = Decimal("0")
        present_reebill.ree_charges = Decimal("0")
        present_reebill.ree_savings = Decimal("0")

        # reset hypothetical and actual totals so we can accumulate across all services
        present_reebill.hypothetical_total = Decimal("0")
        present_reebill.actual_total = Decimal("0")


        # sum up chargegroups into total per utility bill and accumulate reebill values
        for service in present_reebill.services:

            actual_total = Decimal("0")
            hypothetical_total = Decimal("0")

            for chargegroup, charges in present_reebill.actual_chargegroups_for_service(service).items():
                actual_subtotal = Decimal("0")
                for charge in charges:
                    actual_subtotal += charge["total"]
                    actual_total += charge["total"]
                #TODO: subtotals for chargegroups?

            for chargegroup, charges in present_reebill.hypothetical_chargegroups_for_service(service).items():
                hypothetical_subtotal = Decimal("0")
                for charge in charges:
                    hypothetical_subtotal += charge["total"]
                    hypothetical_total += charge["total"]
                #TODO: subtotals for chargegroups?

            # calculate utilbill level numbers
            present_reebill.set_actual_total_for_service(service, actual_total)
            present_reebill.set_hypothetical_total_for_service(service, hypothetical_total)

            ree_value = hypothetical_total - actual_total
            ree_charges = (Decimal("1") - discount_rate) * (hypothetical_total - actual_total)
            ree_savings = discount_rate * (hypothetical_total - actual_total)

            present_reebill.set_ree_value_for_service(service, ree_value.quantize(Decimal('.00')))
            present_reebill.set_ree_charges_for_service(service, Decimal(ree_charges).quantize(Decimal('.00'),rounding=ROUND_DOWN))
            present_reebill.set_ree_savings_for_service(service, Decimal(ree_savings).quantize(Decimal('.00'),rounding=ROUND_UP))


            # accumulate at the reebill level
            present_reebill.hypothetical_total = present_reebill.hypothetical_total + hypothetical_total
            present_reebill.actual_total = present_reebill.actual_total + actual_total

            present_reebill.ree_value = present_reebill.ree_value + ree_value
            present_reebill.ree_charges = present_reebill.ree_charges + ree_charges
            present_reebill.ree_savings = present_reebill.ree_savings + ree_savings

            # now grab the prior bill and pull values forward
            present_reebill.prior_balance = prior_reebill.balance_due
            present_reebill.balance_forward = present_reebill.prior_balance - present_reebill.payment_received
            present_reebill.balance_due = present_reebill.balance_forward + present_reebill.ree_charges

            # TODO total_adjustment


    def copy_actual_charges(self, reebill):

        for service in reebill.services:
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            reebill.set_hypothetical_chargegroups_for_service(service, actual_chargegroups)

    def pay_bill(self, account, sequence):

        pay = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

        pay_rebill = pay.rebill_summary

        # depend on first ub period to be the date range for which a payment is seeked.
        # this is a wrong design because there may be more than on ub period and
        # these periods come back in document order, which could change.
        ubperiod = pay.utilbill_summary_charges.itervalues().next()
        payments = self.state_db.find_payment(account, pay_rebill.begin, pay_rebill.end)
        pay_rebill.paymentreceived = sum([payment.credit for payment in payments])

        # set rebill back to bill
        pay.rebill_summary = pay_rebill

        XMLUtils().save_xml_file(pay.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence), self.config.get("xmldb", "user"), 
            self.config.get("xmldb", "password"))
        # save in mongo
        reebill = MongoReebill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))
        self.reebill_dao.save_reebill(reebill)

    def roll_bill(self, account, sequence):
        """
        Create rebill for next period, based on prior bill.
        This is acheived by accessing xml document for prior bill, and resetting select values.
        """

        # obtain the last Rebill sequence
        last_sequence = self.state_db.last_sequence(account)

        if (int(sequence) < int(last_sequence)):
            raise Exception("Not the last sequence")

        next_sequence = int(last_sequence + 1)

        # duplicate the rate structure(s) so that it may be edited
        # first, we must get the bill and introspect it to determine what rate structures it is bound to
        the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

        utilbills = the_bill.utilbill_summary_charges
        rsbindings = [utilbill.rsbinding for (s, utilbill) in utilbills.items()]

        rspath = self.config.get("billdb", "rspath")

        import shutil 
        for rsbinding in rsbindings:
            shutil.copyfile(os.path.join(rspath, rsbinding, account, sequence+".yaml"), os.path.join(rspath, rsbinding, account, str(next_sequence)+".yaml"))
            

        # increment sequence
        the_bill.id = next_sequence

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

                detail.total = Decimal("0.00")

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
                
        XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"),
            account, next_sequence), self.config.get("xmldb", "user"), self.config.get("xmldb", "password"))
        # save in mongo
        reebill = MongoReebill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))
        self.reebill_dao.save_reebill(reebill)

        # create an initial rebill record to which the utilbills are later associated
        self.state_db.new_rebill(
            account,
            next_sequence
        )


    def commit_rebill(self, account, sequence):

            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))
            begin = the_bill.rebill_summary.begin
            end = the_bill.rebill_summary.end

            self.state_db.commit_bill(
                account,
                sequence,
                begin,
                end
            )

    def load_rs(self, rsdb, rsbinding, account, sequence):
        rs = yaml.load(file(os.path.join(rsdb, rsbinding, account, sequence+".yaml")))
        return rate_structure.RateStructure(rs)


    def bind_rate_structure(self, account, sequence):

            # actual
            self.bindrs(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("billdb", "rspath"),
                False, 
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

            #hypothetical
            self.bindrs(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("billdb", "rspath"),
                True, 
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

            self.calculate_reperiod(account, sequence)


    def bindrs(self, inputbill, outputbill, rsdb, hypothetical, user=None, password=None):
        """ This function binds a rate structure against the actual and hypothetical charges found """
        """ in a bill. If and RSI specifies information no in the bill, it is added to the bill.   """
        """ If the bill specifies information in a charge that is not in the RSI, the charge is """
        """ left untouched."""
        """ """

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

            rs = self.load_rs(rsdb, rsbinding_utilbill, account, id)

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
                        +rsbinding_register+"']/ub:total")

                    # it is possible a shadow register does not exist, because we may be showing all meters for a
                    # given service and only one of those meters services hot water and is offset by renewable
                    if len(shadow_reg_total) > 0:
                        register_quantity += float(shadow_reg_total[0].text)

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
        # save in mongo
        reebill = MongoReebill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, id))
        self.reebill_dao.save_reebill(reebill)

    def calculate_statistics(self, account, sequence):
        """ Period Statistics for the input bill period are determined here from the total energy usage """
        """ contained in the registers. Cumulative statistics are determined by adding period statistics """
        """ to the past cumulative statistics """ 


        # the trailing bill where totals are obtained
        prev_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, int(sequence)-1))

        # the current bill where accumulated values are stored
        next_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))

        # determine the renewable and conventional energy across all services by converting all registers to BTUs
        # TODO these conversions should be treated in a utility class
        def normalize(units, total):
            if (units.lower() == "kwh"):
                # 1 kWh = 3413 BTU
                return total * 3413 
            elif (units.lower() == "therms" or units.lower() == "ccf"):
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
            elif (units.lower() == "therms" or units.lower() == "ccf"):
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

        XMLUtils().save_xml_file(next_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence), 
            self.config.get("xmldb", "user"), self.config.get("xmldb", "password"))
        # save in mongo
        reebill = MongoReebill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))
        self.reebill_dao.save_reebill(reebill)


    def calculate_reperiod(self, account, sequence):
        """ Set the Renewable Energy bill Period """

        inputtree = etree.parse("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))
        outputtree = etree.parse("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))

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

        XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence), 
            self.config.get("xmldb", "user"), self.config.get("xmldb", "password"))
        # save in mongo
        reebill = MongoReebill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))
        self.reebill_dao.save_reebill(reebill)

    def issue(self, account, sequence, issuedate=None):
        """ Set the Renewable Energy bill Period """

        inputtree = etree.parse("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))
        outputtree = etree.parse("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))

        if issuedate is None:
            issuedate = datetime.date.today()
        else:
            issuedate = datetime.datetime.strptime(issuedate, "%Y-%m-%d")
        # TODO: parameterize for dependence on customer 
        duedate = issuedate + datetime.timedelta(days=30)

        # TODO: refactor out xml code to depend on bill.py
        self.get_elem(outputtree, "/ub:bill/ub:rebill/ub:issued")[0].text = issuedate.strftime("%Y-%m-%d")
        self.get_elem(outputtree, "/ub:bill/ub:rebill/ub:duedate")[0].text = duedate.strftime("%Y-%m-%d")

        XMLUtils().save_xml_file(etree.tostring(outputtree, pretty_print=True), "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence), 
            self.config.get("xmldb", "user"), self.config.get("xmldb", "password"))
        # save in mongo
        reebill = MongoReebill("%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence))
        self.reebill_dao.save_reebill(reebill)

    def issue_to_customer(self, account, sequence):

        # issue to customer
        self.state_db.issue(account, sequence)

