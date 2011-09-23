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
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state
from billing.mongo import ReebillDAO

class Process(object):
    """ Class with a variety of utility procedures for processing bills """

    config = None
    
    def __init__(self, config, state_db, reebill_dao, rate_structure_dao):
        self.config = config
        self.state_db = state_db
        self.reebill_dao = reebill_dao
        self.rate_structure_dao = rate_structure_dao

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
        reebill = self.reebill_dao.load_reebill(account, sequence)
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
        reebill = self.reebill_dao.load_reebill(account, sequence)
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


    def bind_rate_structure(self, reebill):

            # process the actual charges across all services
            self.bindrs(reebill, self.rate_structure_dao)

            self.calculate_reperiod(reebill.account, reebill.sequence)

    def bindrs(self, reebill, ratestructure_db):
        """ This function binds a rate structure against the actual and hypothetical charges found """
        """ in a bill. If and RSI specifies information no in the bill, it is added to the bill.   """
        """ If the bill specifies information in a charge that is not in the RSI, the charge is """
        """ left untouched."""

        account = reebill.account
        sequence = reebill.sequence

        # process rate structures for all services
        for service in reebill.services:



            #
            # All registers for all meters in a given service are made available
            # to the rate structure for the given service.
            # Registers that are not to be used by the rate structure should
            # simply not have an rsi_binding.
            #

            # actual

            rate_structure = self.rate_structure_dao.load_rate_structure(reebill, service)

            # find out what registers are needed to process this rate structure
            #register_needs = rate_structure.register_needs()

            # get metered energy from all meter registers in the reebill
            actual_register_readings = reebill.actual_registers(service)

            # apply the registers from the reebill to the probable rate structure
            rate_structure.bind_register_readings(actual_register_readings)

            # process actual charges with non-shadow meter register totals
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)

            # iterate over the charge groups, binding the reebill charges to its associated RSI
            for chargegroup, charges in actual_chargegroups.items():
                rate_structure.bind_charges(charges)
            reebill.set_actual_chargegroups_for_service(service, actual_chargegroups)


            # process hypothetical charges with non-shadow + shadow meter register totals
            rate_structure = self.rate_structure_dao.load_rate_structure(reebill, service)

            # find out what registers are needed to process this rate structure
            #register_needs = rate_structure.register_needs()

            actual_register_readings = reebill.actual_registers(service)
            shadow_register_readings = reebill.shadow_registers(service)

            # add the shadow register totals to the actual register, and re-process

            # TODO: probably a better way to do this
            for shadow_reading in shadow_register_readings:
                for actual_reading in actual_register_readings:
                    if actual_reading['identifier'] == shadow_reading['identifier']:
                        shadow_reading['total'] += actual_reading['total']
                # TODO: throw exception when registers mismatch

            # apply the combined registers from the reebill to the probable rate structure
            rate_structure.bind_register_readings(shadow_register_readings)


            # process actual charges with non-shadow meter register totals
            hypothetical_chargegroups = reebill.hypothetical_chargegroups_for_service(service)

            # iterate over the charge groups, binding the reebill charges to its associated RSI
            for chargegroup, charges in hypothetical_chargegroups.items():
                rate_structure.bind_charges(charges)
            reebill.set_actual_chargegroups_for_service(service, actual_chargegroups)

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
        reebill = self.reebill_dao.load_reebill(account, sequence)
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
        reebill = self.reebill_dao.load_reebill(account, sequence)
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
        reebill = self.reebill_dao.load_reebill(account, sequence)
        self.reebill_dao.save_reebill(reebill)

    def issue_to_customer(self, account, sequence):

        # issue to customer
        self.state_db.issue(account, sequence)

if __name__ == '__main__':


    import pdb
    pdb.set_trace()

    from billing.processing.rate_structure import Register

    reg_data = {u'descriptor': u'REG_THERMS', u'description': u'Total therm register', u'quantityunits': u'therm', u'quantity': u'0'}
    my_reg = Register(reg_data)

    reebill_dao = ReebillDAO({
        "host":"localhost", 
        "port":27017, 
        "database":"skyline", 
        "collection":"reebills", 
        "destination_prefix":"http://localhost:8080/exist/rest/db/skyline/bills"
    })

    ratestructure_dao = RateStructureDAO({
        "database":"skyline",
        "rspath":"/db-dev/skyline/ratestructure/",
        "host":"localhost",
        "collection":"ratestructure",
        "port": 27017
    })

    reebill = reebill_dao.load_reebill("10002","17")
    Process(None, None, reebill_dao, ratestructure_dao).bind_rate_structure(reebill)


