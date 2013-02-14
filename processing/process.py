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
import operator
#
# uuid collides with locals so both the locals and package are renamed
import uuid as UUID
import skyliner
from billing.processing import state
from billing.processing.mongo import MongoReebill
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state, fetch_bill_data
from billing.processing.db_objects import Payment, Customer, UtilBill, ReeBill
from billing.processing.mongo import ReebillDAO
from billing.processing.mongo import float_to_decimal
from billing.util import nexus_util
from billing.util import dateutils
from billing.util.dateutils import estimate_month, month_offset, month_difference
from billing.util.monthmath import Month, approximate_month
from billing.util.dictutils import deep_map
from billing.processing.exceptions import IssuedBillError, NotIssuable, NotAttachable, BillStateError

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint
sys.stdout = sys.stderr

sys.stdout = sys.stderr
class Process(object):
    """ Class with a variety of utility procedures for processing bills.
        The idea here is that this class is instantiated with the data
        access objects it needs, and then ReeBills (why not just references
        to them?) are passed in and returned.  
    """

    config = None
    
    def __init__(self, state_db, reebill_dao, rate_structure_dao, billupload,
            nexus_util, splinter=None):
        '''If 'splinter' is not none, Skyline back-end should be used.'''
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        self.reebill_dao = reebill_dao
        self.billupload = billupload
        self.nexus_util = nexus_util
        self.splinter = splinter
        self.monguru = None if splinter is None else splinter.get_monguru()

    def new_account(self, session, name, account, discount_rate, late_charge_rate):
        new_customer = Customer(name, account, discount_rate, late_charge_rate)
        session.add(new_customer)
        return new_customer

    def upload_utility_bill(self, session, account, service, begin_date,
                end_date, bill_file, file_name, total=0):
        '''Uploads 'bill_file' with the name 'file_name' as a utility bill for
        the given account, service, and dates. If the upload succeeds, a row is
        added to the utilbill table in MySQL. If this is the newest or oldest
        utility bill for the given account and service, "estimated" utility
        bills will be added to cover the gap between this bill's period and the
        previous newest or oldest one respectively. The total of all charges on
        the utility bill may be given.'''
        # NOTE 'total' does not yet go into the utility bill document in Mongo

        # get & save end date of last bill (before uploading a new bill which
        # may come later)
        original_last_end = self.state_db.last_utilbill_end_date(session,
                account)

        if bill_file is None:
            # if there's no file, this is a "skyline estimated bill":
            # record it in the database with that state, but don't upload
            # anything
            self.state_db.record_utilbill_in_database(session, account,
                    service, begin_date, end_date, total, datetime.utcnow(),
                    state=UtilBill.SkylineEstimated)
        else:
            # if there is a file, get the Python file object and name
            # string from CherryPy, and pass those to BillUpload to upload
            # the file (so BillUpload can stay independent of CherryPy)
            upload_result = self.billupload.upload(account, begin_date,
                    end_date, bill_file, file_name)
            if upload_result is True:
                self.state_db.record_utilbill_in_database(session, account,
                        service, begin_date, end_date, total,
                        datetime.utcnow())
            else:
                raise IOError('File upload failed: %s %s %s' % (file_name,
                    begin_date, end_date))

        # if begin_date does not match end date of latest existing bill, create
        # hypothetical bills to cover the gap
        if original_last_end is not None and begin_date > original_last_end:
            self.state_db.fill_in_hypothetical_utilbills(session, account,
                    service, original_last_end, begin_date)

    def delete_utility_bill(self, session, utilbill_id):
        '''Deletes the utility bill given by utilbill_id (if it's not
        associated or attached to a reebill) and returns the path where the
        file was moved (it never really gets deleted). This path will be None
        if there was no file or it could not be found. Raises a ValueError if
        the utility bill cannot be deleted.'''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        if utilbill.has_reebill:
            raise ValueError("Can't delete an attached utility bill.")

        # find out if any version of any reebill in mongo has this utilbill
        # associated with it. if so, it can't be deleted.
        possible_reebills = self.reebill_dao.load_reebills_in_period(
                utilbill.customer.account, start_date=utilbill.period_start,
                end_date=utilbill.period_end, version='any')
        for pb in possible_reebills:
            if utilbill.service in pb.services and \
                    pb.utilbill_period_for_service(utilbill.service) \
                    == (utilbill.period_start, utilbill.period_end):
                raise ValueError(("Can't delete a utility bill that has reebill"
                    " associated with it."))

        # OK to delete now.
        # first try to delete the file on disk
        try:
            new_path = self.billupload.delete_utilbill_file(
                    utilbill.customer.account, utilbill.period_start,
                    utilbill.period_end)
        except IOError:
            # file never existed or could not be found
            new_path = None

        # TODO move to StateDB?
        session.delete(utilbill)

        return new_path

    def compute_bill(self, session, prior_reebill, present_reebill):
        '''Compute everything about the bill that can be continuously
        recomputed. This should be called immediately after roll_bill()
        whenever roll_bill() is called.'''
        acc = present_reebill.account

        ## TODO: 22726549 hack to ensure the computations from bind_rs come back as decimal types
        present_reebill.reebill_dict = deep_map(float_to_decimal, present_reebill.reebill_dict)
        present_reebill._utilbills = [deep_map(float_to_decimal, u) for u in
                present_reebill._utilbills]

        self.bind_rate_structure(present_reebill)

        # get payment_received: all payments between issue date of
        # predecessor's version 0 and issue date of current reebill's version 0
        # (if current reebill is unissued, its version 0 has None as its
        # issue_date, meaning the payment period lasts up until the present)
        if self.state_db.is_issued(session, acc,
                prior_reebill.sequence, nonexistent=False):
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

        ## TODO: 22726549 hack to ensure the computations from bind_rs come back as decimal types
        present_reebill.reebill_dict = deep_map(float_to_decimal, present_reebill.reebill_dict)
        present_reebill._utilbills = [deep_map(float_to_decimal, u) for u in
                present_reebill._utilbills]

        # get discount rate
        discount_rate = present_reebill.discount_rate
        if not discount_rate:
            raise Exception("%s-%s-%s has no discount rate" % (acc,
                present_reebill.sequence, present_reebill.version))

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

        # compute adjustment: this bill only gets an adjustment if it's the
        # earliest unissued version-0 bill, i.e. it meets 2 criteria:
        # (1) it's a version-0 bill, not a correction
        # (2) at least the 0th version of its predecessor has been issued (it
        #     may have an unissued correction; if so, that correction will
        #     contribute to the adjustment on this bill)
        if present_reebill.version == 0 and self.state_db.is_issued(session,
                prior_reebill.account, prior_reebill.sequence, version=0,
                nonexistent=False):
            present_reebill.total_adjustment = self.get_total_adjustment(
                    session, present_reebill.account)
        else:
            present_reebill.total_adjustment = Decimal(0)

        # now grab the prior bill and pull values forward
        # TODO balance_forward currently contains adjustment, but it should not
        present_reebill.prior_balance = prior_reebill.balance_due
        present_reebill.balance_forward = present_reebill.prior_balance - \
                present_reebill.payment_received + \
                present_reebill.total_adjustment

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

        ## TODO: 22726549  hack to ensure the computations from bind_rs come back as decimal types
        present_reebill.reebill_dict = deep_map(float_to_decimal, present_reebill.reebill_dict)
        present_reebill._utilbills = [deep_map(float_to_decimal, u) for u in
                present_reebill._utilbills]
        
        self.calculate_statistics(prior_reebill, present_reebill)


    def copy_actual_charges(self, reebill):
        for service in reebill.services:
            actual_chargegroups = reebill.actual_chargegroups_for_service(service)
            reebill.set_hypothetical_chargegroups_for_service(service, actual_chargegroups)

    def roll_bill(self, session, reebill, utility_bill_date=None):
        '''Modifies 'reebill' to convert it into a template for the reebill of
        the next period (including incrementing the sequence). 'reebill' must
        be its customer's last bill before roll_bill is called. This method
        does not save the reebill in Mongo, but it DOES create new CPRS
        documents in Mongo (by copying the ones originally attached to the
        reebill). compute_bill() should always be called immediately after this
        one so the bill is updated to its current state.'''
        if utility_bill_date:
            utilbills = self.state_db.get_utilbills_on_date(session, reebill.account, utility_bill_date)
        else:
            utilbills = self.state_db.choose_next_utilbills(session, reebill.account, reebill.services)
        
        # duplicate the UPRS and CPRS for each service
        # TODO: 22597151 refactor
        for service in reebill.services:
            utility_name = reebill.utility_name_for_service(service)
            rate_structure_name = reebill.rate_structure_name_for_service(service)

            # load current CPRS, save it with same account, next sequence, version 0
            cprs = self.rate_structure_dao.load_cprs(reebill.account, reebill.sequence,
                    reebill.version, utility_name, rate_structure_name)
            if cprs is None:
                raise NoRateStructureError("No current CPRS")
            self.rate_structure_dao.save_cprs(reebill.account, reebill.sequence + 1,
                    0, utility_name, rate_structure_name, cprs)

            # generate predicted UPRS, save it with account, sequence, version 0
            uprs = self.rate_structure_dao.get_probable_uprs(reebill, service)
            if uprs is None:
                raise NoRateStructureError("No current UPRS")
            self.rate_structure_dao.save_uprs(reebill.account, reebill.sequence + 1,
                    0, utility_name, rate_structure_name, uprs)

            # remove charges that don't correspond to any RSI binding (because
            # their corresponding RSIs were not part of the predicted rate structure)
            valid_bindings = {rsi['rsi_binding']: False for rsi in uprs['rates'] +
                    cprs['rates']}
            chargegroups = reebill._get_utilbill_for_service(service)['chargegroups']
            for group, charges in chargegroups.iteritems():
                for charge in charges:
                    # if the charge matches a valid RSI binding, mark that
                    # binding as matched; if not, delete the charge
                    if charge['rsi_binding'] in valid_bindings:
                        valid_bindings[charge['rsi_binding']] = True
                    else:
                        charges.remove(charge)
                # chargegroup is not removed if it's empty because it might
                # come back

            # TODO add a charge for every RSI that doesn't have a charge, i.e.
            # the ones whose value in 'valid_bindings' is False.
            # we can't do this yet because we don't know what group it goes in.
            # see https://www.pivotaltracker.com/story/show/43797365

        # TODO Put somewhere nice because this has a specific function
        active_utilbills = [u for u in reebill._utilbills if u['service'] in reebill.services]
        reebill.reebill_dict['utilbills'] = [handle for handle in reebill.reebill_dict['utilbills'] if handle['id'] in [u['_id'] for u in active_utilbills]]

        # construct a new reebill from an old one. the new one's version is
        # always 0 even if it was created from a non-0 version of the old one.
        reebill.new_utilbill_ids()
        new_reebill = MongoReebill(reebill.reebill_dict, active_utilbills)
        new_reebill.version = 0
        new_reebill.new_utilbill_ids()
        new_reebill.clear()
        new_reebill.sequence += 1
        # Update the new reebill's periods to the periods identified in the StateDB
        for ub in utilbills:
            new_reebill.set_utilbill_period_for_service(ub.service, (ub.period_start, ub.period_end))
        new_reebill.set_meter_dates_from_utilbills()
        # set discount rate & late charge rate to the instananeous value from MySQL
        # NOTE suspended_services list is carried over automatically
        new_reebill.discount_rate = self.state_db.discount_rate(session, reebill.account)
        new_reebill.late_charge_rate = self.state_db.late_charge_rate(session, reebill.account)

        #self.reebill_dao.save_reebill(new_reebill)

        # create reebill row in state database
        self.state_db.new_rebill(session, new_reebill.account, new_reebill.sequence)
        self.attach_utilbills(session, new_reebill, utilbills)        
        
        return new_reebill


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
        customer = session.query(Customer).filter(Customer.account==account).one()

        if sequence <= 0:
            raise ValueError('Only sequence >= 0 can have multiple versions.')
        if not self.state_db.is_issued(session, account, sequence):
            raise ValueError("Can't create new version of an un-issued bill.")

        # get current max version from MySQL, and load that version's document
        # from Mongo (even if higher version exists in Mongo, it doesn't count
        # unless MySQL knows about it)
        max_version = self.state_db.max_version(session, account, sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence,
                version=max_version)

        # duplicate rate structures (CPRS)
        for service in reebill.services:
            utility_name = reebill.utility_name_for_service(service)
            rs_name = reebill.rate_structure_name_for_service(service)
            cprs = self.rate_structure_dao.load_cprs(reebill.account,
                    reebill.sequence, reebill.version, utility_name, rs_name)
            self.rate_structure_dao.save_cprs(account, sequence, max_version +
                    1, utility_name, rs_name, cprs)
            uprs = self.rate_structure_dao.load_uprs(reebill.account,
                    reebill.sequence, reebill.version, utility_name, rs_name)
            self.rate_structure_dao.save_uprs(account, sequence, max_version +
                    1, utility_name, rs_name, uprs)

        # re-bind
        fetch_bill_data.fetch_oltp_data(self.splinter,
                self.nexus_util.olap_id(account), reebill)

        # recompute, using sequence predecessor to compute balance forward and
        # prior balance. this is always version 0, because we want those values
        # to be the same as they were on version 0 of this bill--we don't care
        # about any corrections that might have been made to that bill later.
        predecessor = self.reebill_dao.load_reebill(account, sequence-1,
                version=0)

        # increment max version in mysql
        self.state_db.increment_version(session, account, sequence)

        # increment version, make un-issued, and replace utilbills with the
        # current-truth ones
        self.reebill_dao.increment_reebill_version(session, reebill)

        self.compute_bill(session, predecessor, reebill)

        # save in mongo
        self.reebill_dao.save_reebill(reebill)

        return reebill

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


    # TODO 21052893: probably want to set up the next reebill here.  Automatically roll?
    def attach_utilbills(self, session, reebill, utilbills):
        '''Freeze utilbills from the previous reebill into a new reebill.

        This affects only the Mongo document.'''
        if self.state_db.is_attached(session, reebill.account, reebill.sequence):
            raise NotAttachable(("Can't attach reebill %s-%s: it already has utility "
                    "bill(s) attached") % (reebill.account, reebill.sequence))
        #reebill = self.reebill_dao.load_reebill(account, sequence)

        # save in mongo, with frozen copies of the associated utility bill
        # (the mongo part should normally come last because it can't roll back,
        # but here it must precede MySQL because ReebillDAO.save_reebill will
        # refuse to create frozen utility bills "again" if MySQL says its
        # attached". see https://www.pivotaltracker.com/story/show/38308443)
        self.state_db.try_to_attach_utilbills(session, reebill.account, reebill.sequence, utilbills, reebill.suspended_services)

        self.reebill_dao.save_reebill(reebill)
        self.reebill_dao.save_reebill(reebill, freeze_utilbills=True)

        self.state_db.attach_utilbills(session, reebill.account, reebill.sequence, utilbills, reebill.suspended_services)

    def bind_rate_structure(self, reebill):
            # process the actual charges across all services
            self.bindrs(reebill)

    # TODO remove (move to bind_rate_structure)
    def bindrs(self, reebill):
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
        'issue_date' (or today by default),
        and the due date to 30 days from the issue date. The reebill's late
        charge is set to its permanent value in mongo, and the reebill is
        marked as issued in the state database. Does not attach utililty bills.'''
        # version 0 of predecessor must be issued before this bill can be
        # issued:
        if sequence > 1 and not self.state_db.is_issued(session, account,
                sequence - 1, version=0):
            raise NotIssuable(("Can't issue reebill %s-%s because its "
                    "predecessor has not been issued.") % (account, sequence))
        # TODO complain if utility bills have not been attached yet
        if not self.state_db.is_attached(session, account, sequence):
            raise NotAttachable(("Can't attach reebill %s-%s: it must "
                    "be attached first") % (account, sequence))

        # set issue date and due date in mongo
        reebill = self.reebill_dao.load_reebill(account, sequence)
        reebill.issue_date = issue_date

        # TODO: parameterize for dependence on customer 
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
        self.reebill_dao.save_reebill(reebill)

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
                total_ree = self.total_ree_in_reebill(reebill)\
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

    def reebill_report(self, session):
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

                # iterate the payments and find the ones that apply. 
                if (reebill.period_begin is not None and reebill.period_end is not None):
                    applicable_payments = filter(lambda x: x.date_applied >
                            reebill.period_begin and x.date_applied <
                            reebill.period_end, payments)
                    # pop the ones that get applied from the payment list
                    # (there is a bug due to the reebill periods overlapping, where a payment may be applicable more than ones)
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
                total_ree = self.total_ree_in_reebill(reebill)\
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


