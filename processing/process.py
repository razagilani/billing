#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""
import sys
sys.stdout = sys.stderr
import os  
from optparse import OptionParser
import copy
import datetime
import calendar
import pprint
#
# uuid collides with locals so both the locals and package are renamed
import uuid as UUID

import yaml

# used for processing fixed point monetary decimal numbers
from decimal import *
from billing import bill

import skyliner
import rate_structure
from billing import bill
from billing.processing import state
from billing.mongo import MongoReebill
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state
from billing.mongo import ReebillDAO
from billing import nexus_util
from billing import dateutils

class Process(object):
    """ Class with a variety of utility procedures for processing bills.
        The idea here is that this class is instantiated with the data
        access objects it needs, and then ReeBills (why not just references
        to them?) are passed in and returned.  
    """

    config = None
    
    def __init__(self, config, state_db, reebill_dao, rate_structure_dao,
            splinter, monguru):
        self.config = config
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        self.reebill_dao = reebill_dao
        self.splinter = splinter
        self.monguru = monguru

    # compute the value, charges and savings of renewable energy
    def sum_bill(self, session, prior_reebill, present_reebill):

        # get discount rate
        discount_rate = Decimal(str(self.state_db.discount_rate(session,
            present_reebill.account)))

        # reset ree_charges, ree_value, ree_savings so we can accumulate across
        # all services
        present_reebill.ree_value = Decimal("0")
        present_reebill.ree_charges = Decimal("0")
        present_reebill.ree_savings = Decimal("0")

        # reset hypothetical and actual totals so we can accumulate across all
        # services
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
            present_reebill.set_ree_charges_for_service(service, ree_charges)
            present_reebill.set_ree_savings_for_service(service, ree_savings)


        # accumulate at the reebill level
        present_reebill.hypothetical_total = present_reebill.hypothetical_total + hypothetical_total
        present_reebill.actual_total = present_reebill.actual_total + actual_total

        present_reebill.ree_value = Decimal(present_reebill.ree_value + ree_value).quantize(Decimal('.00'))
        present_reebill.ree_charges = Decimal(present_reebill.ree_charges + ree_charges).quantize(Decimal('.00'), rounding=ROUND_DOWN)
        present_reebill.ree_savings = Decimal(present_reebill.ree_savings + ree_savings).quantize(Decimal('.00'), rounding=ROUND_UP)

        # now grab the prior bill and pull values forward
        present_reebill.prior_balance = prior_reebill.balance_due
        present_reebill.balance_forward = present_reebill.prior_balance - present_reebill.payment_received
        present_reebill.balance_due = present_reebill.balance_forward + present_reebill.ree_charges

        # TODO total_adjustment


    def copy_actual_charges(self, reebill):

        for service in reebill.services:
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            reebill.set_hypothetical_chargegroups_for_service(service, actual_chargegroups)

    def pay_bill(self, session, reebill):

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
        payments = self.state_db.find_payment(session, reebill.account, period[0], period[1])
        # sum() of [] is int zero, so always wrap payments in a Decimal
        reebill.payment_received = Decimal(sum([payment.credit for payment in payments]))

    def roll_bill(self, session, reebill):
        '''Modifies 'reebill' to convert it into a template for the reebill of
        the next period. 'reebill' must be its customer's last bill before
        roll_bill is called. This method does not save the reebill in Mongo,
        but it DOES create new CPRS documents in Mongo (by copying the ones
        originally attached to the reebill).'''

        # obtain the last Reebill sequence from the state database
        # TODO: database connection needs to be passed through here
        # such that transactions encompassing the http request can be done
        if reebill.sequence < self.state_db.last_sequence(session, reebill.account):
            raise Exception("Not the last sequence")

        # duplicate the CPRS for each service
        # TODO: 22597151 refactor
        for service in reebill.services:
            utility_name = reebill.utility_name_for_service(service)
            rate_structure_name = reebill.rate_structure_name_for_service(service)

            # load current CPRS
            cprs = self.rate_structure_dao.load_cprs(reebill.account, reebill.sequence,
                reebill.branch, utility_name, rate_structure_name)
            if cprs is None:
                raise Exception("No current CPRS")

            # save it with same account, next sequence
            self.rate_structure_dao.save_cprs(reebill.account, reebill.sequence + 1,
                reebill.branch, utility_name, rate_structure_name, cprs)

        # increment sequence
        reebill.sequence = reebill.sequence + 1

        # set start date of each utility bill in this reebill to the end date
        # of the previous utility bill for that service
        for service in reebill.services:
            prev_start, prev_end = reebill.utilbill_period_for_service(service)
            reebill.set_utilbill_period_for_service(service, (prev_end, None))

        # save original end date of reebill before resetting: this will become
        # the new begin date and is needed to guess the new end date
        old_period_end = reebill.period_end

        # clear out much but not all data in the bill, including dates
        reebill.reset()
        # TODO: unclear that call to reset() belongs here. it should go as
        # early in the method as possible; putting it here suggests that
        # reset() wipes out everything below this call but not any of the
        # things preceding it, which is probably not true. and if it were, why
        # does reset() only reset such an arbitrary subset of the reebill's
        # data?
        # we do have a story suggesting that the reset method should/will go
        # away:
        # https://www.pivotaltracker.com/story/show/22547583

        # set reebill begin date and probable end date
        reebill.period_begin = old_period_end
        utilbills, new_period_end = state.guess_utilbills_and_end_date(session,
                reebill.account, old_period_end)
        reebill.period_end = new_period_end

        # set discount rate to the value in MySQL
        reebill.discount_rate = self.state_db.discount_rate(session,
                reebill.account)

        # create an initial rebill record to which the utilbills are later
        # attached
        self.state_db.new_rebill(session, reebill.account, reebill.sequence)

    def delete_reebill(self, session, account, sequence):
        '''Deletes the reebill given by 'account' and 'sequence': removes state
        data and utility bill associations from MySQL, and actual bill data
        from Mongo. A reebill that has been issued can't be deleted.'''
        # TODO add branch, which MySQL doesn't have yet:
        # https://www.pivotaltracker.com/story/show/24374911 

        # don't delete an issued reebill
        if self.state_db.is_issued(session, account, sequence):
            raise Exception("Can't delete an issued reebill.")

        # delete reebill document from Mongo
        self.reebill_dao.delete_reebill(account, sequence)

        # delete reebill state data from MySQL and dissociate utilbills from it
        self.state_db.delete_reebill(session, account, sequence)

    def create_new_account(self, session, account, name, discount_rate, template_account):

        result = self.state_db.account_exists(session, account)

        if result is True:
            raise Exception("Account exists")

        template_last_sequence = self.state_db.last_sequence(session, template_account)

        #TODO 22598787 use the active branch of the template_account
        reebill = self.reebill_dao.load_reebill(template_account, template_last_sequence, 0)

        # reset this bill to the new account
        reebill.account = account
        reebill.sequence = 0
        reebill.branch = 0
        reebill.reset()

        reebill.billing_address = {}
        reebill.service_address = {}

        # create template reebill in mongo for this new account
        self.reebill_dao.save_reebill(reebill)


        # TODO: 22597151 refactor
        # for each service, duplicate the CPRS
        for service in reebill.services:

            utility_name = reebill.utility_name_for_service(service)
            rate_structure_name = reebill.rate_structure_name_for_service(service)

            # load current CPRS of the template account
            # TODO: 22598787
            cprs = self.rate_structure_dao.load_cprs(template_account, template_last_sequence,
                0, utility_name, rate_structure_name)

            if cprs is None: raise Exception("No current CPRS")

            # save the CPRS for the new reebill
            self.rate_structure_dao.save_cprs(reebill.account, reebill.sequence,
                reebill.branch, utility_name, rate_structure_name, cprs)

        # create new account in mysql
        customer = self.state_db.new_account(session, name, account, discount_rate)

        return customer


    # TODO 21052893: probably want to set up the next reebill here.  Automatically roll?
    def attach_utilbills(self, session, account, sequence):
        '''Creates association between the reebill given by 'account',
        'sequence' and all utilbills belonging to that customer whose entire
        periods are within the date interval [start, end]. The utility bills
        are marked as processed.'''
        reebill = self.reebill_dao.load_reebill(account, sequence)
        begin = reebill.period_begin
        end = reebill.period_end
        self.state_db.attach_utilbills(session, account, sequence, begin, end)

    def bind_rate_structure(self, reebill):
            # process the actual charges across all services
            self.bindrs(reebill, self.rate_structure_dao)

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

            # TODO: 12205265 Big problem here.... if REG_TOTAL, for example, is used to calculate
            # a rate shown on the utility bill, it works - until REG_TOTAL has the shadow
            # renewable energy - then the rate is calculated incorrectly.  This is because
            # a seemingly innocent expression like SETF 2.22/REG_TOTAL.quantity calcs 
            # one way for actual charge computation and another way for hypothetical charge
            # computation.

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

    def calculate_statistics(self, prior_reebill, reebill):
        """ Period Statistics for the input bill period are determined here from the total energy usage """
        """ contained in the registers. Cumulative statistics are determined by adding period statistics """
        """ to the past cumulative statistics """ 


        # the trailing bill where totals are obtained
        #prev_bill = self.reebill_dao.load_reebill(prior_reebill.account, int(prior_reebill.sequence)-1)
        prev_bill = prior_reebill

        # the current bill where accumulated values are stored
        #next_bill = self.reebill_dao.load_reebill(reebill.account, int(reebill.sequence))
        next_bill = reebill

        # determine the renewable and conventional energy across all services by converting all registers to BTUs
        # TODO these conversions should be treated in a utility class
        def normalize(units, total):
            if (units.lower() == "kwh"):
                # 1 kWh = 3413 BTU
                return total * Decimal("3413")
            elif (units.lower() == "therms" or units.lower() == "ccf"):
                # 1 therm = 100000 BTUs
                return total * Decimal("100000")
            else:
                raise Exception("Units '" + units + "' not supported")


        # total renewable energy
        re = Decimal("0.0")
        # total conventional energy
        ce = Decimal("0.0")

        # CO2 is fuel dependent
        co2 = Decimal("0.0")
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
        next_stats['total_trees'] = next_stats['total_co2_offset']/Decimal("1300.0")
        

        if (self.config.getboolean('runtime', 'integrate_skyline_backend') is True):
            # fill in data for "Monthly Renewable Energy Consumption" graph
            print 'integrate skyline backend is:', self.config.getboolean('runtime', 'integrate_skyline_backend')

            # objects for getting olap data
            olap_id = nexus_util.NexusUtil().olap_id(reebill.account)
            install = self.splinter.get_install_obj_for(olap_id)

            bill_year, bill_month = dateutils.estimate_month(
                    next_bill.period_begin,
                    next_bill.period_end)
            next_stats['consumption_trend'] = []

            first_bill_date = self.reebill_dao \
                    .get_first_bill_date_for_account(reebill.account)
            first_bill_year = first_bill_date.year
            first_bill_month = first_bill_date.month

            first_month = install.install_commissioned.month
            for year, month in dateutils.months_of_past_year(bill_year, bill_month):
                # months before first bill have 0 energy, even if data were
                # collected during that time. however, the graph shows ALL the
                # renewable energy sold during the month of the first bill,
                # including energy sold before the install was "commissioned"
                # (meaning its data have been declared valid for billing).
                # TODO: change this to include only energy after the
                # install_commissioned date within that month?
                if year < first_bill_year or (year == first_bill_year and month
                        < first_bill_month):
                    renewable_energy_btus = 0
                else:
                    # get billing data from OLAP (instead of
                    # DataHandler.get_single_chunk_for_range()) for speed only.
                    # we insist that data should be available during the month of
                    # first billing and all following months; if get_data_for_month()
                    # fails, that's a real error that we shouldn't ignore.
                    # (but, inexplicably, that's not true: we bill webster
                    # house (10019) starting in october 2011 but its first
                    # monthly olap doc is in november.)
                    renewable_energy_btus = self.monguru.get_data_for_month(
                            install, year, month).energy_sold

                therms = Decimal(str(renewable_energy_btus)) / Decimal('100000.0')
                next_stats['consumption_trend'].append({
                    'month': calendar.month_abbr[month],
                    'quantity': therms
                })
             


    def calculate_reperiod(self, reebill):
        """ Set the Renewable Energy bill Period """
        #reebill = self.reebill_dao.load_reebill(account, sequence)
        
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

    def issue(self, session, account, sequence, issuedate=None):
        '''Sets the issue date of the reebill given by account, sequence to
        'issuedate' (or today by default) and the due date to 30 days from the
        issue date. The reebill is marked as issued in the state database.'''
        # set issue date and due date in mongo
        reebill = self.reebill_dao.load_reebill(account, sequence)
        if issuedate is None:
            issuedate = datetime.date.today()
        else:
            issuedate = datetime.datetime.strptime(issuedate, "%Y-%m-%d")
        # TODO: parameterize for dependence on customer 
        duedate = issuedate + datetime.timedelta(days=30)
        reebill.issue_date = issuedate
        reebill.due_date = duedate
        self.reebill_dao.save_reebill(reebill)

        # mark as issued in mysql
        self.state_db.issue(session, account, sequence)

    def all_ree_charges(self, session):

        accounts = self.state_db.listAccounts(session)

        rows = [] 
        totalCount = 0
        for account in accounts:
            for reebill in self.reebill_dao.load_reebills_for(account):
                totalCount += 1
                row = {}
                row['account'] = account
                row['sequence'] = reebill.sequence
                row['billing_address'] = reebill.billing_address
                row['service_address'] = reebill.service_address
                row['issue_date'] = reebill.issue_date
                row['period_begin'] = reebill.period_begin
                row['period_end'] = reebill.period_end
                row['ree_value'] = reebill.ree_value.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['ree_charges'] = reebill.ree_charges.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['actual_charges'] = reebill.actual_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['hypothetical_charges'] = reebill.hypothetical_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
                total_energy_therms = self.total_ree_in_reebill(reebill).quantize(Decimal(".0"), rounding=ROUND_HALF_EVEN)
                row['total_energy'] = total_energy_therms
                if total_energy_therms != Decimal(0):
                    row['marginal_rate_therm'] = ((reebill.hypothetical_total - reebill.actual_total)/total_energy_therms).quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
                else:
                    row['marginal_rate_therm'] = 0
                rows.append(row)

        return rows, totalCount

    def summary_ree_charges(self, session, accounts, full_names):

        rows = [] 
        for i, account in enumerate(accounts):
            row = {}
            reebills = self.reebill_dao.load_reebills_for(account)
            ree_charges = Decimal(sum([reebill.ree_charges for reebill in reebills]))
            actual_total = Decimal(sum([reebill.actual_total for reebill in reebills]))
            hypothetical_total = Decimal(sum([reebill.hypothetical_total for reebill in reebills]))
            total_energy = Decimal(0)
            marginal_rate_therm = Decimal(0)
            total_energy = self.total_ree_in_reebills(reebills)

            if total_energy != Decimal(0):
                marginal_rate_therm = (hypothetical_total - actual_total)/total_energy

            row['account'] = account
            row['fullname'] = full_names[i]
            row['ree_charges'] = ree_charges
            row['actual_charges'] = actual_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            row['hypothetical_charges'] = hypothetical_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            row['total_energy'] = total_energy.quantize(Decimal("0"))
            # per therm
            row['marginal_rate_therm'] = (marginal_rate_therm).quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            rows.append(row)

        return rows

    # TODO 20991629: maybe we should move this into ReeBill, because it should know how to report its data?
    def total_ree_in_reebill(self, reebill):
        """ Returns energy in Therms """

        total_energy = Decimal(0)

        services = reebill.services
        for service in services:
            registers = reebill.shadow_registers(service)
            # 20977305 - treat registers the same
            if service.lower() == 'gas':
                # add up all registers and normalize energy to BTU
                # gotta check units
                for register in registers:
                    if 'quantity' in register:
                        total_energy += register['quantity']
            elif service.lower() == 'electric':
                # add up only total register and normalize energy
                for register in registers:
                    if 'type' in register and register['type'] == 'total':
                        # 1kWh =  29.30722 Th
                        total_energy += (register['quantity'] / Decimal("29.30722"))

        return total_energy

    def total_ree_in_reebills(self, reebills):

        total_energy = Decimal(0)

        for reebill in reebills:
            total_energy += self.total_ree_in_reebill(reebill)

        return total_energy

        

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


