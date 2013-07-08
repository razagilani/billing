#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""
import sys
import os  
import copy
import datetime
from datetime import date, datetime, timedelta
import calendar
from optparse import OptionParser
from decimal import *
from sqlalchemy.sql import desc
from sqlalchemy import not_
from sqlalchemy.orm.exc import MultipleResultsFound
import operator
from bson import ObjectId
#
# uuid collides with locals so both the locals and package are renamed
import uuid as UUID
import skyliner
from billing.processing import state
from billing.processing.mongo import MongoReebill
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state, fetch_bill_data
from billing.processing.state import Payment, Customer, UtilBill, ReeBill
from billing.processing.mongo import ReebillDAO
from billing.processing.mongo import float_to_decimal
from billing.util import nexus_util
from billing.util import dateutils
from billing.util.dateutils import estimate_month, month_offset, month_difference, date_to_datetime
from billing.util.monthmath import Month, approximate_month
from billing.util.dictutils import deep_map
from billing.processing.exceptions import IssuedBillError, NotIssuable, NotAttachable, BillStateError, NoSuchBillException, NotUniqueException

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint
sys.stdout = sys.stderr

# number of days allowed between two non-Hypothetical utility bills before
# Hypothetical utility bills will be added between them.
# this was added to make the behavior of "hypothetical" utility bills less
# irritating, but really, they should never exist or at least never be stored
# in the database as if they were actual bills.
# see https://www.pivotaltracker.com/story/show/30083239
MAX_GAP_DAYS = 10

