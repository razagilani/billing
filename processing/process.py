#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""
import sys
import os  
import copy
import datetime
from datetime import date
import calendar
import pprint
from optparse import OptionParser
from decimal import *
#
# uuid collides with locals so both the locals and package are renamed
import uuid as UUID
import skyliner
from billing.processing import state
from billing.mongo import MongoReebill
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state
from billing.processing.db_objects import Payment, Customer, UtilBill
from billing.mongo import ReebillDAO
from billing import nexus_util
from billing import dateutils
from billing.dateutils import estimate_month, month_offset, month_difference
from billing.monthmath import Month, approximate_month

sys.stdout = sys.stderr
class Process(object):
    """ Class with a variety of utility procedures for processing bills.
        The idea here is that this class is instantiated with the data
        access objects it needs, and then ReeBills (why not just references
        to them?) are passed in and returned.  
    """

    config = None
    
    def __init__(self, config, state_db, reebill_dao, rate_structure_dao,
            billupload, splinter, monguru):
        self.config = config
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        self.reebill_dao = reebill_dao
        self.billupload = billupload
        self.splinter = splinter
        self.monguru = monguru

    def new_account(self, session, name, account, discount_rate, late_charge_rate):
        new_customer = Customer(name, account, discount_rate, late_charge_rate)
        session.add(new_customer)
        return new_customer

    def upload_utility_bill(self, session, account, service, begin_date,
            end_date, bill_file, file_name):
        '''Uploads 'bill_file' with the name 'file_name' as a utility bill for
        the given account, service, and dates. If the upload succeeds, a row is
        added to the utilbill table. If this is the newest or oldest utility
        bill for the given account and service, "hypothetical" utility bills
        will be added to cover the gap between this bill's period and the
        previous newest or oldest one respectively.'''

        # get & save end date of last bill (before uploading a new bill which
        # may come later)
        original_last_end = self.state_db.last_utilbill_end_date(session,
                account)

        if bill_file is None:
            # if there's no file, this is a "skyline estimated bill":
            # record it in the database with that state, but don't upload
            # anything
            self.state_db.record_utilbill_in_database(session, account,
                    service, begin_date, end_date, datetime.datetime.utcnow(),
                    state=UtilBill.SkylineEstimated)
        else:
            # if there is a file, get the Python file object and name
            # string from CherryPy, and pass those to BillUpload to upload
            # the file (so BillUpload can stay independent of CherryPy)
            upload_result = self.billupload.upload(account, begin_date,
                    end_date, bill_file, file_name)
            if upload_result is True:
                self.state_db.record_utilbill_in_database(session, account,
                        service, begin_date, end_date,
                        datetime.datetime.utcnow())
            else:
                raise IOError('File upload failed: %s %s %s' % (file_name,
                    begin_date, end_date))

        # if begin_date does not match end date of latest existing bill, create
        # hypothetical bills to cover the gap
        if original_last_end is not None and begin_date > original_last_end:
            self.state_db.fill_in_hypothetical_utilbills(session, account,
                    service, original_last_end, begin_date)

    #def delete_utility_bill(self, session, account, service, start_date, end_date):
        #'''Deletes the utility bill given by customer account, service, and
        #period dates, if it's not associated or attached to a reebill. Raises
        #an exception if the utility bill cannot be deleted.'''
        #utilbill = session.query(UtilBill)\
                #.filter(UtilBill.period_start==start_date and
                #UtilBill.period_end==end_date).one()
        #if utilbill.has_reebill:
            #raise Exception("Can't delete an attached utility bill.")

        ## find out if some reebill in mongo has this utilbill associated with
        ## it. (there should be at most one.)
        #possible_reebills = self.reebill_dao.load_reebills_in_period(account,
                #start_date=start_date, end_date=end_date)
        #if len(possible_reebills) > 0:
            #raise Exception(("Can't delete a utility bill that has reebill"
                #" associated with it."))

        ## OK to delete now.
        ## first try to delete the file on disk
        #self.billupload.delete_utilbill_file(account, start_date, end_date)

        ## TODO move to StateDB?
        #session.delete(utilbill)

    def delete_utility_bill(self, session, utilbill_id):
        '''Deletes the utility bill given by utilbill_id, if it's not
        associated or attached to a reebill. Raises a ValueError if the utility
        bill cannot be deleted.'''
        utilbill = session.query(UtilBill)\
                .filter(UtilBill.id==utilbill_id).one()
        if utilbill.has_reebill:
            raise ValueError("Can't delete an attached utility bill.")

        # find out if some reebill in mongo has this utilbill associated with
        # it. (there should be at most one.)
        possible_reebills = self.reebill_dao.load_reebills_in_period(
                utilbill.customer.account, start_date=utilbill.period_start,
                end_date=utilbill.period_end)
        if len(possible_reebills) > 0:
            raise ValueError(("Can't delete a utility bill that has reebill"
                " associated with it."))

        # OK to delete now.
        # first try to delete the file on disk
        self.billupload.delete_utilbill_file(utilbill.customer.account,
                utilbill.period_start, utilbill.period_end)

        # TODO move to StateDB?
        session.delete(utilbill)

    def sum_bill(self, session, prior_reebill, present_reebill):
        '''Compute everything about the bill that can be continuously
        recomputed. This should be called immediately after roll_bill()
        whenever roll_bill() is called.'''
        # get discount rate
        # TODO: 26500689 discount rate in the reebill structure must be relied on
        # versus fetch the instantaneous one - what if a historical bill is being
        # summed?  The discount rate in the reebill would have to be relied on.
        #discount_rate = Decimal(str(self.state_db.discount_rate(session,
        #    present_reebill.account)))

        discount_rate = present_reebill.discount_rate
        if not discount_rate:
            raise Exception("%s-%s-%s has no discount rate" % (present_reebill.account, 
                present_reebill.sequence, present_reebill.branch))

        # reset ree_charges, ree_value, ree_savings so we can accumulate across
        # all services
        present_reebill.ree_value = Decimal("0")
        present_reebill.ree_charges = Decimal("0")
        present_reebill.ree_savings = Decimal("0")

        # reset hypothetical and actual totals so we can accumulate across all
        # services
        present_reebill.hypothetical_total = Decimal("0")
        present_reebill.actual_total = Decimal("0")

        # sum up chargegroups into total per utility bill and accumulate
        # reebill values
        for service in present_reebill.services:

            actual_total = Decimal("0")
            hypothetical_total = Decimal("0")

            for chargegroup, charges in present_reebill.\
                    actual_chargegroups_for_service(service).items():
                actual_subtotal = Decimal("0")
                for charge in charges:
                    actual_subtotal += charge["total"]
                    actual_total += charge["total"]
                #TODO: subtotals for chargegroups?

            for chargegroup, charges in present_reebill.\
                    hypothetical_chargegroups_for_service(service).items():
                hypothetical_subtotal = Decimal("0")
                for charge in charges:
                    hypothetical_subtotal += charge["total"]
                    hypothetical_total += charge["total"]
                #TODO: subtotals for chargegroups?

            # calculate utilbill level numbers
            present_reebill.set_actual_total_for_service(service, actual_total)
            present_reebill.set_hypothetical_total_for_service(service,
                    hypothetical_total)

            ree_value = hypothetical_total - actual_total
            ree_charges = (Decimal("1") - discount_rate) * (hypothetical_total 
                    - actual_total)
            ree_savings = discount_rate * (hypothetical_total - actual_total)

            present_reebill.set_ree_value_for_service(service, 
                    ree_value.quantize(Decimal('.00')))
            present_reebill.set_ree_charges_for_service(service, ree_charges)
            present_reebill.set_ree_savings_for_service(service, ree_savings)


        # accumulate at the reebill level
        present_reebill.hypothetical_total = present_reebill.hypothetical_total\
                + hypothetical_total
        present_reebill.actual_total = present_reebill.actual_total + actual_total

        present_reebill.ree_value = Decimal(present_reebill.ree_value + ree_value).quantize(Decimal('.00'))
        present_reebill.ree_charges = Decimal(present_reebill.ree_charges + ree_charges).quantize(Decimal('.00'), rounding=ROUND_DOWN)
        present_reebill.ree_savings = Decimal(present_reebill.ree_savings + ree_savings).quantize(Decimal('.00'), rounding=ROUND_UP)

        # set late charge, if any (this will be None if the previous bill has
        # not been issued, 0 before the previous bill's due date, and non-0
        # after that)

        # now grab the prior bill and pull values forward
        present_reebill.prior_balance = prior_reebill.balance_due
        present_reebill.balance_forward = present_reebill.prior_balance - present_reebill.payment_received

        lc = self.get_late_charge(session, present_reebill)
        if lc is not None:
            # set late charge and include it in balance_due
            present_reebill.late_charges = lc
            present_reebill.balance_due = present_reebill.balance_forward + \
                    present_reebill.ree_charges + present_reebill.late_charges
        else:
            # ignore late charge
            present_reebill.balance_due = present_reebill.balance_forward + \
                    present_reebill.ree_charges

        # TODO total_adjustment


    def copy_actual_charges(self, reebill):
        for service in reebill.services:
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            reebill.set_hypothetical_chargegroups_for_service(service, actual_chargegroups)

    def pay_bill(self, session, reebill):
        '''Sets the 'payment_received' in 'reebill' to the sum of all payments
        that occurred within the first utility bill's period.'''
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
        originally attached to the reebill). sum_bill() should always be called
        immediately after this one so the bill is updated to its current
        state.'''

        # obtain the last Reebill sequence from the state database
        if reebill.sequence < self.state_db.last_sequence(session,
                reebill.account):
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

        # construct a new reebill from an old one.
        # if we wanted a copy, we would copy the current ReeBill
        # but we don't want a copy, we want a new instance.
        print "C reebill period end is %s" % reebill.period_end
        new_reebill = MongoReebill(reebill)

        print "A reebill period end is %s" % reebill.period_end

        new_period_end, utilbills = state.guess_utilbills_and_end_date(session,
                reebill.account, reebill.period_end)

        print "B reebill period end is %s" % reebill.period_end

        print "******* new period, utilbills is %s " % new_period_end, utilbills
        new_reebill.period_end = new_period_end

        # set discount rate to the instananeous value from MySQL
        new_reebill.discount_rate = self.state_db.discount_rate(session,
                reebill.account)

        # set late charge rate to the instananeous value from MySQL
        new_reebill.late_charge_rate = self.state_db.late_charge_rate(session,
                reebill.account)

        # NOTE suspended_services list is carried over automatically

        # create reebill row in state database
        self.state_db.new_rebill(session, new_reebill.account, new_reebill.sequence)

        return new_reebill


    def get_late_charge(self, session, reebill, day=date.today()):
        '''Returns the late charge for the given reebill on 'day', which is the
        present by default. ('day' will only affect the result for a bill that
        hasn't been issued yet: there is a late fee applied to the balance of
        the previous bill when only when that previous bill's due date has
        passed.) Late fees only apply to bills whose predecessor has been
        issued; None is returned if the predecessor has not been issued. (The
        first bill and the sequence 0 template bill always have a late charge
        of 0.)'''
        if reebill.sequence <= 1:
            return Decimal(0)

        # ensure that a large charge rate exists in the reebill
        # if not, do not process a late_charge_rate (treat as zero)
        try: 
            reebill.late_charge_rate
        except KeyError:
            return None

        if not self.state_db.is_issued(session, reebill.account,
                reebill.sequence - 1):
            return None

        # late fee is 0 if previous bill is not overdue
        predecessor = self.reebill_dao.load_reebill(reebill.account,
                reebill.sequence - 1)
        if day <= predecessor.due_date:
            return Decimal(0)

        outstanding_balance = self.get_outstanding_balance(session,
                reebill.account, reebill.sequence - 1)
        return (reebill.late_charge_rate) * outstanding_balance

    def get_outstanding_balance(self, session, account, sequence=None):
        '''Returns the balance due of the reebill given by account and sequence
        (or the account's last issued reebill when 'sequence' is not given)
        minus the sum of all payments that have been made since that bill was
        issued. Returns 0 if total payments since the issue date exceed the
        balance due, or if no reebill has ever been issued for the customer.'''
        # get balance due of last reebill
        if sequence == None:
            sequence = self.state_db.last_sequence(session, account)
        if sequence == 0:
            return Decimal(0)
        reebill = self.reebill_dao.load_reebill(account, sequence)

        if reebill.issue_date == None:
            return Decimal(0)

        # get sum of all payments since the last bill was issued
        customer = session.query(Customer).filter(Customer.account==account).one()
        payments = session.query(Payment).filter(Payment.customer==customer)\
                .filter(Payment.date >= reebill.issue_date)
        payment_total = sum(payment.credit for payment in payments.all())

        # result cannot be negative
        return max(Decimal(0), reebill.balance_due - payment_total)

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

    def create_new_account(self, session, account, name, discount_rate, late_charge_rate, template_account):

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
        customer = self.new_account(session, name, account, discount_rate, late_charge_rate)

        return customer


    # TODO 21052893: probably want to set up the next reebill here.  Automatically roll?
    def attach_utilbills(self, session, account, sequence):
        '''Creates association between the reebill given by 'account',
        'sequence' and all utilbills belonging to that customer whose entire
        periods are within the reebill's period and whose services are not
        suspended. The utility bills are marked as processed.'''
        reebill = self.reebill_dao.load_reebill(account, sequence)
        self.state_db.attach_utilbills(session, account, sequence,
                reebill.period_begin, reebill.period_end,
                suspended_services=reebill.suspended_services)

    def bind_rate_structure(self, reebill):
            # process the actual charges across all services
            self.bindrs(reebill, self.rate_structure_dao)

    def bindrs(self, reebill, ratestructure_db):
        """This function binds a rate structure against the actual and
        hypothetical charges found in a bill. If and RSI specifies information
        no in the bill, it is added to the bill. If the bill specifies
        information in a charge that is not in the RSI, the charge is left
        untouched."""
        account, sequence = reebill.account, reebill.sequence

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

            # get non-shadow registers in the reebill
            actual_register_readings = reebill.actual_registers(service)

            # copy the quantity of each non-shadow register in the reebill to
            # the corresponding register dictionary in the rate structure
            # ("apply the registers from the reebill to the probable rate structure")
            rate_structure.bind_register_readings(actual_register_readings)

            # get all utility charges from the reebill's utility bill (in the
            # form of a group name -> [list of charges] dictionary). for each
            # charge, find the corresponding rate structure item (the one that
            # matches its "rsi_binding") and copy the values of "description",
            # "quantity", "quantity_units", "rate", and "rate_units" in that
            # RSI to the charge
            # ("process actual charges with non-shadow meter register totals")
            # ("iterate over the charge groups, binding the reebill charges to
            # its associated RSI")
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            for charges in actual_chargegroups.values():
                rate_structure.bind_charges(charges)

            # (original comment "don't have to set this because we modified the
            # actual_chargegroups" is false--we modified the rate structure
            # items, but left the charges in the bill unchanged. as far as i
            # can tell this line of code has no effect)
            reebill.set_actual_chargegroups_for_service(service, actual_chargegroups)


            # hypothetical charges

            # "re-load rate structure" (doesn't this clear out all the changes above?)
            rate_structure = self.rate_structure_dao.load_rate_structure(reebill, service)

            # get shadow and non-shadow registers in the reebill
            actual_register_readings = reebill.actual_registers(service)
            shadow_register_readings = reebill.shadow_registers(service)

            # "add the shadow register totals to the actual register, and re-process"

            # TODO: 12205265 Big problem here.... if REG_TOTAL, for example, is used to calculate
            # a rate shown on the utility bill, it works - until REG_TOTAL has the shadow
            # renewable energy - then the rate is calculated incorrectly.  This is because
            # a seemingly innocent expression like SETF 2.22/REG_TOTAL.quantity calcs 
            # one way for actual charge computation and another way for hypothetical charge
            # computation.

            # for each shadow register dictionary: add its quantity to the
            # quantity of the corresponding non-shadow register
            registers_to_bind = copy.deepcopy(shadow_register_readings)
            for shadow_reading in registers_to_bind:
                for actual_reading in actual_register_readings:
                    if actual_reading['identifier'] == shadow_reading['identifier']:
                        shadow_reading['quantity'] += actual_reading['quantity']
                # TODO: throw exception when registers mismatch

            # copy the quantity of each register dictionary in the reebill to
            # the corresponding register dictionary in the rate structure
            # ("apply the combined registers from the reebill to the probable
            # rate structure")
            rate_structure.bind_register_readings(registers_to_bind)

            # for each hypothetical charge in the reebill, copy the values of
            # "description", "quantity", "quantity_units", "rate", and
            # "rate_units" from the corresponding rate structure item to the
            # charge
            # ("process hypothetical charges with shadow and non-shadow meter register totals")
            # ("iterate over the charge groups, binding the reebill charges to its associated RSI")
            hypothetical_chargegroups = reebill.hypothetical_chargegroups_for_service(service)
            for chargegroup, charges in hypothetical_chargegroups.items():
                rate_structure.bind_charges(charges)

            # don't have to set this because we modified the hypothetical_chargegroups
            #reebill.set_hypothetical_chargegroups_for_service(service, hypothetical_chargegroups)

            # NOTE that the reebill has not been modified at all


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

            # get month of first billing date
            first_bill_date = self.reebill_dao \
                    .get_first_bill_date_for_account(reebill.account)
            first_bill_year = first_bill_date.year
            first_bill_month = first_bill_date.month

            # get month of "install commissioned"
            commissioned_year = install.install_commissioned.year
            commissioned_month = install.install_commissioned.month

            for year, month in dateutils.months_of_past_year(bill_year, bill_month):
                # the graph shows 0 energy for months before the first bill
                # month or the install_commissioned month, whichever is later,
                # even if data were collected during that time. however, the
                # graph shows ALL the renewable energy sold during the first
                # month, including energy sold before the start of the first
                # billing period or the install_commissioned date.
                if (year, month) < max((commissioned_year, commissioned_month),
                        (first_bill_year, first_bill_month)):
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
                    try:
                        renewable_energy_btus = self.monguru.get_data_for_month(
                                install, year, month).energy_sold
                    except Exception as e:
                        print >> sys.stderr, 'Missing olap document for %s, %s-%s: skipped, but the graph will be wrong'
                        renewable_energy_btus = 0

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

    def issue(self, session, account, sequence,
            issue_date=datetime.date.today()):
        '''Sets the issue date of the reebill given by account, sequence to
        'issue_date' (or today by default) and the due date to 30 days from the
        issue date. The reebill's late charge is set to its permanent value in
        mongo, and the reebill is marked as issued in the state database.'''
        # set issue date and due date in mongo
        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.issue_date = issue_date
        # TODO: parameterize for dependence on customer 
        reebill.due_date = issue_date + datetime.timedelta(days=30)

        # set late charge to its final value (payments after this have no
        # effect on late fee)
        # TODO: should this be replaced with a call to sum_bill() to just make
        # sure everything is up-to-date before issuing?
        lc = self.get_late_charge(session, reebill)
        if lc is not None:
            reebill.late_charges = lc

        # save in mongo
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
                row['ree_value'] = reebill.ree_value.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['ree_charges'] = reebill.ree_charges.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['actual_charges'] = reebill.actual_total.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['hypothetical_charges'] = reebill.hypothetical_total.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                total_energy_therms = self.total_ree_in_reebill(reebill)\
                        .quantize(Decimal(".0"), rounding=ROUND_HALF_EVEN)
                row['total_energy'] = total_energy_therms
                if total_energy_therms != Decimal(0):
                    row['marginal_rate_therm'] = ((reebill.hypothetical_total -
                            reebill.actual_total)/total_energy_therms)\
                            .quantize(Decimal(".00"),
                            rounding=ROUND_HALF_EVEN)
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
            average_ree_rate = Decimal(0)
            total_energy = self.total_ree_in_reebills(reebills)

            if total_energy != Decimal(0):
                average_ree_rate = (hypothetical_total - actual_total)/total_energy

            row['account'] = account
            row['fullname'] = full_names[i]
            row['ree_charges'] = ree_charges
            row['actual_charges'] = actual_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            row['hypothetical_charges'] = hypothetical_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            row['total_energy'] = total_energy.quantize(Decimal("0"))
            # per therm
            row['average_ree_rate'] = (average_ree_rate).quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
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
        
    def sequences_for_approximate_month(self, session, account, year, month):
        '''Returns a list of sequences of all reebills whose approximate month
        (as determined by dateutils.estimate_month()) is 'month' of 'year', or
        None if the month precedes the approximate month of the first reebill.
        When 'sequence' exceeds the last sequence for the account, bill periods
        are assumed to correspond exactly to calendar months.
        
        This should be the inverse of the mapping from bill periods to months
        provided by estimate_month() when its domain is restricted to months
        that actually have bills.'''
        # get all reebills whose periods contain any days in this month (there
        # should be at most 3)
        next_month_year, next_month = month_offset(year, month, 1)
        reebills = self.reebill_dao.load_reebills_in_period(account,
                start_date=date(year, month, 1),
                end_date=date(next_month_year, next_month, 1))

        # sequences for this month are those of the bills whose approximate
        # month is this month
        sequences_for_month = [r.sequence for r in reebills if
                estimate_month(r.period_begin, r.period_end) == (year, month)]
        
        # if there's at least one sequence, return the list of sequences
        if sequences_for_month != []:
            return sequences_for_month

        # get approximate month of last reebill (return [] if there were never
        # any reebills)
        last_sequence = self.state_db.last_sequence(session, account)
        if last_sequence == 0:
            return []
        last_reebill = self.reebill_dao.load_reebill(account, last_sequence)
        last_reebill_year, last_reebill_month = estimate_month(
                last_reebill.period_begin, last_reebill.period_end)

        # if this month isn't after the last bill month, there are no bill
        # sequences
        if (year, month) <= (last_reebill_year, last_reebill_month):
            return []

        # if (year, month) is after the last bill month, return the sequence
        # determined by counting real months after the approximate month of the
        # last bill (there is only one sequence in this case)
        sequence_offset = month_difference(last_reebill_year,
                last_reebill_month, year, month)
        return [last_sequence + sequence_offset]

    def sequences_in_month(self, session, account, year, month):
        '''Returns a list of sequences of all reebills whose periods contain
        ANY days within the given month. The list is empty if the month
        precedes the period of the account's first issued reebill, or if the
        account has no issued reebills at all. When 'sequence' exceeds the last
        sequence for the account (including un-issued bills in mongo), bill
        periods are assumed to correspond exactly to calendar months. This is
        NOT related to the approximate billing month.'''
        # get all reebills whose periods contain any days in this month, and
        # their sequences (there should be at most 3)
        query_month = Month(year, month)
        sequences_for_month = [r.sequence for r in
                self.reebill_dao.load_reebills_in_period(account,
                start_date=query_month.first, end_date=query_month.last)]
        
        # get sequence of last reebill and the month in which its period ends,
        # which will be useful below
        last_sequence = self.state_db.last_sequence(session, account)

        # if there's at least one sequence, return the list of sequences. but
        # if query_month is the month in which the account's last reebill ends,
        # and that period does not perfectly align with the end of the month,
        # also include the sequence of an additional hypothetical reebill whose
        # period would cover the end of the month.
        if sequences_for_month != []:
            last_end = self.reebill_dao.load_reebill(account,
                    last_sequence).period_end
            if Month(last_end) == query_month and last_end \
                    < (Month(last_end) + 1).first:
                sequences_for_month.append(last_sequence + 1)
            return sequences_for_month

        # if there are no sequences in this month because the query_month
        # precedes the first reebill's start, or there were never any reebills
        # at all, return []
        if last_sequence == 0 or query_month.last < \
                self.reebill_dao.load_reebill(account, 1).period_begin:
            return []

        # now query_month must exceed the month in which the account's last
        # reebill ends. return the sequence determined by counting real months
        # after the approximate month of the last bill (there is only one
        # sequence in this case)
        last_reebill_end = self.reebill_dao.load_reebill(account,
                last_sequence).period_end
        return [last_sequence + (query_month - Month(last_reebill_end))]


if __name__ == '__main__':
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


