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

import copy

from billing import bill


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

# uuid collides with locals so both the locals and package are renamed
import uuid as UUID

class Process(object):
    """ Class with a variety of utility procedures for processing bills.
        The idea here is that this class is instantiated with the data
        access objects it needs, and then ReeBills (why not just references
        to them?) are passed in and returned.  
    """

    config = None
    
    def __init__(self, config, state_db, reebill_dao, rate_structure_dao):
        self.config = config
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        #TODO: why do we need a reebill_dao? Reebills get passed in to this helper class
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

    def pay_bill(self, reebill):

        # depend on first ub period to be the date range for which a payment is seeked.
        # this is a wrong design because there may be more than one ub period
        # in the case of multiple services with staggered periods.
        # can't use reeperiod because it overlaps.
        # TODO: determine the date range for which a payment is applied
        # see bug 16622833 and feature 16622489

        # get a service from the bill
        for service in reebill.services:
            pass

        all_service_periods = reebill.utilbill_periods

        period = all_service_periods[service]

        payments = self.state_db.find_payment(reebill.account, period[0], period[1])
        # sum() of [] is int zero, so always wrap payments in a Decimal
        reebill.payment_received = Decimal(sum([payment.credit for payment in payments]))

    def roll_bill(self, reebill):
        """
        Create rebill for next period, based on prior bill.
        """

        # obtain the last Reebill sequence from the state database
        # TODO: database connection needs to be passed through here
        # such that transactions encompassing the http request can be done
        last_sequence = self.state_db.last_sequence(reebill.account)

        if (int(reebill.sequence) < int(last_sequence)):
            raise Exception("Not the last sequence")

        next_sequence = int(last_sequence + 1)

        # for each service, duplicate the CPRS
        for service in reebill.services:

            utility_name = reebill.utility_name_for_service(service)
            rate_structure_name = reebill.rate_structure_name_for_service(service)

            # load current CPRS
            cprs = self.rate_structure_dao.load_cprs(reebill.account, reebill.sequence,
                reebill.branch, utility_name, rate_structure_name)

            if cprs is None: raise Exception("No current CPRS")

            # save the next CPRS
            self.rate_structure_dao.save_cprs(reebill.account, next_sequence,
                reebill.branch, utility_name, rate_structure_name, cprs)

        # increment reebill sequence
        reebill.sequence = next_sequence

        # process rebill
        reebill.period_begin = None
        reebill.period_end = None
        reebill.total_adjustment = Decimal("0.00")
        reebill.hypothetical_total = Decimal("0.00")
        reebill.actual_total = Decimal("0.00")
        reebill.ree_value = Decimal("0.00")
        reebill.ree_charges = Decimal("0.00")
        reebill.ree_savings = Decimal("0.00")
        reebill.due_date = None
        reebill.issue_date = None
        reebill.motd = None

        reebill.prior_balance = Decimal("0.00")
        reebill.total_due = Decimal("0.00")
        reebill.payment_received = Decimal("0.00")
        reebill.balance_forward = Decimal("0.00")

        for service in reebill.services:

            # get utilbill numbers and zero them out
            reebill.set_actual_total_for_service(service, Decimal("0.00")) 
            reebill.set_hypothetical_total_for_service(service, Decimal("0.00")) 
            reebill.set_ree_value_for_service(service, Decimal("0.00")) 
            reebill.set_ree_savings_for_service(service, Decimal("0.00")) 
            reebill.set_ree_charges_for_service(service, Decimal("0.00")) 

            # set utility period dates
            old_period = reebill.utilbill_period_for_service(service)
            # end is now begin
            # TODO: the end date might not be the begin date, so this could be
            # a utility specific business rule
            old_period = (old_period[1], None)
            reebill.set_utilbill_period_for_service(service, old_period)

            # set new UUID's & clear out the last bound charges
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            for (group, charges) in actual_chargegroups.items():
                for charge in charges:
                    charge['uuid'] = str(UUID.uuid1())
                    if 'rate' in charge: del charge['rate']
                    if 'quantity' in charge: del charge['quantity']
                    if 'total' in charge: del charge['total']
                    
            reebill.set_actual_chargegroups_for_service(service, actual_chargegroups)

            hypothetical_chargegroups = reebill.hypothetical_chargegroups_for_service(service)
            for (group, charges) in hypothetical_chargegroups.items():
                for charge in charges:
                    charge['uuid'] = str(UUID.uuid1())
                    if 'rate' in charge: del charge['rate']
                    if 'quantity' in charge: del charge['quantity']
                    if 'total' in charge: del charge['total']
                    
            reebill.set_hypothetical_chargegroups_for_service(service, hypothetical_chargegroups)

       
        # reset measured usage

        for service in reebill.services:
            for meter in reebill.meters_for_service(service):
                reebill.set_meter_read_date(service, meter['identifier'], None, meter['present_read_date'])
            for actual_register in reebill.actual_registers(service):
                reebill.set_actual_register_quantity(actual_register['identifier'], 0)
            for shadow_register in reebill.shadow_registers(service):
                reebill.set_shadow_register_quantity(shadow_register['identifier'], 0)


        # zero out statistics section
        statistics = reebill.statistics

        statistics["conventional_consumed"] = None
        statistics["renewable_consumed"] = None
        statistics["renewable_utilization"] = None
        statistics["conventional_utilization"] = None
        statistics["renewable_produced"] = None
        statistics["co2_offset"] = None
        statistics["total_savings"] = None
        statistics["total_renewable_consumed"] = None
        statistics["total_renewable_produced"] = None
        statistics["total_trees"] = None
        statistics["total_co2_offset"] = None

        reebill.statistics = statistics

        # leave consumption trend alone since we want to carry it forward until it is based on the cubes
        # at which time we can just recreate the whole trend

        # TODO: this needs to be done in a http request level database transaction
        # create an initial rebill record to which the utilbills are later associated
        self.state_db.new_rebill(
            reebill.account,
            reebill.sequence
        )

        # reebill is saved by caller - but what happens if the save fails?
        # the state_db transaction is done at this point

    def commit_rebill(self, account, sequence):
        reebill = self.reebill_dao.load_reebill(account, sequence)
        begin = reebill.period_begin
        end = reebill.period_end

        self.state_db.commit_bill(account, sequence, begin, end)

    # TODO: delete me
    def load_rs(self, rsdb, rsbinding, account, sequence):
        raise Exception("Nobody should be calling this now")
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

            # hypothetical charges

            # process hypothetical charges with non-shadow + shadow meter register totals
            rate_structure = self.rate_structure_dao.load_rate_structure(reebill, service)

            # find out what registers are needed to process this rate structure
            #register_needs = rate_structure.register_needs()

            actual_register_readings = reebill.actual_registers(service)
            shadow_register_readings = reebill.shadow_registers(service)

            # add the shadow register totals to the actual register, and re-process

            # TODO: Big problem here.... if REG_TOTAL, for example, is used to calculate
            # a rate shown on the utility bill, it works - until REG_TOTAL has the shadow
            # renewable energy - then the rate is calculated incorrectly.  This is because
            # a seemingly innocent expression like SETF 2.22/REG_TOTAL.quantity calcs 
            # one way for actual charge computation and another way for hypothetical charge
            # computation.  See 12205265

            # TODO: probably a better way to do this
            registers_to_bind = copy.deepcopy(shadow_register_readings)
            for shadow_reading in registers_to_bind:
                for actual_reading in actual_register_readings:
                    if actual_reading['identifier'] == shadow_reading['identifier']:
                        shadow_reading['quantity'] += actual_reading['quantity']
                # TODO: throw exception when registers mismatch

            # apply the combined registers from the reebill to the probable rate structure
            rate_structure.bind_register_readings(registers_to_bind)


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
        prev_bill = self.reebill_dao.load_reebill(account, int(sequence)-1)

        # the current bill where accumulated values are stored
        next_bill = self.reebill_dao.load_reebill(account, int(sequence))

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

        for meters in next_bill.meters.itervalues():                        
            for meter in meters:
                for register in meter['registers']:
                    units = register['quantity_units']
                    total = register['quantity']
                    if register['shadow'] == True:
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
        next_stats['renewable_utilization'] = re_utilization
        next_stats['conventional_utilization'] = ce_utilization

        # determine cumulative savings

        # update cumulative savings
        next_stats['total_savings'] = prev_stats['total_savings'] + next_bill.ree_savings

        # set renewable consumed
        next_stats['renewable_consumed'] = re

        next_stats['total_renewable_consumed'] = prev_stats['renewable_consumed'] + re

        # set conventional consumed
        next_stats['conventional_consumed'] = ce

        next_stats['total_conventional_consumed'] = prev_stats['conventional_consumed'] + ce

        # set CO2
        next_stats['co2_offset'] = co2

        # determine and set cumulative CO2
        next_stats['total_co2_offset'] =  prev_stats['total_co2_offset'] + co2

        # externalize this calculation to utilities
        next_stats['total_trees'] = next_stats['total_co2_offset']/1300
        

        # determine re consumption trend
        # last day of re bill period is taken to be the month of consumption (This is ultimately utility dependent - 
        # especially when graphing ce from the utilty bill)
        #billdate = next_bill.rebill_summary.end
        billdate = next_bill.period_end

        # determine current month (this needs to be quantized according to some logic)
        month = billdate.strftime("%b")

        for period in next_stats['consumption_trend']:
            if(period['month'] == month):
                period['quantity'] = re/100000

        next_bill.statistics = next_stats

        # save in mongo
        #reebill = self.reebill_dao.load_reebill(account, sequence)
        self.reebill_dao.save_reebill(next_bill)


    def calculate_reperiod(self, account, sequence):
        """ Set the Renewable Energy bill Period """
        reebill = self.reebill_dao.load_reebill(account, sequence)
        
        utilbill_period_beginnings = []
        utilbill_period_ends = []
        for period in reebill.utilbill_periods.itervalues():
            utilbill_period_beginnings.append(period[0])
            utilbill_period_ends.append(period[1])

        rebill_periodbegindate = datetime.datetime.max
        for beginning in utilbill_period_beginnings:
            candidate_date = datetime.datetime(beginning.year, beginning.month, beginning.day, 0, 0, 0)
            # find minimum date
            if (candidate_date < rebill_periodbegindate):
                rebill_periodbegindate = candidate_date

        rebill_periodenddate = datetime.datetime.min 
        for end in utilbill_period_ends:
            # find maximum date
            candidate_date = datetime.datetime(end.year, end.month, end.day, 0, 0, 0)
            if (candidate_date > rebill_periodenddate):
                rebill_periodenddate = candidate_date

        reebill.period_begin = rebill_periodbegindate
        reebill.period_end = rebill_periodenddate

        # save in mongo
        #reebill = self.reebill_dao.load_reebill(account, sequence)
        self.reebill_dao.save_reebill(reebill)

    def issue(self, account, sequence, issuedate=None):
        """ Set the Renewable Energy bill Period """

        reebill = self.reebill_dao.load_reebill(account, sequence)

        if issuedate is None:
            issuedate = datetime.date.today()
        else:
            issuedate = datetime.datetime.strptime(issuedate, "%Y-%m-%d")
        # TODO: parameterize for dependence on customer 
        duedate = issuedate + datetime.timedelta(days=30)

        reebill.issue_date = issuedate
        reebill.due_date = duedate

        # save in mongo
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