class Process(object):
    """ Class with a variety of utility procedures for processing bills.
        The idea here is that this class is instantiated with the data
        access objects it needs, and then ReeBills (why not just references
        to them?) are passed in and returned.  
    """

    config = None
    
    def __init__(self, state_db, reebill_dao, rate_structure_dao, billupload,
            nexus_util, splinter=None, logger=None):
        '''If 'splinter' is not none, Skyline back-end should be used.'''
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        self.reebill_dao = reebill_dao
        self.billupload = billupload
        self.nexus_util = nexus_util
        self.splinter = splinter
        self.monguru = None if splinter is None else splinter.get_monguru()
        self.logger = logger

    def new_account(self, session, name, account, discount_rate, late_charge_rate):
        new_customer = Customer(name, account, discount_rate, late_charge_rate)
        session.add(new_customer)
        return new_customer

    def upload_utility_bill(self, session, account, service, begin_date,
            end_date, bill_file, file_name, total=0, state=UtilBill.Complete):
        '''Uploads 'bill_file' with the name 'file_name' as a utility bill for
        the given account, service, and dates. If the upload succeeds, a row is
        added to the utilbill table in MySQL and a document is added in Mongo
        (based on a previous bill or the template). If this is the newest or
        oldest utility bill for the given account and service, "estimated"
        utility bills will be added to cover the gap between this bill's period
        and the previous newest or oldest one respectively. The total of all
        charges on the utility bill may be given.'''
        if end_date <= begin_date:
            raise ValueError("Start date %s must precede end date %s" %
                    (begin_date, end_date))
        if end_date - begin_date > timedelta(days=365):
            raise ValueError(("Utility bill period %s to %s is longer than "
                "1 year") % (start, end))
        if bill_file is None and state in (UtilBill.UtilityEstimated,
                UtilBill.Complete):
            raise ValueError(("Bill file is required for a complete or "
                    "utility-estimated utility bill"))
        if bill_file is not None and state in (UtilBill.Hypothetical,
                UtilBill.SkylineEstimated):
            raise ValueError("Hypothetical or Skyline-estimated utility bills "
                    "can't have file")

        # NOTE 'total' does not yet go into the utility bill document in Mongo

        # get & save end date of last bill (before uploading a new bill which
        # may come later)
        original_last_end = self.state_db.last_utilbill_end_date(session,
                account)

        # find an existing utility bill that will provide rate class and
        # utility name for the new one, or get it from the template.
        # note that it doesn't matter if this is wrong because the user can
        # edit it after uploading.
        # TODO get utility name and rate class as arguments instead of from
        # template: see https://www.pivotaltracker.com/story/show/52495771
        try:
            predecessor = self.state_db.get_last_real_utilbill(session,
                    account, begin_date, service=service)
            rate_class = predecessor.rate_class
            utility = predecessor.utility
        except NoSuchBillException:
            template = self.reebill_dao.load_utilbill_template(session, account)
            rate_class = template['rate_structure_binding']
            utility = template['utility']

        if bill_file is not None:
            # if there is a file, get the Python file object and name
            # string from CherryPy, and pass those to BillUpload to upload
            # the file (so BillUpload can stay independent of CherryPy)
            upload_result = self.billupload.upload(account, begin_date,
                    end_date, bill_file, file_name)
            if not upload_result:
                raise IOError('File upload failed: %s %s %s' % (file_name,
                    begin_date, end_date))

        # record the bill in state DB
        self.record_utilbill_in_database(session, account, utility,
                service, rate_class, begin_date, end_date, total,
                date_received=datetime.utcnow().date(),
                state=state)

        # if begin_date does not match end date of latest existing bill, create
        # hypothetical bills to cover the gap
        # NOTE hypothetical bills are not created if the gap is small enough
        if original_last_end is not None and begin_date > original_last_end \
                and begin_date - original_last_end > \
                timedelta(days=MAX_GAP_DAYS):
            self.state_db.fill_in_hypothetical_utilbills(session, account,
                    service, utility, rate_class, original_last_end,
                    begin_date)

    def record_utilbill_in_database(self, session, account, utility, service,
            rate_class, begin_date, end_date, total_charges, date_received,
            state=UtilBill.Complete):
        '''Inserts a row into the utilbill table when a utility bill file has
        been uploaded. The bill is Complete by default but can can have other
        states (see comment in state.UtilBill for explanation of utility
        bill states). The bill is initially marked as un-processed.'''
        # get customer id from account number
        customer = session.query(Customer).filter(Customer.account==account) \
                .one()

        # get existing bills matching dates and service
        # (there should be at most one, but you never know)
        existing_bills = session.query(UtilBill) \
                .filter(UtilBill.customer_id==customer.id) \
                .filter(UtilBill.service==service) \
                .filter(UtilBill.period_start==begin_date) \
                .filter(UtilBill.period_end==end_date)

        if list(existing_bills) == []:
            # nothing to replace; just upload the bill

            self.create_new_utility_bill(session, account, utility, service,
                    rate_class, begin_date, end_date, total=total_charges,
                    state=state)

        elif len(list(existing_bills)) > 1:
            raise NotUniqueException(("Can't upload a bill for dates %s, %s because"
                    " there are already %s of them") % (begin_date, end_date,
                    len(list(existing_bills))))
        else:
            # now there is one existing bill with the same dates. if state is
            # "more final" than an existing non-final bill that matches this
            # one, replace that bill
            # TODO 38385969: is this really a good idea?
            # (we can compare with '>' because states are ordered from "most
            # final" to least (see state.UtilBill)
            bills_to_replace = existing_bills.filter(UtilBill.state > state)

            if list(bills_to_replace) == []:
                # TODO this error message is kind of obscure
                raise NotUniqueException(("Can't upload a utility bill for "
                    "dates %s, %s because one already exists with a more final"
                    " state than %s") % (begin_date, end_date, state))
                    
            bill_to_replace = bills_to_replace.one()
                
            # now there is exactly one bill with the same dates and its state is
            # less final than the one being uploaded, so replace it.
            session.delete(bill_to_replace)
            self.create_new_utility_bill(session, account, utility, service,
                    rate_class, begin_date, end_date, total=total_charges,
                    state=state)


    def delete_utility_bill(self, session, utilbill_id):
        '''Deletes the utility bill given by its MySQL id 'utilbill_id' (if
        it's not attached to a reebill) and returns the path where the file was
        moved (it never really gets deleted). This path will be None if there
        was no file or it could not be found. Raises a ValueError if the
        utility bill cannot be deleted.'''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        if utilbill.is_attached():
            raise ValueError("Can't delete an attached utility bill.")

        # OK to delete now.
        # first try to delete the file on disk
        try:
            new_path = self.billupload.delete_utilbill_file(
                    utilbill.customer.account, utilbill.period_start,
                    utilbill.period_end)
        except IOError:
            # file never existed or could not be found
            new_path = None

        # delete from MySQL
        # TODO move to StateDB?
        session.delete(utilbill)

        # delete from Mongo
        self.reebill_dao.delete_doc_for_statedb_utilbill(utilbill)

        return new_path


    def compute_bill(self, session, prior_reebill, present_reebill):
        '''Compute everything about the bill that can be continuously
        recomputed. This should be called immediately after roll_bill()
        whenever roll_bill() is called.'''
        acc = present_reebill.account

        # replace "utilbills" sub-documents of reebill document with new ones
        # generated directly from the reebill's '_utilbills'. these will
        # contain hypothetical charges that matche the actual charges until
        # updated.
        present_reebill.update_utilbill_subdocs()

        ## "TODO: 22726549 hack to ensure the computations from bind_rs come back as decimal types"
        present_reebill.reebill_dict = deep_map(float_to_decimal, present_reebill.reebill_dict)
        present_reebill._utilbills = [deep_map(float_to_decimal, u) for u in
                present_reebill._utilbills]

        # get MySQL reebill row corresponding to the document 'present_reebill'
        # (would be better to pass in the state.ReeBill itself: see
        # https://www.pivotaltracker.com/story/show/51922065)
        customer = self.state_db.get_customer(session, present_reebill.account)
        reebill_row = session.query(ReeBill)\
                .filter(ReeBill.customer == customer)\
                .filter(ReeBill.sequence == present_reebill.sequence)\
                .filter(ReeBill.version == present_reebill.version).one()
        for utilbill in reebill_row.utilbills:
            rs = self.rate_structure_dao.load_rate_structure(utilbill)
            self.bind_rate_structure(present_reebill, rs)

        ## TODO: 22726549 hack to ensure the computations from bind_rs come back as decimal types
        present_reebill.reebill_dict = deep_map(float_to_decimal, present_reebill.reebill_dict)
        present_reebill._utilbills = [deep_map(float_to_decimal, u) for u in
                present_reebill._utilbills]

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

            for chargegroup, charges in present_reebill.\
                    hypothetical_chargegroups_for_service(service).items():
                hypothetical_subtotal = Decimal("0")
                for charge in charges:
                    hypothetical_subtotal += charge["total"]
                    hypothetical_total += charge["total"]

            # calculate utilbill level numbers
            present_reebill.set_actual_total_for_service(service, actual_total)
            present_reebill.set_hypothetical_total_for_service(service,
                    hypothetical_total)

            ree_value = hypothetical_total - actual_total
            ree_charges = (Decimal("1") - present_reebill.discount_rate) * \
                    (hypothetical_total - actual_total)
            ree_savings = present_reebill.discount_rate * (hypothetical_total -
                    actual_total)

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

        # compute adjustment: this bill only gets an adjustment if it's the
        # earliest unissued version-0 bill, i.e. it meets 2 criteria:
        # (1) it's a version-0 bill, not a correction
        # (2) at least the 0th version of its predecessor has been issued (it
        #     may have an unissued correction; if so, that correction will
        #     contribute to the adjustment on this bill)
        if prior_reebill is not None and present_reebill == 0 \
                and self.state_db.is_issued(session, prior_reebill.account,
                prior_reebill.sequence, version=0, nonexistent=False):
            present_reebill.total_adjustment = self.get_total_adjustment(
                    session, present_reebill.account)
        else:
            present_reebill.total_adjustment = Decimal(0)

        if prior_reebill == None:
            # this is the first reebill
            assert present_reebill.sequence == 1

            # include all payments since the beginning of time, in case there
            # happen to be any.
            # if any version of this bill has been issued, get payments up
            # until the issue date; otherwise get payments up until the
            # present.
            present_v0_issue_date = self.reebill_dao.load_reebill(acc,
                    present_reebill.sequence, version=0).issue_date
            if present_v0_issue_date is None:
                present_reebill.payment_received = self.state_db.\
                        get_total_payment_since(session, acc,
                        state.MYSQLDB_DATETIME_MIN)
            else:
                present_reebill.payment_received = self.state_db.\
                        get_total_payment_since(session, acc,
                        state.MYSQLDB_DATETIME_MIN,
                        end=present_v0_issue_date)
            # obviously balances are 0
            present_reebill.prior_balance = Decimal(0)
            present_reebill.balance_forward = Decimal(0)

            # NOTE 'calculate_statistics' is not called because statistics
            # section should already be zeroed out
        else:
            # calculations that depend on 'prior_reebill' go here.
            assert present_reebill.sequence > 1

            # get payment_received: all payments between issue date of
            # predecessor's version 0 and issue date of current reebill's version 0
            # (if current reebill is unissued, its version 0 has None as its
            # issue_date, meaning the payment period lasts up until the present)
            if self.state_db.is_issued(session, acc,
                    prior_reebill.sequence, version=0, nonexistent=False):
                # if predecessor's version 0 is issued, gather all payments from
                # its issue date until version 0 issue date of current bill, or
                # today if this bill has never been issued
                if self.state_db.is_issued(session, acc, present_reebill.sequence,
                        version=0):
                    prior_v0_issue_date = self.reebill_dao.load_reebill(acc,
                            prior_reebill.sequence, version=0).issue_date
                    present_v0_issue_date = self.reebill_dao.load_reebill(acc,
                            present_reebill.sequence, version=0).issue_date
                    present_reebill.payment_received = self.state_db.\
                            get_total_payment_since(session, acc,
                            prior_v0_issue_date,
                            end=present_v0_issue_date)
                else:
                    present_reebill.payment_received = self.state_db.\
                            get_total_payment_since(session, acc,
                            prior_reebill.issue_date)
            else:
                # if predecessor is not issued, there's no way to tell what
                # payments will go in this bill instead of a previous bill, so
                # assume there are none (all payments since last issue date go in
                # the account's first unissued bill)
                present_reebill.payment_received = Decimal(0)

                present_reebill.prior_balance = prior_reebill.balance_due
                present_reebill.balance_forward = prior_reebill.balance_due - \
                        present_reebill.payment_received + \
                        present_reebill.total_adjustment
            self.calculate_statistics(prior_reebill, present_reebill)

        # include manually applied adjustment
        present_reebill.balance_forward += present_reebill.manual_adjustment

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

        ## TODO: 22726549  hack to ensure the computations from bind_rs come
        # back as decimal types
        present_reebill.reebill_dict = deep_map(float_to_decimal,
                present_reebill.reebill_dict)
        present_reebill._utilbills = [deep_map(float_to_decimal, u) for u in
                present_reebill._utilbills]
        


    def copy_actual_charges(self, reebill):
        for service in reebill.services:
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            reebill.set_hypothetical_chargegroups_for_service(service, actual_chargegroups)

    #def roll_bill(self, session, reebill, utility_bill_date=None):
        #'''Modifies 'reebill' to convert it into a template for the reebill of
        #the next period (including incrementing the sequence). 'reebill' must
        #be its customer's last bill before roll_bill is called. This method
        #does not save the reebill in Mongo, but it DOES create new CPRS
        #documents in Mongo (by copying the ones originally attached to the
        #reebill). compute_bill() should always be called immediately after this
        #one so the bill is updated to its current state.'''
        #if utility_bill_date:
            #utilbills = self.state_db.get_utilbills_on_date(session,
                    #reebill.account, utility_bill_date)
        #else:
            #utilbills = self.state_db.choose_next_utilbills(session,
                    #reebill.account, reebill.services)
        
        ## "TODO Put somewhere nice because this has a specific function"--ST
        ## what does this do? nothing? ('reebill.services' itself looks at
        ## utility bills' "service" keys)--DK
        #active_utilbills = [u for u in reebill._utilbills if u['service'] in
                #reebill.services]
        #reebill.reebill_dict['utilbills'] = [handle for handle in
                #reebill.reebill_dict['utilbills'] if handle['id'] in [u['_id']
                #for u in active_utilbills]]

        ## construct a new reebill from an old one. the new one's version is
        ## always 0 even if it was created from a non-0 version of the old one.
        #reebill.new_utilbill_ids()
        #new_reebill = MongoReebill(reebill.reebill_dict, active_utilbills)
        #new_reebill.version = 0
        #new_reebill.new_utilbill_ids()
        #new_reebill.clear()
        #new_reebill.sequence += 1
        ## Update the new reebill's periods to the periods identified in the StateDB
        #for ub in utilbills:
            #new_reebill.set_utilbill_period_for_service(ub.service,
                    #(ub.period_start, ub.period_end))
        #new_reebill.set_meter_dates_from_utilbills()


        #def ignore_function(uprs):
            ## ignore UPRSs of un-attached utility bills, and utility bills whose
            ## reebill sequence is 0, which are meaningless
            #if 'sequence' not in uprs['_id'] or uprs['_id']['sequence'] == 0:
                #return True

            ### ignore UPRSs whose utility bills are attached to un-issued
            ### reebills
            ##if not self.state_db.is_issued(session, uprs['_id']['account'],
                    ##uprs['_id']['sequence']):
                ##return True

            ## ignore UPRSs belonging to a utility bill whose reebill version is
            ## less than the maximum version (because they may be wrong, and to
            ## prevent multiple-counting)
            #if self.state_db.max_version(session, uprs['_id']['account'],
                    #uprs['_id']['sequence']):
                #return True

            #return False

        ## for each utility bill, duplicate the CPRS, generate a predicted UPRS,
        ## and remove any charges that were in the previous bill but are not in
        ## the new bill's UPRS
        ## TODO: 22597151 refactor

        ## TODO: this doesn't work for sequence 0
        #reebill_row = self.state_db.get_reebill(session, reebill.account,
                #reebill.sequence, reebill.version)
        #for utilbill_row in reebill_row.utilbills:
            #utility_name = new_reebill.utility_name_for_service(service)
            #rate_structure_name = reebill.rate_structure_name_for_service(service)

            ## load previous CPRS, save it with same account, next sequence, version 0
            #cprs = self.rate_structure_dao.load_cprs(utilbill_row.cprs_document_id)
            #cprs['_id'] = ObjectId()
            #self.rate_structure_dao.save_rs(cprs)

            ## generate predicted UPRS, save it with account, sequence, version 0
            #uprs = self.rate_structure_dao.get_probable_uprs(new_reebill,
                    #service, ignore=ignore_function)
            #if uprs is None:
                #raise NoRateStructureError("No current UPRS")
            #self.rate_structure_dao.save_uprs(new_reebill.account, new_reebill.sequence,
                    #0, utility_name, rate_structure_name, uprs)

            ## remove charges that don't correspond to any RSI binding (because
            ## their corresponding RSIs were not part of the predicted rate structure)
            #valid_bindings = {rsi['rsi_binding']: False for rsi in uprs['rates'] +
                    #cprs['rates']}
            #actual_chargegroups = new_reebill._get_utilbill_for_service(
                    #service)['chargegroups']
            #hypothetical_chargegroups = new_reebill._get_handle_for_service(
                    #service)['hypothetical_chargegroups']
            #for whichever_chargegroups in [actual_chargegroups,
                    #hypothetical_chargegroups]:
                #for group, charges in whichever_chargegroups.iteritems():
                    #for charge in charges:
                        ## if the charge matches a valid RSI binding, mark that
                        ## binding as matched; if not, delete the charge
                        #if charge['rsi_binding'] in valid_bindings:
                            #valid_bindings[charge['rsi_binding']] = True
                        #else:
                            #charges.remove(charge)
                ## NOTE empty chargegroup is not removed because the user might
                ## want to add charges to it again

            ## TODO add a charge for every RSI that doesn't have a charge, i.e.
            ## the ones whose value in 'valid_bindings' is False.
            ## we can't do this yet because we don't know what group it goes in.
            ## see https://www.pivotaltracker.com/story/show/43797365


        ## set discount rate & late charge rate to the instananeous value from MySQL
        ## NOTE suspended_services list is carried over automatically
        #new_reebill.discount_rate = self.state_db.discount_rate(session,
                #reebill.account)
        #new_reebill.late_charge_rate = self.state_db.late_charge_rate(session,
                #reebill.account)

        ##self.reebill_dao.save_reebill(new_reebill)

        ## create reebill row in state database
        #self.state_db.new_reebill(session, new_reebill.account,
                #new_reebill.sequence)
        #self.attach_utilbills(session, new_reebill, utilbills)        
        
        #return new_reebill

    def create_first_reebill(self, session, utilbill):
        '''Create and save the account's first reebill (in Mongo and MySQL),
        based on the given state.UtilBill.'''
        customer = utilbill.customer

        # make sure there are no reebills yet
        num_existing_reebills = session.query(ReeBill).join(Customer)\
                .filter(ReeBill.customer==customer).count()
        if num_existing_reebills > 0:
            raise ValueError("%s reebill(s) already exist for account %s" %
                    (num_existing_reebills, customer.account))
        
        # load document for the 'utilbill', use it to create the reebill
        # document, and save the reebill document
        utilbill_doc = self.reebill_dao.load_doc_for_statedb_utilbill(utilbill)
        reebill_doc = MongoReebill.get_reebill_doc_for_utilbills(
                utilbill.customer.account, 1, 0, customer.discountrate,
                utilbill.customer.latechargerate, [utilbill_doc])
        self.reebill_dao.save_reebill(reebill_doc)

        # add row in MySQL
        session.add(ReeBill(customer, 1, version=0, utilbills=[utilbill]))


    def create_next_reebill(self, session, account):
        '''Creates the successor to the highest-sequence state.ReeBill for
        the given account, and its associated Mongo document.'''
        customer = session.query(Customer)\
                .filter(Customer.account == account).one()
        last_reebill_row = session.query(ReeBill)\
                .filter(ReeBill.customer == customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version)).first()

        # find successor to every utility bill belonging to the reebill, along
        # with its mongo document. note theat this includes Hypothetical
        # utility bills.
        # NOTE as far as i know, you can't filter SQLAlchemy objects by methods
        # or by properties that do not correspond to db columns. so, there is
        # no way to tell if a utility bill has reebills except by filtering
        # _utilbill_reebills.
        # see 
        new_utilbills, new_utilbill_docs = [], []
        for utilbill in last_reebill_row.utilbills:
            successor = session.query(UtilBill)\
                .filter(UtilBill.customer == customer)\
                .filter(not_(UtilBill._utilbill_reebills.any()))\
                .filter(UtilBill.service == utilbill.service)\
                .filter(UtilBill.utility == utilbill.utility)\
                .filter(UtilBill.period_start >= utilbill.period_end)\
                .order_by(UtilBill.period_end).first()
            if successor == None:
                raise NoSuchBillException(("Couldn't find an unattached "
                "successor to %s") % utilbill)
            new_utilbills.append(successor)
            new_utilbill_docs.append(
                    self.reebill_dao.load_doc_for_statedb_utilbill(successor))

        # currently only one service is supported
        assert len(new_utilbills) == 1

        # create mongo document for the new reebill, based on the documents for
        # the utility bills. discount rate and late charge rate are set to the
        # "current" values for the customer in MySQL. the sequence is 1 greater
        # than the predecessor's and the version is always 0.
        new_mongo_reebill = MongoReebill.get_reebill_doc_for_utilbills(account,
                last_reebill_row.sequence + 1, 0, customer.discountrate,
                customer.latechargerate, new_utilbill_docs)

        # copy 'suspended_services' list from predecessor reebill's document
        last_reebill_doc = self.reebill_dao.load_reebill(account,
                last_reebill_row.sequence, last_reebill_row.version)
        assert all(new_mongo_reebill.suspend_service(s) for s in
                last_reebill_doc.suspended_services)

        # create reebill row in state database
        session.add(ReeBill(customer, new_mongo_reebill.sequence,
                new_mongo_reebill.version, utilbills=new_utilbills))

        # save reebill document in Mongo
        self.reebill_dao.save_reebill(new_mongo_reebill)


    def create_new_utility_bill(self, session, account, utility, service,
            rate_class, start, end, total=0, state=UtilBill.Complete):
        '''Creates a new utility bill based on the state.UtilBill
        'predecessor', with period dates 'start', 'end'. (This is the
        lowest-level method for creating utility bills; it's called called by
        record_utilbill_in_database, which is called by upload_utility_bill)'''
