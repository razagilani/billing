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
from decimal import * # BAD
from sqlalchemy.sql import desc
from sqlalchemy import not_
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
import operator
from bson import ObjectId
import traceback
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

    def get_utilbill_doc(self, session, utilbill_id, reebill_sequence=None,
            reebill_version=None):
        '''Loads and returns the Mongo document for the utility bill given by
        'utilbill_id' (MySQL id). If the sequence and version of an issued
        reebill are given, the document returned will be the frozen version for
        the issued reebill.
        '''
        # NOTE this method is in Process because it uses both databases; is
        # there a better place to put it?

        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

        if reebill_sequence is None:
            assert reebill_version is None
            # load editable utility bill document
            return self.reebill_dao.load_doc_for_utilbill(utilbill)

        # otherwise, load frozen utility bill document for the given reebill
        reebill = self.state_db.get_reebill(utilbill.customer.account,
                reebill_sequence, version=reebill_version)
        assert reebill.issued == True
        return self.state_db.load_doc_for_utilbill(session, utilbill,
                reebill=reebill)

    def get_rs_doc(self, session, utilbill_id, rs_type, reebill_sequence=None,
            reebill_version=None):
        '''Loads and returns a rate structure document of type 'rs_type'
        ("uprs" or "cprs") for the utility bill given by 'utilbill_id' (MySQL
        id). If the sequence and version of an issued reebill are given, the
        document returned will be the frozen version for the issued reebill.
        '''
        # NOTE this method is in Process because it uses both databases; is
        # there a better place to put it?

        if rs_type == 'uprs':
            load_method = self.rate_structure_dao.load_uprs_for_utilbill
        elif rs_type == 'cprs':
            load_method = self.rate_structure_dao.load_cprs_for_utilbill
        else:
            raise ValueError(('Unknown "rs_type": expected "uprs" or "cprs", '
                'got "%s"') % rs_type)

        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

        if reebill_sequence is None:
            assert reebill_version is None
            # load editable utility bill document
            return load_method(utilbill)

        # otherwise, load frozen utility bill document for the given reebill
        reebill = self.state_db.get_reebill(utilbill.customer.account,
                reebill_sequence, version=reebill_version)
        assert reebill.issued == True
        return load_method(session, utilbill, reebill=reebill)


    def update_utilbill_metadata(self, session, utilbill_id, period_start=None,
            period_end=None, service=None, total_charges=None, utility=None,
            rate_structure=None):
        '''Update various fields in MySQL and Mongo for the utility bill whose
        MySQL id is 'utilbill_id'. Fields that are not None get updated to new
        values while other fields are unaffected.
        '''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

        # save period dates for use in moving the utility bill file at the end
        # of this method
        old_start, old_end = utilbill.period_start, utilbill.period_end

        # forbid editing if this utility bill has an issued reebill
        # TODO this should change when it is clear which version of a utility bill can be edited in the UI
        if utilbill.is_attached():
            reebill = utilbill.reebill
            mongo_reebill = self.reebill_dao.load_reebill(
                    reebill.customer.account, reebill.sequence)
            # utility bills that have issued reebills shouldn't be editable
            if utilbill.reebill.issued:
                raise ValueError(("Can't edit utility bills that are attached "
                        "to an issued reebill."))

        # load Mongo document
        doc = self.reebill_dao.load_doc_for_utilbill(utilbill)

        # for total charges, it doesn't matter whether a reebill exists
        if total_charges is not None:
            utilbill.total_charges = total_charges

        # for service and period dates, a reebill must be updated if it does
        # exist

        if service is not None:
            doc['service'] = service
            utilbill.service = service
            
        if period_start is not None:
            UtilBill.validate_utilbill_period(period_start, utilbill.period_end)
            utilbill.period_start = period_start
            doc['start'] = period_start

        if period_end is not None:
            UtilBill.validate_utilbill_period(utilbill.period_start, period_end)
            utilbill.period_end = period_end
            doc['end'] = period_end

        if utility is not None:
            utilbill.utility = utility
            doc['utility'] = utility

        if rate_structure is not None:
            utilbill.rate_class = rate_structure
            doc['rate_structure_binding'] = rate_structure

        # delete any Hypothetical utility bills that were created to cover gaps
        # that no longer exist
        self.state_db.trim_hypothetical_utilbills(session,
                utilbill.customer.account, utilbill.service)

        # finally, un-rollback-able operations: move the file, if there is one,
        # and save in Mongo. (only utility bills that are Complete (0) or
        # UtilityEstimated (1) have files; SkylineEstimated (2) and
        # Hypothetical (3) ones don't.)
        if utilbill.state < state.UtilBill.SkylineEstimated:
            self.billupload.move_utilbill_file(utilbill.customer.account,
                    # don't trust the client to say what the original dates were
                    # TODO don't pass dates into BillUpload as strings
                    # https://www.pivotaltracker.com/story/show/24869817
                    old_start, old_end,
                    # dates in destination file name are the new ones
                    period_start or utilbill.period_start,
                    period_end or utilbill.period_end)


    def upload_utility_bill(self, session, account, service, utility,
            rate_class, begin_date, end_date, bill_file, file_name, total=0,
            state=UtilBill.Complete):
        '''Uploads 'bill_file' with the name 'file_name' as a utility bill for
        the given account, service, and dates. If the upload succeeds, a row is
        added to the utilbill table in MySQL and a document is added in Mongo
        (based on a previous bill or the template). If this is the newest or
        oldest utility bill for the given account and service, "estimated"
        utility bills will be added to cover the gap between this bill's period
        and the previous newest or oldest one respectively. The total of all
        charges on the utility bill may be given.'''
        # validate arguments
        if end_date <= begin_date:
            raise ValueError("Start date %s must precede end date %s" %
                    (begin_date, end_date))
        if end_date - begin_date > timedelta(days=365):
            raise ValueError(("Utility bill period %s to %s is longer than "
                "1 year") % (start, end))
        if bill_file is None and state in (UtilBill.UtilityEstimated,
                UtilBill.Complete):
            raise ValueError(("A file is required for a complete or "
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
        # (don't try to improve this code because it will go away when these
        # parameters are passed in from the client)
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

        # delete any existing bill with same service and period but less-final
        # state
        customer = self.state_db.get_customer(session, account)
        bill_to_replace = self._find_replaceable_utility_bill(session,
                customer, service, begin_date, end_date, state)
        if bill_to_replace is not None:
            session.delete(bill_to_replace)

        # create new UtilBill document (it does not have any mongo document
        # _ids yet but these are created below)
        # NOTE SQLAlchemy automatically adds this UtilBill to the session, so
        # calling session.add() is superfluous; see
        # https://www.pivotaltracker.com/story/show/26147819
        new_utilbill = UtilBill(customer, state, service, utility, rate_class,
                period_start=begin_date, period_end=end_date,
                total_charges=total, date_received=datetime.utcnow().date())

        # save 'new_utilbill' in MySQL with _ids from Mongo docs, and save the
        # 3 mongo docs in Mongo (unless it's a 'Hypothetical' utility bill,
        # which has no documents)
        session.add(new_utilbill)
        if state < UtilBill.Hypothetical:
            doc, uprs, cprs = self._generate_docs_for_new_utility_bill(session,
                    new_utilbill)
            new_utilbill.document_id = doc['_id']
            new_utilbill.uprs_document_id = uprs['_id']
            new_utilbill.cprs_document_id = cprs['_id']
            self.reebill_dao._save_utilbill(doc)
            self.rate_structure_dao.save_rs(uprs)
            self.rate_structure_dao.save_rs(cprs)

        # if begin_date does not match end date of latest existing bill, create
        # hypothetical bills to cover the gap
        # NOTE hypothetical bills are not created if the gap is small enough
        if original_last_end is not None and begin_date > original_last_end \
                and begin_date - original_last_end > \
                timedelta(days=MAX_GAP_DAYS):
            self.state_db.fill_in_hypothetical_utilbills(session, account,
                    service, utility, rate_class, original_last_end,
                    begin_date)

    def _find_replaceable_utility_bill(self, session, customer, service, start,
            end, state):
        '''Returns exactly one state.UtilBill that should be replaced by
        'new_utilbill' which is about to be uploaded (i.e. has the same
        customer, period, and service, but a less-final state). Returns None if
        there is no such bill. A NotUniqueException is raised if more than one
        utility bill matching these criteria is found.
        
        Note: customer, service, start, end are passed in instead of a new
        UtilBill because SQLAlchemy automatically adds any UtilBill that is
        instantiated to the session, which breaks the test for matching utility
        bills that already exist.'''
        # TODO 38385969: is this really a good idea?

        # get existing bills matching dates and service
        # (there should be at most one, but you never know)
        existing_bills = session.query(UtilBill)\
                .filter_by(customer=customer)\
                .filter_by(service=service)\
                .filter_by(period_start=start)\
                .filter_by(period_end=end)
        try:
            existing_bill = existing_bills.one()
        except NoResultFound:
            return None
        except MultipleResultsFound:
            raise NotUniqueException(("Can't upload a bill for dates %s, %s "
                    "because there are already %s of them") % (begin_date,
                    end_date, len(list(existing_bills))))

        # now there is one existing bill with the same dates. if state is
        # "more final" than an existing non-final bill that matches this
        # one, that bill should be replaced with the new one
        # (states can be compared with '<=' because they're ordered from
        # "most final" to least--see state.UtilBill)
        if existing_bill.state <= state:
            # TODO this error message is kind of obscure
            raise NotUniqueException(("Can't upload a utility bill for "
                "dates %s, %s because one already exists with a more final"
                " state than %s") % (start, end, state))

        return existing_bill


    def _generate_docs_for_new_utility_bill(self, session, utilbill):
        '''Returns utility bill doc, UPRS doc, CPRS doc for the given
        StateDB.UtilBill which is about to be added to the database, using the
        last utility bill with the same account, service, and rate class, or
        the account's template if no such bill exists. 'utilbill' must be at
        most 'SkylineEstimated', 'Hypothetical' because 'Hypothetical' utility
        bills have no documents. No database changes are made.'''
        assert utilbill.state < UtilBill.Hypothetical

        # look for the last utility bill with the same account, service, and
        # rate class, (i.e. the last-ending before 'end'), ignoring
        # Hypothetical ones. copy its mongo document and CPRS.
        # TODO pass this predecessor in from upload_utility_bill?
        # see https://www.pivotaltracker.com/story/show/51749487
        try:
            predecessor = self.state_db.get_last_real_utilbill(session,
                    utilbill.customer.account, utilbill.period_end,
                    service=utilbill.service, utility=utilbill.utility,
                    rate_class=utilbill.rate_class)
            doc = self.reebill_dao.load_doc_for_utilbill(predecessor)
            cprs = self.rate_structure_dao.load_cprs_for_utilbill(predecessor)
            cprs['_id'] = ObjectId()
        except NoSuchBillException:
            # if this is the first bill ever for the account (or all the
            # existing ones are Hypothetical), use template for the utility
            # bill document, and create new empty CPRS
            doc = self.reebill_dao.load_utilbill_template(session,
                    utilbill.customer.account)
            # template document should have the same service/utility/rate class
            # as this one; multiple services are not supported since there
            # would need to be more than one template
            assert doc['service'] == utilbill.service
            assert doc['utility'] == utilbill.utility
            assert doc['rate_structure_binding'] == utilbill.rate_class
            cprs = {'_id': ObjectId(), 'type': 'CPRS', 'rates': []}
        doc.update({
            '_id': ObjectId(),
            'start': date_to_datetime(utilbill.period_start),
            'end': date_to_datetime(utilbill.period_end),
             # update the document's "account" field just in case it's wrong or
             # two accounts are sharing the same template document
            'account': utilbill.customer.account,
        })

        # generate predicted UPRS
        uprs = self.rate_structure_dao.get_probable_uprs(session,
                utilbill.utility, utilbill.service, utilbill.rate_class,
                utilbill.period_start, utilbill.period_end,
                ignore=lambda uprs: False)
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

        return doc, uprs, cprs


    def delete_utility_bill(self, session, utilbill):
        '''Deletes the utility bill given by its MySQL id 'utilbill_id' (if
        it's not attached to a reebill) and returns the path where the file was
        moved (it never really gets deleted). This path will be None if there
        was no file or it could not be found. Raises a ValueError if the
        utility bill cannot be deleted.'''
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

        # delete utility bill document from Mongo
        self.reebill_dao.delete_doc_for_statedb_utilbill(utilbill)

        # delete UPRS and CPRS documents from Mongo
        self.rate_structure_dao.delete_rs_docs_for_utilbill(utilbill)

        return new_path


    def compute_bill(self, session, present_reebill):
        '''Compute everything about the bill that can be continuously
        recomputed. This should be called immediately after roll_bill()
        whenever roll_bill() is called.'''
        if present_reebill.sequence == 1:
            prior_reebill = None
        else:
            prior_reebill = self.reebill_dao.load_reebill(
                    present_reebill.account, present_reebill.sequence - 1,
                    version=0)
        acc = present_reebill.account

        # update "hypothetical charges" in reebill document to match actual
        # charges in utility bill document. note that hypothetical charges are
        # just replaced, so they will be wrong until computed below.
        for service in present_reebill.services:
            actual_chargegroups = present_reebill.\
                    actual_chargegroups_for_service(service)
            present_reebill.set_hypothetical_chargegroups_for_service(service,
                    actual_chargegroups)

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
            present_reebill.compute_charges(rs)

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
        if prior_reebill is not None and present_reebill.version == 0 \
                and self.state_db.is_issued(session, prior_reebill.account,
                prior_reebill.sequence, version=0, nonexistent=False):
            present_reebill.total_adjustment = self.get_total_adjustment(
                    session, present_reebill.account)
        else:
            present_reebill.total_adjustment = Decimal(0)

        if prior_reebill is None:
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
        

    def create_first_reebill(self, session, utilbill):
        '''Create and save the account's first reebill (in Mongo and MySQL),
        based on the given state.UtilBill.
        This is a separate method from create_next_reebill because a specific
        utility bill is provided indicating where billing should start.
        '''
        customer = utilbill.customer

        # make sure there are no reebills yet
        num_existing_reebills = session.query(ReeBill).join(Customer)\
                .filter(ReeBill.customer==customer).count()
        if num_existing_reebills > 0:
            raise ValueError("%s reebill(s) already exist for account %s" %
                    (num_existing_reebills, customer.account))
        
        # load document for the 'utilbill', use it to create the reebill
        # document, and save the reebill document
        utilbill_doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
        reebill_doc = MongoReebill.get_reebill_doc_for_utilbills(
                utilbill.customer.account, 1, 0, customer.discountrate,
                utilbill.customer.latechargerate, [utilbill_doc])
        self.reebill_dao.save_reebill(reebill_doc)

        # add row in MySQL
        session.add(ReeBill(customer, 1, version=0, utilbills=[utilbill]))


    def create_next_reebill(self, session, account):
        '''Creates the successor to the highest-sequence state.ReeBill for the
        given account, or the first reebill if none exists yet, and its
        associated Mongo document.'''
        customer = session.query(Customer)\
                .filter(Customer.account == account).one()
        last_reebill_row = session.query(ReeBill)\
                .filter(ReeBill.customer == customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version)).first()

        # now there is at least one reebill.
        # find successor to every utility bill belonging to the reebill, along
        # with its mongo document. note that Hypothetical utility bills are
        # excluded.
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
            if successor.state == UtilBill.Hypothetical:
                raise NoSuchBillException(('The next utility bill is '
                    '"hypothetical" so a reebill can\'t be based on it'))
            new_utilbills.append(successor)
            new_utilbill_docs.append(
                    self.reebill_dao.load_doc_for_utilbill(successor))

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
        max_version number in MySQL. Returns the new MongoReebill object.'''
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

        # replace utility bill documents with the "current" ones, and update
        # "hypothetical" utility bill data in the reebill document to match
        # (note that utility bill subdocuments in the reebill also get updated
        # in 'compute_bill' below, but 'fetch_oltp_data' won't work unless they
        # are updated)
        reebill_doc._utilbills = [self.reebill_dao.load_doc_for_utilbill(u)
                for u in reebill.utilbills]
        reebill_doc.update_utilbill_subdocs()

        # re-bind and compute
        # recompute, using sequence predecessor to compute balance forward and
        # prior balance. this is always version 0, because we want those values
        # to be the same as they were on version 0 of this bill--we don't care
        # about any corrections that might have been made to that bill later.
        fetch_bill_data.fetch_oltp_data(self.splinter,
                self.nexus_util.olap_id(account), reebill_doc)
        try:
            self.compute_bill(session, reebill_doc)
        except Exception as e:
            # NOTE: catching Exception is awful and horrible and terrible and
            # you should never do it, except when you can't think of any other
            # way to accomplish the same thing. ignoring the error here allows
            # a new version of the bill to be created even when it can't be
            # computed (e.g. the rate structure is broken and the user wants to
            # edit it, but can't until the new version already exists).
            self.logger.error(("In Process.new_version, couldn't compute new "
                    "version %s of reebill %s-%s: %s\n%s") % (
                    reebill_doc.version, reebill_doc.account,
                    reebill_doc.sequence, e, traceback.format_exc()))

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
        
        # load target reebill from mongo
        target_reebill = self.reebill_dao.load_reebill(account,
                target_sequence, version=target_max_version)

        # recompute target reebill (this sets total adjustment) and save it
        self.compute_bill(session, target_reebill)
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

    def delete_reebill(self, session, reebill):
        '''Deletes the the given reebill: removes the ReeBill object/row and
        its utility bill associations from MySQL, and its document from Mongo.
        A reebill version has been issued can't be deleted. Returns the version
        of the reebill that was deleted.'''
        # don't delete an issued reebill
        if reebill.issued:
            raise IssuedBillError("Can't delete an issued reebill.")

        version = reebill.version

        # delete reebill state data from MySQL and dissociate utilbills from it
        # (save max version first because row may be deleted)
        session.delete(reebill)

        # delete highest-version reebill document from Mongo
        self.reebill_dao.delete_reebill(reebill)

        return version


    def create_new_account(self, session, account, name, discount_rate,
            late_charge_rate, billing_address, service_address,
            template_account):
        '''Creates a new account with utility bill template copied from the
        last utility bill of 'template_account' (which must have at least one
        utility bill).
        
        'billing_address' and 'service_address' are dictionaries containing the
        addresses for the utility bill. The address format should be the
        utility bill address format.

        Returns the new state.Customer.'''
        if self.state_db.account_exists(session, account):
            raise ValueError("Account %s already exists" % account)

        template_last_sequence = self.state_db.last_sequence(session,
                template_account)

        # load document of last utility bill from template account (or its own
        # template utility bill document if there are no real ones) to become
        # the template utility bill for this account; update its account and
        # _id
        template_account_last_utilbill = session.query(UtilBill)\
                .join(Customer).filter(Customer.account==template_account)\
                .order_by(desc(UtilBill.period_end)).first()
        if template_account_last_utilbill is None:
            utilbill_doc = self.reebill_dao.load_utilbill_template(session,
                    template_account)
        else:
            utilbill_doc = self.reebill_dao.load_doc_for_utilbill(
                    template_account_last_utilbill)

        # create row for new customer in MySQL, with new utilbill document
        # template _id
        new_id = ObjectId()
        new_customer = Customer(name, account, discount_rate, late_charge_rate,
                new_id)
        session.add(new_customer)

        # save utilbill document template in Mongo with new account, _id,
        # addresses, and "total"
        utilbill_doc.update({
            '_id': new_id, 'account': account,

            # TODO what is 'total' anyway? should it be removed?
            # see https://www.pivotaltracker.com/story/show/53093021
            'total': 0,

            # keys listed explicitly to document the schema and validate the
            # address dictionaries passed in by the caller
            'billing_address': {
                'addressee': billing_address['addressee'],
                'street': billing_address['street'],
                'city': billing_address['city'],
                'state': billing_address['state'],
                'postal_code': billing_address['postal_code'],
            },
            'service_address': {
                'addressee': service_address['addressee'],
                'street': service_address['street'],
                'city': service_address['city'],
                'state': service_address['state'],
                'postal_code': service_address['postal_code'],
            },
        })
        self.reebill_dao._save_utilbill(utilbill_doc)

        return new_customer


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
        reebill_document = self.reebill_dao.load_reebill(account, sequence)
        reebill_document.issue_date = issue_date
        reebill_document.due_date = issue_date + timedelta(days=30)

        # set late charge to its final value (payments after this have no
        # effect on late fee)
        # TODO: should this be replaced with a call to compute_bill() to just
        # make sure everything is up-to-date before issuing?
        # https://www.pivotaltracker.com/story/show/36197985
        lc = self.get_late_charge(session, reebill_document)
        if lc is not None:
            reebill_document.late_charges = lc

        # save in mongo, creating a new frozen utility bill document, and put
        # that document's _id in the utilbill_reebill table
        # NOTE this only works when the reebill has one utility bill
        reebill = self.state_db.get_reebill(session, account, sequence)
        assert len(reebill._utilbill_reebills) == 1
        frozen_utilbill_id = self.reebill_dao.save_reebill(reebill_document,
                freeze_utilbills=True)
        reebill._utilbill_reebills[0].document_id = frozen_utilbill_id

        # also duplicate UPRS and CPRS, storing the new _ids in MySQL
        # ('save_reebill' can't do it because ReeBillDAO deals only with bill
        # documents)
        frozen_uprs_id, frozen_cprs_id = ObjectId(), ObjectId()
        uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                reebill.utilbills[0])
        cprs = self.rate_structure_dao.load_cprs_for_utilbill(
                reebill.utilbills[0])
        uprs['_id'], cprs['_id'] = frozen_uprs_id, frozen_cprs_id
        self.rate_structure_dao.save_rs(uprs)
        self.rate_structure_dao.save_rs(cprs)
        reebill._utilbill_reebills[0].uprs_document_id = frozen_uprs_id
        reebill._utilbill_reebills[0].cprs_document_id = frozen_cprs_id

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
            total_energy = total_ree_in_reebills(reebills)

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