#        def ignore_function(uprs):
#            # ignore UPRSs of un-attached utility bills, and utility bills whose
#            # reebill sequence is 0, which are meaningless
#            if 'sequence' not in uprs['_id'] or uprs['_id']['sequence'] == 0:
#                return True
#            # ignore UPRSs belonging to a utility bill whose reebill version is
#            # less than the maximum version (because they may be wrong, and to
#            # prevent multiple-counting)
#            if self.state_db.max_version(session, uprs['_id']['account'],
#                    uprs['_id']['sequence']):
#                return True
#            return False
        ignore_function = lambda uprs: False

        # look for the last utility bill with the same account, service, and
        # rate class, (i.e. the last-ending before 'end'), ignoring
        # Hypothetical ones. copy its mongo document and CPRS.
        # TODO pass this predecessor in from upload_utility_bill?
        # see https://www.pivotaltracker.com/story/show/51749487
        try:
            predecessor = self.state_db.get_last_real_utilbill(session, account,
                    end, service=service, utility=utility, rate_class=rate_class)
            doc = self.reebill_dao.load_doc_for_statedb_utilbill(predecessor)
            cprs = self.rate_structure_dao.load_cprs_for_utilbill(predecessor)
            cprs['_id'] = ObjectId()
        except NoSuchBillException:
            # if this is the first bill ever for the account (or all the
            # existing ones are Hypothetical), use template for the utility
            # bill document, and create new empty CPRS
            doc = self.reebill_dao.load_utilbill_template(session, account)
            # template document should have the same service/utility/rate class
            # as this one; multiple services are not supported since there
            # would need to be more than one template
            assert doc['service'] == service
            assert doc['utility'] == utility
            assert doc['rate_structure_binding'] == rate_class
            cprs = {'_id': ObjectId(), 'type': 'CPRS', 'rates': []}
        doc.update({
            '_id': ObjectId(),
            'start': date_to_datetime(start),
            'end': date_to_datetime(end),
             # update the document's "account" field just in case it's wrong or
             # two accounts are sharing the same template document
            'account': account,
        })

        # generate predicted UPRS
        uprs = self.rate_structure_dao.get_probable_uprs(session,
                utility, service, rate_class, start, end,
                ignore=ignore_function)
        uprs['_id'] = ObjectId()

        # remove charges that don't correspond to any RSI binding (because
        # their corresponding RSIs were not part of the predicted rate structure)
        valid_bindings = {rsi['rsi_binding']: False for rsi in uprs['rates'] +
                cprs['rates']}

        for group, charges in doc['chargegroups'].iteritems():
            i = 0
            while i < len(charges):
                charge = charges[i]
                # if the charge matches a valid RSI binding, mark that
                # binding as matched; if not, delete the charge
                if charge['rsi_binding'] in valid_bindings:
                    valid_bindings[charge['rsi_binding']] = True
                    i += 1
                else:
                    charges.pop(i)
            # NOTE empty chargegroup is not removed because the user might
            # want to add charges to it again

        # TODO add a charge for every RSI that doesn't have a charge, i.e.
        # the ones whose value in 'valid_bindings' is False.
        # we can't do this yet because we don't know what group it goes in.
        # see https://www.pivotaltracker.com/story/show/43797365

        # create new row in MySQL
        session.add(UtilBill(self.state_db.get_customer(session, account),
                state, service, utility, rate_class, doc_id=doc['_id'], uprs_id=uprs['_id'],
                cprs_id=cprs['_id'], period_start=start, period_end=end, total_charges=0,
                date_received=datetime.utcnow().date()))

        # save all 3 mongo documents
        self.rate_structure_dao.save_rs(uprs)
        self.rate_structure_dao.save_rs(cprs)
        self.reebill_dao._save_utilbill(doc)

    def new_versions(self, session, account, sequence):
        '''Creates new versions of all reebills for 'account' starting at
        'sequence'. Any reebills that already have an unissued version are
        skipped. Returns a list of the new reebill objects.'''
        sequences = range(sequence, self.state_db.last_sequence(session,
                account) + 1)
        return [self.new_version(session, account, s) for s in sequences if 
                self.state_db.is_issued(session, account, s)]

    def new_version(self, session, account, sequence):
        '''Creates a new version of the given reebill: duplicates the Mongo
        document, re-computes the bill, saves it, and increments the
        max_version number in MySQL. Returns the new reebill object.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()

        if sequence <= 0:
            raise ValueError('Only sequence >= 0 can have multiple versions.')
        if not self.state_db.is_issued(session, account, sequence):
            raise ValueError("Can't create new version of an un-issued bill.")

        # get current max version from MySQL, and load that version's document
        # from Mongo (even if higher version exists in Mongo, it doesn't count
        # unless MySQL knows about it)
        max_version = self.state_db.max_version(session, account, sequence)
        reebill_doc = self.reebill_dao.load_reebill(account, sequence,
                version=max_version)
        reebill_doc.version = max_version + 1

        # increment max version in mysql: this adds a new reebill row with an
        # incremented version number, the same assocation to utility bills but
        # null document_id, uprs_id, and cprs_id in the utilbill_reebill table,
        # meaning its utility bills are the current ones.
        reebill = self.state_db.increment_version(session, account, sequence)

        # replace utility bill documents with the "current" ones
        # (note that utility bill subdocuments in the reebill get updated in
        # 'compute_bill' below)
        reebill_doc._utilbills = [self.reebill_dao.load_doc_for_statedb_utilbill(u)
                for u in reebill.utilbills]

        # re-bind and compute
        # recompute, using sequence predecessor to compute balance forward and
        # prior balance. this is always version 0, because we want those values
        # to be the same as they were on version 0 of this bill--we don't care
        # about any corrections that might have been made to that bill later.
        fetch_bill_data.fetch_oltp_data(self.splinter,
                self.nexus_util.olap_id(account), reebill_doc)
        predecessor = self.reebill_dao.load_reebill(account, sequence-1,
                version=0) if sequence > 1 else None
        self.compute_bill(session, predecessor, reebill_doc)

        # save in mongo
        self.reebill_dao.save_reebill(reebill_doc)

        return reebill_doc

    def get_unissued_corrections(self, session, account):
        '''Returns [(sequence, max_version, balance adjustment)] of all
        un-issued versions of reebills > 0 for the given account.'''
        result = []
        for seq, max_version in self.state_db.get_unissued_corrections(session,
                account):
            # adjustment is difference between latest version's
            # charges and the previous version's
            latest_version = self.reebill_dao.load_reebill(account, seq,
                    version=max_version)
            prev_version = self.reebill_dao.load_reebill(account, seq,
                    max_version-1)
            adjustment = latest_version.total - prev_version.total
            result.append((seq, max_version, adjustment))
        return result

    def get_unissued_correction_sequences(self, session, account):
        return [c[0] for c in self.get_unissued_corrections(session, account)]

    def issue_corrections(self, session, account, target_sequence):
        '''Applies adjustments from all unissued corrections for 'account' to
        the reebill given by 'target_sequence', and marks the corrections as
        issued.'''
        # corrections can only be applied to an un-issued reebill whose version
        # is 0
        target_max_version = self.state_db.max_version(session, account,
                target_sequence)
        if self.state_db.is_issued(session, account, target_sequence) \
                or target_max_version > 0:
            raise ValueError(("Can't apply corrections to %s-%s, "
                    "because the latter is an issued reebill or another "
                    "correction.") % (account, target_sequence))
        all_unissued_corrections = self.get_unissued_corrections(session,
                account)
        if len(all_unissued_corrections) == 0:
            raise ValueError('%s has no corrections to apply' % account)
        
        # load target reebill from mongo (and, for recomputation, version 0 of
        # its predecessor)
        target_reebill = self.reebill_dao.load_reebill(account,
                target_sequence, version=target_max_version)
        target_reebill_predecessor = self.reebill_dao.load_reebill(account,
                target_sequence - 1, version=0)

        # recompute target reebill (this sets total adjustment) and save it
        self.compute_bill(session, target_reebill_predecessor, target_reebill)
        self.reebill_dao.save_reebill(target_reebill)

        # issue each correction
        for correction in all_unissued_corrections:
            correction_sequence, _, _ = correction
            self.issue(session, account, correction_sequence)

    def get_total_adjustment(self, session, account):
        '''Returns total adjustment that should be applied to the next issued
        reebill for 'account' (i.e. the earliest unissued version-0 reebill).
        This adjustment is the sum of differences in totals between each
        unissued correction and the previous version it corrects.'''
        return Decimal(sum(adjustment for (sequence, version, adjustment) in
                self.get_unissued_corrections(session, account)))

    def get_total_error(self, session, account, sequence):
        '''Returns the net difference between the total of the latest
        version (issued or not) and version 0 of the reebill given by account,
        sequence.'''
        earliest = self.reebill_dao.load_reebill(account, sequence, version=0)
        latest = self.reebill_dao.load_reebill(account, sequence, 'max')
        return latest.total - earliest.total

    def get_late_charge(self, session, reebill,
            day=datetime.utcnow().date()):
        '''Returns the late charge for the given reebill on 'day', which is the
        present by default. ('day' will only affect the result for a bill that
        hasn't been issued yet: there is a late fee applied to the balance of
        the previous bill when only when that previous bill's due date has
        passed.) Late fees only apply to bills whose predecessor has been
        issued; None is returned if the predecessor has not been issued. (The
        first bill and the sequence 0 template bill always have a late charge
        of 0.)'''
        acc, seq = reebill.account, reebill.sequence

        if reebill.sequence <= 1:
            return Decimal(0)

        # ensure that a large charge rate exists in the reebill
        # if not, do not process a late_charge_rate (treat as zero)
        try: 
            reebill.late_charge_rate
        except KeyError:
            return None

        # unissued bill has no late charge
        if not self.state_db.is_issued(session, acc, seq - 1):
            return None

        # late charge is 0 if version 0 of the previous bill is not overdue
        predecessor0 = self.reebill_dao.load_reebill(acc, seq - 1, version=0)
        if day <= predecessor0.due_date:
            return Decimal(0)

        # the balance on which a late charge is based is not necessarily the
        # current bill's balance_forward or the "outstanding balance": it's the
        # least balance_due of any issued version of the predecessor (as if it
        # had been charged on version 0's issue date, even if the version
        # chosen is not 0).
        max_predecessor_version = self.state_db.max_version(session, acc,
                seq - 1)
        min_balance_due = min((self.reebill_dao.load_reebill(acc, seq - 1,
                version=v) for v in range(max_predecessor_version + 1)),
                key=operator.attrgetter('balance_due')).balance_due
        source_balance = min_balance_due - \
                self.state_db.get_total_payment_since(session, acc,
                predecessor0.issue_date)
        #Late charges can only be positive
        return (reebill.late_charge_rate) * max(0, source_balance)

    def get_outstanding_balance(self, session, account, sequence=None):
        '''Returns the balance due of the reebill given by account and sequence
        (or the account's last issued reebill when 'sequence' is not given)
        minus the sum of all payments that have been made since that bill was
        issued. Returns 0 if total payments since the issue date exceed the
        balance due, or if no reebill has ever been issued for the customer.'''
        # get balance due of last reebill
        if sequence == None:
            sequence = self.state_db.last_issued_sequence(session, account)
        if sequence == 0:
            return Decimal(0)
        reebill = self.reebill_dao.load_reebill(account, sequence)

        if reebill.issue_date == None:
            return Decimal(0)

        # result cannot be negative
        return max(Decimal(0), reebill.balance_due -
                self.state_db.get_total_payment_since(session, account,
                reebill.issue_date))

    def delete_reebill(self, session, account, sequence):
        '''Deletes the latest version of the reebill given by 'account' and
        'sequence': removes state data and utility bill associations from
        MySQL, and actual bill data from Mongo. A reebill that has been issued
        can't be deleted. Returns the version of the reebill that was
        deleted (the highest ersion before deletion).'''
        # don't delete an issued reebill
        if self.state_db.is_issued(session, account, sequence):
            raise IssuedBillError("Can't delete an issued reebill.")

        # delete reebill state data from MySQL and dissociate utilbills from it
        # (save max version first because row may be deleted)
        max_version = self.state_db.max_version(session, account, sequence)
        self.state_db.delete_reebill(session, account, sequence)

        # delete highest-version reebill document from Mongo
        self.reebill_dao.delete_reebill(account, sequence, max_version)

        return max_version


    def create_new_account(self, session, account, name, discount_rate,
            late_charge_rate, template_account):
        '''Returns MySQL Customer object.'''
        # TODO don't roll by copying https://www.pivotaltracker.com/story/show/36805917
        result = self.state_db.account_exists(session, account)
        if result is True:
            raise ValueError("Account exists")

        # create row for new customer in MySQL
        customer = self.new_account(session, name, account, discount_rate,
                late_charge_rate)

        template_last_sequence = self.state_db.last_sequence(session, template_account)

        #TODO 22598787 use the active version of the template_account
        reebill = self.reebill_dao.load_reebill(template_account, template_last_sequence, 0)

        reebill.convert_to_new_account(account)
        # This 'copy' is set to sequence zero which acts as a 'template' 
        reebill.sequence = 0
        reebill.version = 0
        for utilbill in reebill._utilbills:
            utilbill['sequence'] = 0
            utilbill['version'] = 0
        reebill = MongoReebill(reebill.reebill_dict, reebill._utilbills)
        reebill.billing_address = {}
        reebill.service_address = {}
        reebill.bill_recipients = []
        reebill.last_recipients = []
        reebill.late_charge_rate = late_charge_rate

        # reset the reebill's fields to 0/blank/etc.
        reebill.clear()
        reebill.discount_rate = self.state_db.discount_rate(session, account)
        reebill.late_charge_rate = self.state_db.late_charge_rate(session,
                account)

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
            if cprs is None:
                raise ValueError("No current CPRS")

            # save the CPRS for the new reebill
            self.rate_structure_dao.save_cprs(reebill.account, reebill.sequence,
                reebill.version, utility_name, rate_structure_name, cprs)

        return customer


    ## TODO 21052893: probably want to set up the next reebill here.  Automatically roll?
    #def attach_utilbills(self, session, reebill, utilbills):
        #'''Freeze utilbills from the previous reebill into a new reebill.

        #This affects only the Mongo document.'''
        #if self.state_db.is_attached(session, reebill.account, reebill.sequence):
            #raise NotAttachable(("Can't attach reebill %s-%s: it already has utility "
                    #"bill(s) attached") % (reebill.account, reebill.sequence))
        ##reebill = self.reebill_dao.load_reebill(account, sequence)

        ## save in mongo, with frozen copies of the associated utility bill
        ## (the mongo part should normally come last because it can't roll back,
        ## but here it must precede MySQL because ReebillDAO.save_reebill will
        ## refuse to create frozen utility bills "again" if MySQL says its
        ## attached". see https://www.pivotaltracker.com/story/show/38308443)
        #self.state_db.try_to_attach_utilbills(session, reebill.account, reebill.sequence, utilbills, reebill.suspended_services)

        #self.reebill_dao.save_reebill(reebill)
        #self.reebill_dao.save_reebill(reebill, freeze_utilbills=True)

        #self.state_db.attach_utilbills(session, reebill.account, reebill.sequence, utilbills, reebill.suspended_services)

    def bind_rate_structure(self, reebill, the_rate_structure):
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

            # copy rate structure because it gets destroyed during use
            rate_structure = copy.deepcopy(the_rate_structure)

            # get non-shadow registers in the reebill
            actual_register_readings = reebill.actual_registers(service)

            #print "loaded rate structure"
            #pp(rate_structure)

            #print "loaded actual register readings"
            #pp(actual_register_readings)

            # copy the quantity of each non-shadow register in the reebill to
            # the corresponding register dictionary in the rate structure
            # ("apply the registers from the reebill to the probable rate structure")
            rate_structure.bind_register_readings(actual_register_readings)

            #print "rate structure with bound registers"
            #pp(rate_structure)

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

            # re-copy rate structure because it gets destroyed during use
            rate_structure = copy.deepcopy(the_rate_structure)

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
        """ Period Statistics for the input bill period are determined here
        from the total energy usage contained in the registers. Cumulative
        statistics are determined by adding period statistics to the past
        cumulative statistics """ 
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
        if re + ce > 0:
            re_utilization = Decimal(str(re / (re + ce)))\
                    .quantize(Decimal('.00'), rounding=ROUND_UP)
            ce_utilization = Decimal(str(ce / (re + ce)))\
                        .quantize(Decimal('.00'), rounding=ROUND_DOWN)
        else:
            re_utilization = 0
            ce_utilization = 0

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
        

        if self.splinter is not None:
            # fill in data for "Monthly Renewable Energy Consumption" graph

            # objects for getting olap data
            olap_id = self.nexus_util.olap_id(reebill.account)
            try:
                install = self.splinter.get_install_obj_for(olap_id)
            except ValueError as ve:
                print >> sys.stderr, ('Cannot lookup install %s, '
                        'statistics not completely calculated for %s-%s') % (
                        olap_id, reebill.account, reebill.sequence)
            else:
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
                            renewable_energy_btus = self.monguru.get_data_for_month(install, year,
                                    month).energy_sold
                            if (renewable_energy_btus is None):
                                renewable_energy_btus = 0
                        except (ValueError, AttributeError) as e:
                            print >> sys.stderr, ('Missing olap document for %s, '
                                    '%s-%s: skipped, but the graph will be wrong') % (
                                    install.name, year, month)
                            renewable_energy_btus = 0

                    therms = Decimal(str(renewable_energy_btus)) / Decimal('100000.0')
                    next_stats['consumption_trend'].append({
                        'month': calendar.month_abbr[month],
                        'quantity': therms
                    })
             
    def issue(self, session, account, sequence,
            issue_date=datetime.utcnow().date()):
        '''Sets the issue date of the reebill given by account, sequence to
        'issue_date' (or today by default), and the due date to 30 days from
        the issue date. The reebill's late charge is set to its permanent value
        in mongo, and the reebill is marked as issued in the state database.'''
        # version 0 of predecessor must be issued before this bill can be
        # issued:
        if sequence > 1 and not self.state_db.is_issued(session, account,
                sequence - 1, version=0):
            raise NotIssuable(("Can't issue reebill %s-%s because its "
                    "predecessor has not been issued.") % (account, sequence))

        # set issue date and due date in mongo
        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.issue_date = issue_date
        reebill.due_date = issue_date + timedelta(days=30)

        # set late charge to its final value (payments after this have no
        # effect on late fee)
        # TODO: should this be replaced with a call to compute_bill() to just
        # make sure everything is up-to-date before issuing?
        # https://www.pivotaltracker.com/story/show/36197985
        lc = self.get_late_charge(session, reebill)
        if lc is not None:
            reebill.late_charges = lc

        # save in mongo
        # NOTE frozen utility bills should already exist (created by
        # attach_utilbills)--so they're not being created here
        self.reebill_dao.save_reebill(reebill, freeze_utilbills=True)

        # mark as issued in mysql
        self.state_db.issue(session, account, sequence)


    def reebill_report_altitude(self, session):
        accounts = self.state_db.listAccounts(session)
        rows = [] 
        totalCount = 0
        for account in accounts:
            payments = self.state_db.payments(session, account)
            cumulative_savings = 0
            for reebill in self.reebill_dao.load_reebills_for(account, 0):
                # Skip over unissued reebills
                if not reebill.issue_date:
                    continue

                row = {}

                row['account'] = account
                row['sequence'] = reebill.sequence
                row['billing_address'] = reebill.billing_address
                row['service_address'] = reebill.service_address
                row['issue_date'] = reebill.issue_date
                row['period_begin'] = reebill.period_begin
                row['period_end'] = reebill.period_end
                row['actual_charges'] = reebill.actual_total.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['hypothetical_charges'] = reebill.hypothetical_total.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                total_ree = reebill.total_renewable_energy()\
                        .quantize(Decimal(".0"), rounding=ROUND_HALF_EVEN)
                row['total_ree'] = total_ree
                if total_ree != Decimal(0):
                    row['average_rate_unit_ree'] = ((reebill.hypothetical_total -
                            reebill.actual_total)/total_ree)\
                            .quantize(Decimal(".00"),
                            rounding=ROUND_HALF_EVEN)
                else:
                    row['average_rate_unit_ree'] = 0
                row['ree_value'] = reebill.ree_value.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['prior_balance'] = reebill.prior_balance.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['balance_forward'] = reebill.balance_forward.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                try:
                    row['total_adjustment'] = reebill.total_adjustment.quantize(
                            Decimal(".00"), rounding=ROUND_HALF_EVEN)
                except:
                    row['total_adjustment'] = None
                row['payment_applied'] = reebill.payment_received.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)

                row['ree_charges'] = reebill.ree_charges.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                try:
                    row['late_charges'] = reebill.late_charges.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                except KeyError:
                    row['late_charges'] = None

                row['balance_due'] = reebill.balance_due.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)

                row['discount_rate'] = reebill.discount_rate

                savings = reebill.ree_value - reebill.ree_charges
                cumulative_savings += savings
                row['savings'] = savings.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['cumulative_savings'] = cumulative_savings.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)

                rows.append(row)
                totalCount += 1

        return rows, totalCount

    def reebill_report(self, session, begin_date=None, end_date=None):
        accounts = self.state_db.listAccounts(session)
        rows = [] 
        totalCount = 0
        for account in accounts:
            payments = self.state_db.payments(session, account)
            cumulative_savings = 0
            for reebill in self.reebill_dao.load_reebills_for(account, 0):
                # Skip over unissued reebills
                if not reebill.issue_date:
                    continue
                # if the user has chosen a begin and/or end date *and* this
                # reebill falls outside of its bounds, skip to the next one
                have_period_dates = begin_date or end_date
                reebill_begins_in_this_period = begin_date and reebill.period_begin >= begin_date
                reebill_ends_in_this_period = end_date and reebill.period_end <= end_date
                reebill_in_this_period = reebill_begins_in_this_period or reebill_ends_in_this_period
                if have_period_dates and not reebill_in_this_period:
                    continue

                row = {}
                # iterate the payments and find the ones that apply. 
                if (reebill.period_begin is not None and reebill.period_end is not None):
                    applicable_payments = filter(lambda x: x.date_applied >
                            reebill.period_begin and x.date_applied <
                            reebill.period_end, payments)
                    # pop the ones that get applied from the payment list
                    # (there is a bug due to the reebill periods overlapping,
                    # where a payment may be applicable more than ones)
                    for applicable_payment in applicable_payments:
                        payments.remove(applicable_payment)

                row['account'] = account
                row['sequence'] = reebill.sequence
                row['version'] = reebill.version
                row['billing_address'] = reebill.billing_address
                row['service_address'] = reebill.service_address
                row['issue_date'] = reebill.issue_date
                row['period_begin'] = reebill.period_begin
                row['period_end'] = reebill.period_end
                row['actual_charges'] = reebill.actual_total.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['hypothetical_charges'] = reebill.hypothetical_total.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                total_ree = reebill.total_renewable_energy()\
                        .quantize(Decimal(".0"), rounding=ROUND_HALF_EVEN)
                row['total_ree'] = total_ree
                if total_ree != Decimal(0):
                    row['average_rate_unit_ree'] = ((reebill.hypothetical_total -
                            reebill.actual_total)/total_ree)\
                            .quantize(Decimal(".00"),
                            rounding=ROUND_HALF_EVEN)
                else:
                    row['average_rate_unit_ree'] = 0
                row['ree_value'] = reebill.ree_value.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['prior_balance'] = reebill.prior_balance.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['balance_forward'] = reebill.balance_forward.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                try:
                    row['total_adjustment'] = reebill.total_adjustment.quantize(
                            Decimal(".00"), rounding=ROUND_HALF_EVEN)
                except:
                    row['total_adjustment'] = None
                row['payment_applied'] = reebill.payment_received.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)

                row['ree_charges'] = reebill.ree_charges.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                try:
                    row['late_charges'] = reebill.late_charges.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                except KeyError:
                    row['late_charges'] = None

                row['balance_due'] = reebill.balance_due.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)

                savings = reebill.ree_value - reebill.ree_charges
                cumulative_savings += savings
                row['savings'] = savings.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)
                row['cumulative_savings'] = cumulative_savings.quantize(
                        Decimal(".00"), rounding=ROUND_HALF_EVEN)

                # normally, only one payment.  Multiple payments their own new rows...
                if applicable_payments:
                    row['payment_date'] = applicable_payments[0].date_applied
                    row['payment_amount'] = applicable_payments[0].credit
                    rows.append(row)
                    totalCount += 1
                    applicable_payments.pop(0)
                    for applicable_payment in applicable_payments:
                        row = {}
                        # ok, there was more than one applicable payment
                        row['account'] = account
                        row['sequence'] = reebill.sequence
                        row['version'] = reebill.version
                        row['billing_address'] = {}
                        row['service_address'] = {}
                        row['issue_date'] = None
                        row['period_begin'] = None
                        row['period_end'] = None
                        row['actual_charges'] = None
                        row['hypothetical_charges'] = None
                        row['total_ree'] = None
                        row['average_rate_unit_ree'] = None 
                        row['ree_value'] = None
                        row['prior_balance'] = None
                        row['balance_forward'] = None
                        row['total_adjustment'] = None
                        row['payment_applied'] = None
                        row['ree_charges'] = None
                        row['late_charges'] = None
                        row['balance_due'] = None
                        row['payment_date'] = applicable_payment.date_applied
                        row['payment_amount'] = applicable_payment.credit
                        row['savings'] = None
                        row['cumulative_savings'] = None
                        rows.append(row)
                        totalCount += 1
                else:
                    row['payment_date'] = None
                    row['payment_amount'] = None
                    rows.append(row)
                    totalCount += 1

            # TODO: why is this here? it seems that what it's doing is ensuring
            # there is alwas at least one row present in 'rows', but why isn't
            # it inside of an 'if/else' block to ensure that the empty row is
            # only present when no other results are returned?
            row = {}
            row['account'] = None
            row['sequence'] = None
            row['version'] = None
            row['billing_address'] = {}
            row['service_address'] = {}
            row['issue_date'] = None
            row['period_begin'] = None
            row['period_end'] = None
            row['actual_charges'] = None
            row['hypothetical_charges'] = None
            row['total_ree'] = None
            row['average_rate_unit_ree'] = None 
            row['ree_value'] = None
            row['prior_balance'] = None
            row['balance_forward'] = None
            row['total_adjustment'] = None
            row['payment_applied'] = None
            row['ree_charges'] = None
            row['late_charges'] = None
            row['balance_due'] = None
            row['payment_date'] = None
            row['payment_amount'] = None
            row['savings'] = None
            row['cumulative_savings'] = None
            rows.append(row)
            totalCount += 1

        return rows, totalCount

    def summary_ree_charges(self, session, accounts, all_names):
        def total_ree_in_reebills(self, reebills):
            total_energy = Decimal(0)
            for reebill in reebills:
                total_energy += reebill.total_renewable_energy()
            return total_energy
        
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
            row['olap_id'] = all_names[i][1].get('codename', '')
            row['casual_name'] = all_names[i][1].get('casualname', '')
            row['primus_name'] = all_names[i][1].get('primus', '')
            row['ree_charges'] = ree_charges
            row['actual_charges'] = actual_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            row['hypothetical_charges'] = hypothetical_total.quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            row['total_energy'] = total_energy.quantize(Decimal("0"))
            # per therm
            row['average_ree_rate'] = (average_ree_rate).quantize(Decimal(".00"), rounding=ROUND_HALF_EVEN)
            rows.append(row)

        return rows

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

