#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""
import sys

import os
import copy
from datetime import date, datetime, timedelta
from operator import itemgetter
import traceback
from itertools import chain
from sqlalchemy.sql import desc, functions
from sqlalchemy import not_, and_
from sqlalchemy import func
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from bson import ObjectId

from billupload import ACCOUNT_NAME_REGEX

#
# uuid collides with locals so both the locals and package are renamed
import re
import errno
import bson
from billing.processing import journal
from billing.processing import state
from billing.processing.state import Customer, UtilBill, ReeBill, \
    UtilBillLoader, ReeBillCharge, Address, Charge, Register, Reading, Session, Payment
from billing.util.dateutils import estimate_month, month_offset, month_difference, date_to_datetime
from billing.util.monthmath import Month
from billing.util.dictutils import subdict
from billing.exc import IssuedBillError, NotIssuable, \
    NoSuchBillException, NotUniqueException, NotComputable, ProcessedBillError

import pprint
from processing.state import UtilbillReebill

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
    def __init__(self, state_db, rate_structure_dao, billupload,
            nexus_util, bill_mailer, renderer, ree_getter,
            splinter=None, logger=None):
        '''If 'splinter' is not none, Skyline back-end should be used.'''
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        self.billupload = billupload
        self.nexus_util = nexus_util
        self.bill_mailer = bill_mailer
        self.ree_getter = ree_getter
        self.renderer = renderer
        self.splinter = splinter
        self.monguru = None if splinter is None else splinter.get_monguru()
        self.logger = logger
        self.journal_dao = journal.JournalDAO()

    def get_utilbill_charges_json(self, utilbill_id):
        """Returns a list of dictionaries of charges for the utility bill given
        by  'utilbill_id' (MySQL id)."""
        session = Session()
        utilbill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        return [charge.column_dict() for charge in utilbill.charges]

    def get_registers_json(self, utilbill_id):
        """Returns a dictionary of register information for the utility bill
        having the specified utilbill_id."""
        l = []
        session = Session()
        for r in session.query(Register).join(UtilBill,
            Register.utilbill_id == UtilBill.id).\
            filter(UtilBill.id == utilbill_id).all():
            l.append(r.column_dict())
        return l

    def new_register(self, utilbill_id, row):
        """Creates a new register for the utility bill having the specified id
        "row" argument is a dictionary but keys other than
        "meter_id" and "register_id" are ignored.
        """
        session = Session()
        utility_bill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        r = Register(
            utility_bill,
            "Insert description",
            0,
            "therms",
            row.get('register_id', "Insert register ID here"),
            False,
            "total",
            "Insert register binding here",
            None,
            row.get('meter_id', ""))
        session.add(r)
        session.flush()
        return r

    def update_register(self, register_id, rows):
        """Updates fields in the register given by 'register_id'
        """
        self.logger.info("Running Process.update_register %s" % register_id)
        session = Session()

        #Register to be updated
        register = session.query(Register).filter(
            Register.id == register_id).one()

        for k in ['description', 'quantity', 'quantity_units',
                  'identifier', 'estimated', 'reg_type', 'register_binding',
                  'active_periods', 'meter_identifier']:
            val = rows.get(k, getattr(register, k))
            self.logger.debug("Setting attribute %s on register %s to %s" %
                              (k, register.id, val))
            setattr(register, k, val)
        self.logger.debug("Commiting changes to register %s" % register.id)
        self.compute_utility_bill(register.utilbill_id)
        return register

    def delete_register(self, register_id):
        self.logger.info("Running Process.delete_register %s" %
                         register_id)
        session = Session()
        register = session.query(Register).filter(
            Register.id == register_id).one()
        utilbill_id = register.utilbill_id
        session.delete(register)
        session.commit()
        self.compute_utility_bill(utilbill_id)

    def add_charge(self, utilbill_id):
        """Add a new charge to the given utility bill."""
        session = Session()
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        all_rsi_bindings = set([c.rsi_binding for c in utilbill.charges])
        n = 1
        while ('New RSI #%s' % n) in all_rsi_bindings:
            n += 1
        charge = Charge(utilbill=utilbill,
                        description="New Charge - Insert description here",
                        group="",
                        quantity=0.0,
                        quantity_units="",
                        rate=0.0,
                        rsi_binding="New RSI #%s" % n,
                        total=0.0)
        session.add(charge)
        registers = utilbill.registers
        charge.quantity_formula = '' if len(registers) == 0 else \
            ('%s.quantity' % 'REG_TOTAL' if any([register.identifier ==
                'REG_TOTAL' for register in registers]) else \
            registers[0].identifier)
        session.flush()
        self.compute_utility_bill(utilbill_id)
        return charge

    def update_charge(self, fields, charge_id=None, utilbill_id=None,
                      rsi_binding=None):
        """Modify the charge given by charge_id
        by setting key-value pairs to match the dictionary 'fields'."""
        assert charge_id or utilbill_id and rsi_binding
        session = Session()
        charge = session.query(Charge).filter(Charge.id == charge_id).one() \
                    if charge_id else \
                session.query(Charge).\
                    filter(Charge.utilbill_id == utilbill_id).\
                    filter(Charge.rsi_binding == rsi_binding).one()

        for k, v in fields.iteritems():
            setattr(charge, k, v)
        session.flush()
        self.refresh_charges(charge.utilbill.id)
        self.compute_utility_bill(charge.utilbill.id)
        return charge

    def delete_charge(self, charge_id=None, utilbill_id=None, rsi_binding=None):
        """Delete the charge given by 'rsi_binding' in the given utility
        bill."""
        assert charge_id or utilbill_id and rsi_binding
        session = Session()
        charge = session.query(Charge).filter(Charge.id == charge_id).one() \
                    if charge_id else \
                session.query(Charge).\
                    filter(Charge.utilbill_id == utilbill_id).\
                    filter(Charge.rsi_binding == rsi_binding).one()
        session.delete(charge)
        self.compute_utility_bill(charge.utilbill_id)
        session.expire(charge.utilbill)

    def create_payment(self, account, date_applied, description,
            credit, date_received=None):
        '''Wrapper to create_payment method in state.py'''
        return self.state_db.create_payment(account, date_applied, description,
            credit, date_received)

    def update_payment(self, id, date_applied, description, credit):
        session = Session()
        payment = session.query(Payment).filter_by(id=id).one()
        payment.date_applied = date_applied
        payment.description = description
        payment.credit = credit

    def delete_payment(self, oid):
        '''Wrapper to delete_payment method in state.py'''
        self.state_db.delete_payment(oid)

    def get_hypothetical_matched_charges(self, reebill_id):
        """Gets all hypothetical charges from a reebill for a service and
        matches the actual charge to each hypotheitical charge
        TODO: This method has no test coverage!"""
        reebill = self.state_db.get_reebill_by_id(reebill_id)
        return [{
            'rsi_binding': reebill_charge.rsi_binding,
            'description': reebill_charge.description,
            'actual_quantity': reebill_charge.a_quantity,
            'actual_rate': reebill_charge.a_rate,
            'actual_total': reebill_charge.a_total,
            'quantity_units': reebill_charge.quantity_unit,
            'quantity': reebill_charge.h_quantity,
            'rate': reebill_charge.h_rate,
            'total': reebill_charge.h_total,
        } for reebill_charge in reebill.charges]

    def update_utilbill_metadata(self, utilbill_id, period_start=None,
            period_end=None, service=None, total_charges=None, utility=None,
            rate_class=None, processed=None):
        """Update various fields for the utility bill having the specified
        `utilbill_id`. Fields that are not None get updated to new
        values while other fields are unaffected.
        """
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        if total_charges is not None:
            utilbill.total_charges = total_charges

        if service is not None:
            utilbill.service = service

        if utility is not None:
            utilbill.utility = utility

        if rate_class is not None:
            utilbill.rate_class = rate_class

        if processed is not None:
            utilbill.processed = processed

        period_start = period_start if period_start else utilbill.period_start
        period_end = period_end if period_end else utilbill.period_end

        UtilBill.validate_utilbill_period(period_start, period_end)
        utilbill.period_start = period_start
        utilbill.period_end = period_end

        self.state_db.trim_hypothetical_utilbills(utilbill.customer.account,
                utilbill.service)
        self.compute_utility_bill(utilbill.id)
        return  utilbill

    def get_reebill_metadata_json(self, account):
        """Returns data describing all reebills for the given account, as list
        of JSON-ready dictionaries.
        """
        session = Session()

        # this subquery gets (customer_id, sequence, version) for all the
        # reebills whose version is the maximum in their (customer, sequence,
        # version) group.
        latest_versions_sq = session.query(ReeBill.customer_id,
                ReeBill.sequence,
                functions.max(ReeBill.version).label('max_version'))\
                .join(Customer)\
                .filter(Customer.account == account)\
                .order_by(ReeBill.customer_id, ReeBill.sequence).group_by(
                ReeBill.customer, ReeBill.sequence).subquery()

        # query ReeBill joined to the above subquery to get only
        # maximum-version bills, and also outer join to ReeBillCharge to get
        # sum of 0 or more charges associated with each reebill
        q = session.query(ReeBill).join(latest_versions_sq, and_(
                ReeBill.customer_id == latest_versions_sq.c.customer_id,
                ReeBill.sequence == latest_versions_sq.c.sequence,
                ReeBill.version == latest_versions_sq.c.max_version)
        ).outerjoin(ReeBillCharge)\
        .order_by(desc(ReeBill.sequence)).group_by(ReeBill.id)

        return [dict(rb.column_dict().items() +
                    [('total_error', self.get_total_error(account, rb.sequence))])
                for rb in q]

    def get_sequential_account_info(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        return {
            'billing_address': reebill.billing_address.column_dict(),
            'service_address': reebill.service_address.column_dict(),
            'discount_rate': reebill.discount_rate,
            'late_charge_rate': reebill.late_charge_rate,
        }

    def update_sequential_account_info(self, account, sequence,
            discount_rate=None, late_charge_rate=None, processed=None,
            ba_addressee=None, ba_street=None, ba_city=None, ba_state=None,
            ba_postal_code=None,
            sa_addressee=None, sa_street=None, sa_city=None, sa_state=None,
            sa_postal_code=None):
        """Update fields for the reebill given by account, sequence
        corresponding to the "sequential account information" form in the UI,
        """
        reebill = self.state_db.get_reebill(account, sequence)
        if reebill.issued:
            raise IssuedBillError("Can't modify an issued reebill")

        if reebill.processed:
            raise ProcessedBillError("can't modify processed reebill")

        if discount_rate is not None:
            reebill.discount_rate = discount_rate
        if late_charge_rate is not None:
            reebill.late_charge_rate = late_charge_rate
        if processed is not None:
            reebill.processed = processed
        if ba_addressee is not None:
            reebill.billing_address.addressee = ba_addressee
        if ba_state is not None:
            reebill.billing_address.state = ba_state
        if ba_street is not None:
            reebill.billing_address.street = ba_street
        if ba_city is not None:
            reebill.billing_address.city = ba_city
        if ba_postal_code is not None:
            reebill.billing_address.postal_code = ba_postal_code

        if sa_addressee is not None:
            reebill.service_address.addressee = sa_addressee
        if sa_state is not None:
            reebill.service_address.state = sa_state
        if sa_street is not None:
            reebill.service_address.street = sa_street
        if sa_city is not None:
            reebill.service_address.city = sa_city
        if sa_postal_code is not None:
            reebill.service_address.postal_code = sa_postal_code

        return reebill

    def upload_utility_bill(self, account, service, begin_date,
            end_date, bill_file, file_name, utility=None, rate_class=None,
            total=0, state=UtilBill.Complete):
        """Uploads `bill_file` with the name `file_name` as a utility bill for
        the given account, service, and dates. If this is the newest or
        oldest utility bill for the given account and service, "estimated"
        utility bills will be added to cover the gap between this bill's period
        and the previous newest or oldest one respectively. The total of all
        charges on the utility bill may be given.

        Returns the newly created UtilBill object.
        
        Currently 'utility' and 'rate_class' are ignored in favor of the
        predecessor's (or template's) values; see
        https://www.pivotaltracker.com/story/show/52495771
        """
        # validate arguments
        if end_date <= begin_date:
            raise ValueError("Start date %s must precede end date %s" %
                    (begin_date, end_date))
        if end_date - begin_date > timedelta(days=365):
            raise ValueError(("Utility bill period %s to %s is longer than "
                "1 year") % (begin_date, end_date))
        if bill_file is None and state in (UtilBill.UtilityEstimated,
                UtilBill.Complete):
            raise ValueError(("A file is required for a complete or "
                    "utility-estimated utility bill"))
        if bill_file is not None and state in (UtilBill.Hypothetical,
                UtilBill.SkylineEstimated):
            raise ValueError("Hypothetical or Skyline-estimated utility bills "
                    "can't have file")

        session = Session()

        # find an existing utility bill that will provide rate class and
        # utility name for the new one, or get it from the template.
        # note that it doesn't matter if this is wrong because the user can
        # edit it after uploading.
        customer = self.state_db.get_customer(account)
        try:
            predecessor = self.state_db.get_last_real_utilbill(account,
                    begin_date, service=service)
            billing_address = predecessor.billing_address
            service_address = predecessor.service_address
        except NoSuchBillException as e:
            # If we don't have a predecessor utility bill (this is the first
            # utility bill we are creating for this customer) then we get the
            # closest one we can find by time difference, having the same rate
            # class and utility.

            q = session.query(UtilBill).\
                filter_by(rate_class=customer.fb_rate_class).\
                filter_by(utility=customer.fb_utility_name).\
                filter_by(processed=True).\
                filter(UtilBill.state != UtilBill.Hypothetical)

            next_ub = q.filter(UtilBill.period_start >= begin_date).\
                order_by(UtilBill.period_start).first()
            prev_ub = q.filter(UtilBill.period_start <= begin_date).\
                order_by(UtilBill.period_start.desc()).first()

            next_distance = (next_ub.period_start - begin_date).days if next_ub\
                else float('inf')
            prev_distance = (begin_date - prev_ub.period_start).days if prev_ub\
                else float('inf')

            predecessor = None if next_distance == prev_distance == float('inf')\
                else prev_ub if prev_distance < next_distance else next_ub

            billing_address = customer.fb_billing_address
            service_address = customer.fb_service_address

        utility = utility if utility else getattr(predecessor, 'utility', "")

        rate_class = rate_class if rate_class else \
            getattr(predecessor, 'rate_class', "")

        # delete any existing bill with same service and period but less-final
        # state
        customer = self.state_db.get_customer(account)
        bill_to_replace = self._find_replaceable_utility_bill(
                customer, service, begin_date, end_date, state)
        if bill_to_replace is not None:
            session.delete(bill_to_replace)
        new_utilbill = UtilBill(customer, state, service, utility, rate_class,
                Address.from_other(billing_address),
                Address.from_other(service_address),
                period_start=begin_date, period_end=end_date,
                target_total=total, date_received=datetime.utcnow().date())
        session.add(new_utilbill)
        session.flush()

        if bill_file is not None:
            # if there is a file, get the Python file object and name
            # string from CherryPy, and pass those to BillUpload to upload
            # the file (so BillUpload can stay independent of CherryPy)
            upload_result = self.billupload.upload(new_utilbill, account,
                    bill_file, file_name)
            if not upload_result:
                raise IOError('File upload failed: %s %s %s' % (account,
                    new_utilbill.id, file_name))
        session.flush()
        if state < UtilBill.Hypothetical:
            new_utilbill.charges = self.rate_structure_dao.\
                get_predicted_charges(new_utilbill, UtilBillLoader(session))
            for register in predecessor.registers if predecessor else []:
                session.add(Register(new_utilbill, register.description,
                                     0, register.quantity_units,
                                     register.identifier, False,
                                     register.reg_type,
                                     register.register_binding,
                                     register.active_periods,
                                     register.meter_identifier))
        session.flush()
        if new_utilbill.state < UtilBill.Hypothetical:
            self.compute_utility_bill(new_utilbill.id)
        return new_utilbill

    def get_service_address(self, account):
        return self.state_db.get_last_real_utilbill(account,
                datetime.utcnow()).service_address.to_dict()

    def _find_replaceable_utility_bill(self, customer, service, start,
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
        session = Session()
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
                    "because there are already %s of them") % (start, end,
                    len(list(existing_bills))))

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

    def delete_utility_bill_by_id(self, utilbill_id):
        """Deletes the utility bill given by its MySQL id 'utilbill_id' (if

        it's not attached to a reebill) and returns the deleted state
        .UtilBill object and the path  where the file was moved (it never
        really gets deleted). This path will be None if there was no file or
        it could not be found. Raises a ValueError if the
        utility bill cannot be deleted.
        """
        session = Session()
        utility_bill = session.query(state.UtilBill).\
            filter(state.UtilBill.id == utilbill_id).one()

        if utility_bill.is_attached():
            raise ValueError("Can't delete an attached utility bill.")

        try:
            path = self.billupload.delete_utilbill_file(utility_bill)
        except IOError:
            # file never existed or could not be found
            path = None

        # TODO use cascade instead if possible
        for charge in utility_bill.charges:
            session.delete(charge)
        for register in utility_bill.registers:
            session.delete(register)
        self.state_db.trim_hypothetical_utilbills(utility_bill.customer.account,
                                                  utility_bill.service)
        session.delete(utility_bill)

        return utility_bill, path

    def regenerate_uprs(self, utilbill_id):
        '''Resets the UPRS of this utility bill to match the predicted one.
        '''
        session = Session()
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        for charge in utilbill.charges:
            session.delete(charge)
        utilbill.charges = []
        utilbill.charges = self.rate_structure_dao.\
            get_predicted_charges(utilbill, UtilBillLoader(session))
        self.compute_utility_bill(utilbill_id)

    def has_utilbill_predecessor(self, utilbill_id):
        try:
            utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
            self.state_db.get_last_real_utilbill(
                    utilbill.customer.account, utilbill.period_start,
                    utility=utilbill.utility, service=utilbill.service)
            return True
        except NoSuchBillException:
            return False

    def refresh_charges(self, utilbill_id):
        '''Replaces charges in the utility bill document with newly-created
        ones based on its rate structures.
        '''
        self.state_db.get_utilbill_by_id(utilbill_id).compute_charges()

    def compute_utility_bill(self, utilbill_id):
        '''Updates all charges in the utility bill given by 'utilbill_id'.
        Also updates some keys in the document that are duplicates of columns
        in the MySQL table.
        '''
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        utilbill.compute_charges()
        return utilbill

    def compute_reebill(self, account, sequence, version='max'):
        '''Loads, computes, and saves the reebill
        '''
        reebill = self.state_db.get_reebill(account, sequence,
                version)
        if reebill.processed:
            # processed reebills are already computed
            return
        reebill.compute_charges()
        actual_total = reebill.get_total_actual_charges()

        reebill.utilbill.compute_charges()
        hypothetical_total = reebill.get_total_hypothetical_charges()
        reebill.ree_value = hypothetical_total - actual_total
        reebill.ree_charge = reebill.ree_value * (1 - reebill.discount_rate)
        reebill.ree_savings = reebill.ree_value * reebill.discount_rate

        # compute adjustment: this bill only gets an adjustment if it's the
        # earliest unissued version-0 bill, i.e. it meets 2 criteria:
        # (1) it's a version-0 bill, not a correction
        # (2) at least the 0th version of its predecessor has been issued (it
        #     may have an unissued correction; if so, that correction will
        #     contribute to the adjustment on this bill)
        if reebill.sequence == 1:
            reebill.total_adjustment = 0

            # include all payments since the beginning of time, in case there
            # happen to be any.
            # if any version of this bill has been issued, get payments up
            # until the issue date; otherwise get payments up until the
            # present.
            present_v0_issue_date = self.state_db.get_reebill(
                  account, sequence, version=0).issue_date
            if present_v0_issue_date is None:
                payments = self.state_db. \
                    get_total_payment_since(account,
                        state.MYSQLDB_DATETIME_MIN, payment_objects=True)
                self.compute_reebill_payments(payments, reebill)
            else:
                payments = self.state_db. \
                    get_total_payment_since(account,
                        state.MYSQLDB_DATETIME_MIN, end=present_v0_issue_date, payment_objects=True)
                self.compute_reebill_payments(payments, reebill)
            # obviously balances are 0
            reebill.prior_balance = 0
            reebill.balance_forward = 0

            # NOTE 'calculate_statistics' is not called because statistics
            # section should already be zeroed out
        else:
            predecessor = self.state_db.get_reebill(account,
                    reebill.sequence - 1, version=0)
            if reebill.version == 0 and predecessor.issued:
                reebill.total_adjustment = self.get_total_adjustment(account)

            # get payment_received: all payments between issue date of
            # predecessor's version 0 and issue date of current reebill's version 0
            # (if current reebill is unissued, its version 0 has None as its
            # issue_date, meaning the payment period lasts up until the present)
            if predecessor.issued:
                # if predecessor's version 0 is issued, gather all payments from
                # its issue date until version 0 issue date of current bill, or
                # today if this bill has never been issued
                if self.state_db.is_issued(account, reebill.sequence,
                        version=0):
                    present_v0_issue_date = self.state_db.get_reebill(account,
                            reebill.sequence, version=0).issue_date
                    payments = self.state_db. \
                            get_total_payment_since(account,
                            predecessor.issue_date, end=present_v0_issue_date, payment_objects=True)
                    self.compute_reebill_payments(payments, reebill)
                else:
                    payments = self.state_db. \
                            get_total_payment_since(account,
                            predecessor.issue_date, payment_objects=True)
                    self.compute_reebill_payments(payments, reebill)
            else:
                # if predecessor is not issued, there's no way to tell what
                # payments will go in this bill instead of a previous bill, so
                # assume there are none (all payments since last issue date go in
                # the account's first unissued bill)
                reebill.payment_received = 0

            reebill.prior_balance = predecessor.balance_due
            reebill.balance_forward = predecessor.balance_due - \
                  reebill.payment_received + reebill.total_adjustment

        # include manually applied adjustment
        reebill.balance_forward += reebill.manual_adjustment

        # set late charge, if any (this will be None if the previous bill has
        # not been issued, 0 before the previous bill's due date, and non-0
        # after that)describe
        lc = self.get_late_charge(reebill)
        reebill.late_charge = lc or 0
        reebill.balance_due = reebill.balance_forward + reebill.ree_charge + \
                reebill.late_charge
        return reebill

    def compute_reebill_payments(self, payments, reebill):
        for payment in payments:
            payment.reebill_id = reebill.id
        reebill.payment_received = float(sum(payment.credit for payment in payments))

    def roll_reebill(self, account, start_date=None):
        """ Create first or roll the next reebill for given account.
        After the bill is rolled, this function also binds renewable energy data
        and computes the bill by default. This behavior can be modified by
        adjusting the appropriate parameters.
        'start_date': must be given for the first reebill.
        """
        session = Session()

        customer = self.state_db.get_customer(account)
        last_reebill_row = session.query(ReeBill)\
                .filter(ReeBill.customer == customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version)).first()

        new_utilbills = []
        if last_reebill_row is None:
            # No Reebills are associated with this account: Create the first one
            assert start_date is not None
            utilbill = session.query(UtilBill)\
                    .filter(UtilBill.customer == customer)\
                    .filter(UtilBill.period_start >= start_date)\
                    .order_by(UtilBill.period_start).first()
            if utilbill is None:
                raise ValueError("No utility bill found starting on/after %s" %
                        start_date)
            new_utilbills.append(utilbill)
            new_sequence = 1
        else:
            # There are Reebills associated with this account: Create the next Reebill
            # First, find the successor to every utility bill belonging to the reebill
            # note that Hypothetical utility bills are excluded.
            for utilbill in last_reebill_row.utilbills:
                successor = session.query(UtilBill)\
                    .filter(UtilBill.customer == customer)\
                    .filter(not_(UtilBill._utilbill_reebills.any()))\
                    .filter(UtilBill.service == utilbill.service)\
                    .filter(UtilBill.utility == utilbill.utility)\
                    .filter(UtilBill.period_start >= utilbill.period_end)\
                    .order_by(UtilBill.period_end).first()
                if successor is None:
                    raise NoSuchBillException(("Couldn't find next "
                            "utility bill following %s") % utilbill)
                if successor.state == UtilBill.Hypothetical:
                    raise NoSuchBillException(('The next utility bill is '
                        '"hypothetical" so a reebill can\'t be based on it'))
                new_utilbills.append(successor)
            new_sequence = last_reebill_row.sequence + 1

        # currently only one service is supported
        assert len(new_utilbills) == 1

        # create reebill row in state database
        new_reebill = ReeBill(customer, new_sequence, 0,
                              utilbills=new_utilbills,
                              billing_address=Address.from_other(
                                new_utilbills[0].billing_address),
                              service_address=Address.from_other(
                                new_utilbills[0].service_address))

        # assign Reading objects to the ReeBill based on registers from the
        # utility bill document
        if last_reebill_row is None:
            new_reebill.replace_readings_from_utility_bill_registers(utilbill)
        else:
            new_reebill.update_readings_from_reebill(last_reebill_row.readings)
            new_reebill.copy_reading_conventional_quantities_from_utility_bill()
        session.add(new_reebill)
        session.add_all(new_reebill.readings)


        self.ree_getter.update_renewable_readings(
                self.nexus_util.olap_id(account), new_reebill, use_olap=True)

        try:
            self.compute_reebill(account, new_sequence)
        except Exception as e:
            self.logger.error("Error when computing reebill %s: %s" % (
                    new_reebill, e))
        return new_reebill

    def new_version(self, account, sequence):
        """Creates a new version of the given reebill: duplicates the Reebill,
        re-computes the it, saves it, and increments the max_version number in
        MySQL. Returns the the new reebill.
        """
        if sequence <= 0:
            raise ValueError('Only sequence >= 0 can have multiple versions.')
        if not self.state_db.is_issued(account, sequence):
            raise ValueError("Can't create new version of an un-issued bill.")

        max_version = self.state_db.max_version(account, sequence)
        reebill = self.state_db.increment_version(account, sequence)

        assert len(reebill.utilbills) == 1

        reebill.replace_readings_from_utility_bill_registers(reebill.utilbill)
        self.ree_getter.\
            update_renewable_readings(self.nexus_util.olap_id(account), reebill)
        try:
            self.compute_reebill(account, sequence, version=max_version+1)
        except Exception as e:
            # NOTE: catching Exception is awful and horrible and terrible and
            # you should never do it, except when you can't think of any other
            # way to accomplish the same thing. ignoring the error here allows
            # a new version of the bill to be created even when it can't be
            # computed (e.g. the rate structure is broken and the user wants to
            # edit it, but can't until the new version already exists).
            self.logger.error(("In Process.new_version, couldn't compute new "
                    "version %s of reebill %s-%s: %s\n%s") % (
                    reebill.version, reebill.customer.account,
                    reebill.sequence, e, traceback.format_exc()))

        return reebill

    def list_all_versions(self, account, sequence):
        ''' Returns all Reebills with sequence and account ordered by versions
            a list of dictionaries
        '''
        session = Session()
        q = session.query(ReeBill).join(Customer).with_lockmode('read')\
            .filter(Customer.account == account)\
            .filter(ReeBill.sequence == sequence)\
            .order_by(desc(ReeBill.version))

        return [rb.column_dict() for rb in q]

    def get_unissued_corrections(self, account):
        """Returns [(sequence, max_version, balance adjustment)] of all
        un-issued versions of reebills > 0 for the given account."""
        result = []
        for seq, max_version in self.state_db.get_unissued_corrections(account):
            # adjustment is difference between latest version's
            # charges and the previous version's
            assert max_version > 0
            latest_version = self.state_db.get_reebill(account, seq,
                    version=max_version)
            prev_version = self.state_db.get_reebill(account, seq,
                    version=max_version - 1)
            adjustment = latest_version.total - prev_version.total
            result.append((seq, max_version, adjustment))
        return result

    def issue_corrections(self, account, target_sequence):
        '''Applies adjustments from all unissued corrections for 'account' to
        the reebill given by 'target_sequence', and marks the corrections as
        issued.'''
        # corrections can only be applied to an un-issued reebill whose version
        # is 0
        target_max_version = self.state_db.max_version(account, target_sequence)
        if self.state_db.is_issued(account, target_sequence) \
                or target_max_version > 0:
            raise ValueError(("Can't apply corrections to %s-%s, "
                    "because the latter is an issued reebill or another "
                    "correction.") % (account, target_sequence))
        all_unissued_corrections = self.get_unissued_corrections(account)
        if len(all_unissued_corrections) == 0:
            raise ValueError('%s has no corrections to apply' % account)

        # recompute target reebill (this sets total adjustment) and save it
        reebill = self.state_db.get_reebill(account, target_sequence, target_max_version)
        if not reebill.processed:
            self.compute_reebill(account, target_sequence,
                version=target_max_version)

        # issue each correction
        for correction in all_unissued_corrections:
            correction_sequence, _, _ = correction
            self.issue(account, correction_sequence)

    def get_total_adjustment(self, account):
        '''Returns total adjustment that should be applied to the next issued
        reebill for 'account' (i.e. the earliest unissued version-0 reebill).
        This adjustment is the sum of differences in totals between each
        unissued correction and the previous version it corrects.'''
        return sum(adjustment for (sequence, version, adjustment) in
                self.get_unissued_corrections(account))

    def get_total_error(self, account, sequence):
        '''Returns the net difference between the total of the latest
        version (issued or not) and version 0 of the reebill given by account,
        sequence.'''
        earliest = self.state_db.get_reebill(account, sequence, version=0)
        latest = self.state_db.get_reebill(account, sequence, version='max')
        return latest.total - earliest.total

    def get_late_charge(self, reebill, day=None):
        '''Returns the late charge for the given reebill on 'day', which is the
        present by default. ('day' will only affect the result for a bill that
        hasn't been issued yet: there is a late fee applied to the balance of
        the previous bill when only when that previous bill's due date has
        passed.) Late fees only apply to bills whose predecessor has been
        issued; None is returned if the predecessor has not been issued. (The
        first bill and the sequence 0 template bill always have a late charge
        of 0.)'''
        session = Session()
        if day is None:
            day = datetime.utcnow().date()
        acc, seq = reebill.customer.account, reebill.sequence

        if reebill.sequence <= 1:
            return 0

        # unissued bill has no late charge
        if not self.state_db.is_issued(acc, seq - 1):
            return None

        # late charge is 0 if version 0 of the previous bill is not overdue
        predecessor0 = self.state_db.get_reebill(acc, seq - 1,
                version=0)
        if day <= predecessor0.due_date:
            return 0

        # the balance on which a late charge is based is not necessarily the
        # current bill's balance_forward or the "outstanding balance": it's the
        # least balance_due of any issued version of the predecessor (as if it
        # had been charged on version 0's issue date, even if the version
        # chosen is not 0).
        customer = self.state_db.get_customer(acc)
        min_balance_due = session.query(func.min(ReeBill.balance_due))\
                .filter(ReeBill.customer == customer)\
                .filter(ReeBill.sequence == seq - 1).one()[0]
        source_balance = min_balance_due - \
                self.state_db.get_total_payment_since(acc,
                predecessor0.issue_date)
        #Late charges can only be positive
        return (reebill.late_charge_rate) * max(0, source_balance)

    def get_outstanding_balance(self, account, sequence=None):
        '''Returns the balance due of the reebill given by account and sequence
        (or the account's last issued reebill when 'sequence' is not given)
        minus the sum of all payments that have been made since that bill was
        issued. Returns 0 if total payments since the issue date exceed the
        balance due, or if no reebill has ever been issued for the customer.'''
        # get balance due of last reebill
        if sequence == None:
            sequence = self.state_db.last_issued_sequence(account)
        if sequence == 0:
            return 0
        reebill = self.state_db.get_reebill(sequence)

        if reebill.issue_date == None:
            return 0

        # result cannot be negative
        return max(0, reebill.balance_due -
                self.state_db.get_total_payment_since(account,
                        reebill.issue_date))

    def delete_reebill(self, account, sequence):
        '''Deletes the the given reebill and its utility bill associations.
        A reebill version has been issued can't be deleted. Returns the version
        of the reebill that was deleted.'''
        session = Session()
        reebill = self.state_db.get_reebill(account, sequence)
        if reebill.issued:
            raise IssuedBillError("Can't delete an issued reebill.")
        if reebill.version == 0 and reebill.sequence < \
                self.state_db.last_sequence(account):
            raise IssuedBillError("Only the last reebill can be deleted")
        version = reebill.version

        # NOTE session.delete() fails with an errror like "InvalidRequestError:
        # Instance '<ReeBill at 0x353cbd0>' is not persisted" if the object has
        # not been persisted (i.e. flushed from SQLAlchemy cache to database)
        # yet; the author says on Stack Overflow to use 'expunge' if the object
        # is in 'session.new' and 'delete' otherwise, but for some reason
        # 'reebill' does not get into 'session.new' when session.add() is
        # called. i have not solved this problem yet.
        session.delete(reebill)

        # Delete the PDF associated with a reebill if it was version 0
        # because we believe it is confusing to delete the pdf when
        # when a version still exists
        if version == 0:
            full_path = self.billupload.get_reebill_file_path(account,
                    sequence)
            # If the file exists, delete it, otherwise don't worry.
            try:
                os.remove(full_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
        return version

    def create_new_account(self, account, name, discount_rate,
            late_charge_rate, billing_address, service_address,
            template_account):
        '''Creates a new account with utility bill template copied from the
        last utility bill of 'template_account' (which must have at least one
        utility bill).
        
        'billing_address' and 'service_address' are dictionaries containing the
        addresses for the utility bill. The address format should be the
        utility bill address format.

        Returns the new state.Customer.'''
        if self.state_db.account_exists(account):
            raise ValueError("Account %s already exists" % account)

        # validate parameters
        if not re.match(ACCOUNT_NAME_REGEX, account):
            raise ValueError('Invalid account number')
        if not 0 <= discount_rate <= 1:
            raise ValueError('Discount rate must be between 0 and 1 inclusive')
        if not 0 <= late_charge_rate <=1:
            raise ValueError(('Late charge rate must be between 0 and 1 '
                              'inclusive'))
        session = Session()
        
        last_utility_bill = session.query(UtilBill)\
            .join(Customer).filter(Customer.account == template_account)\
            .order_by(desc(UtilBill.period_end)).first()

        if last_utility_bill is None:
            raise NoSuchBillException("Last utility bill not found for account %s" % \
                                      template_account)

        new_customer = Customer(name, account, discount_rate, late_charge_rate,
                'example@example.com',
                last_utility_bill.utility,      #fb_utility_name
                last_utility_bill.rate_class,   #fb_rate_class
                Address(billing_address['addressee'],
                        billing_address['street'],
                        billing_address['city'],
                        billing_address['state'],
                        billing_address['postal_code']),
                Address(service_address['addressee'],
                        service_address['street'],
                        service_address['city'],
                        service_address['state'],
                        service_address['postal_code']))
        session.add(new_customer)
        session.flush()
        return new_customer

    def issue(self, account, sequence, issue_date=None):
        '''Sets the issue date of the reebill given by account, sequence to
        'issue_date' (or today by default), and the due date to 30 days from
        the issue date. The reebill is marked as issued.'''
        # version 0 of predecessor must be issued before this bill can be
        # issued:
        if issue_date is None:
            issue_date = datetime.utcnow()
        if sequence > 1 and not self.state_db.is_issued(account,
                sequence - 1, version=0):
            raise NotIssuable(("Can't issue reebill %s-%s because its "
                    "predecessor has not been issued.") % (account, sequence))
        reebill = self.state_db.get_reebill(account, sequence)

        # compute the bill to make sure it's up to date before issuing
        if not reebill.processed:
            self.compute_reebill(reebill.customer.account,
                reebill .sequence, version=reebill.version)

        reebill.issue_date = issue_date
        reebill.due_date = (issue_date + timedelta(days=30)).date()

        # set late charge to its final value (payments after this have no
        # effect on late fee)
        # TODO: should this be replaced with a call to compute_reebill to
        # just make sure everything is up-to-date before issuing?
        # https://www.pivotaltracker.com/story/show/36197985
        reebill.late_charge = self.get_late_charge(reebill)

        assert len(reebill._utilbill_reebills) == 1

        # mark as issued in mysql
        self.state_db.issue(account, sequence, issue_date=issue_date)

        # store email recipient in the bill
        reebill.email_recipient = reebill.customer.bill_email_recipient

    def reebill_report_altitude(self):
        session = Session()
        rows = []
        total_count = 0
        customer_id = None
        for reebill in session.query(ReeBill).\
                filter(ReeBill.issue_date != None).\
                order_by(ReeBill.customer_id).all():

            total_count += 1

            savings = reebill.ree_value - reebill.ree_charge

            if reebill.customer_id != customer_id:
                cumulative_savings = 0
                customer_id = reebill.customer_id

            cumulative_savings += savings

            row = {}

            actual_total = reebill.utilbill.get_total_charges()
            hypothetical_total = reebill.get_total_hypothetical_charges()
            total_ree = reebill.get_total_renewable_energy()

            row['account'] = reebill.customer.account
            row['sequence'] = reebill.sequence
            row['billing_address'] = reebill.billing_address
            row['service_address'] = reebill.service_address
            row['issue_date'] = reebill.issue_date
            row['period_begin'] = reebill.utilbill.period_start
            row['period_end'] = reebill.utilbill.period_end
            row['actual_charges'] = actual_total
            row['hypothetical_charges'] = hypothetical_total
            row['total_ree'] = total_ree
            row['average_rate_unit_ree'] = 0 if total_ree == 0 else \
                (hypothetical_total - actual_total) / total_ree
            row['ree_value'] = reebill.ree_value
            row['prior_balance'] = reebill.prior_balance
            row['balance_forward'] = reebill.balance_forward
            row['total_adjustment'] = reebill.total_adjustment
            row['payment_applied'] = reebill.payment_received
            row['ree_charges'] = reebill.ree_charge
            row['late_charges'] = reebill.late_charge
            row['late_charges'] = reebill.late_charge
            row['balance_due'] = reebill.balance_due
            row['discount_rate'] = reebill.discount_rate
            row['savings'] = savings
            row['cumulative_savings'] = cumulative_savings
            rows.append(row)
        return rows, total_count

    def sequences_for_approximate_month(self, account, year, month):
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
        reebills = session.query(ReeBill).join(UtilBill).filter(
                UtilBill.period_start >= date(year, month, 1),
                UtilBill.period_end <= date(next_month_year, next_month, 1)
                ).all()

        # sequences for this month are those of the bills whose approximate
        # month is this month
        sequences_for_month = [r.sequence for r in reebills if
                estimate_month(r.period_begin, r.period_end) == (year, month)]

        # if there's at least one sequence, return the list of sequences
        if sequences_for_month != []:
            return sequences_for_month

        # get approximate month of last reebill (return [] if there were never
        # any reebills)
        last_sequence = self.state_db.last_sequence(account)
        if last_sequence == 0:
            return []
        last_reebill = self.state_db.get_reebill(account, last_sequence)
        last_reebill_year, last_reebill_month = estimate_month(
                *last_reebill.get_period())

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

    def sequences_in_month(self, account, year, month):
        '''Returns a list of sequences of all reebills whose periods contain
        ANY days within the given month. The list is empty if the month
        precedes the period of the account's first issued reebill, or if the
        account has no issued reebills at all. When 'sequence' exceeds the last
        sequence for the account, bill periods are assumed to correspond
        exactly to calendar months. This is NOT related to the approximate
        billing month.'''
        # get all reebills whose periods contain any days in this month, and
        # their sequences (there should be at most 3)
        session = Session()
        query_month = Month(year, month)
        sequences_for_month = session.query(ReeBill.sequence).join(UtilBill)\
                .filter(UtilBill.period_start >= query_month.first,
                UtilBill.period_end <= query_month.last).all()

        # get sequence of last reebill and the month in which its period ends,
        # which will be useful below
        last_sequence = self.state_db.last_sequence(account)

        # if there's at least one sequence, return the list of sequences. but
        # if query_month is the month in which the account's last reebill ends,
        # and that period does not perfectly align with the end of the month,
        # also include the sequence of an additional hypothetical reebill whose
        # period would cover the end of the month.
        if sequences_for_month != []:
            last_end = self.state_db.get_reebill(last_sequence
                    ).period_end
            if Month(last_end) == query_month and last_end \
                    < (Month(last_end) + 1).first:
                sequences_for_month.append(last_sequence + 1)
            return sequences_for_month

        # if there are no sequences in this month because the query_month
        # precedes the first reebill's start, or there were never any reebills
        # at all, return []
        if last_sequence == 0 or query_month.last < \
                self.state_db.get_reebill(account, 1).get_period()[0]:
            return []

        # now query_month must exceed the month in which the account's last
        # reebill ends. return the sequence determined by counting real months
        # after the approximate month of the last bill (there is only one
        # sequence in this case)
        last_reebill_end = self.state_db.get_reebill(account,
                last_sequence).get_period()[1]
        return [last_sequence + (query_month - Month(last_reebill_end))]


    def all_names_of_accounts(self, accounts):
        # get list of customer name dictionaries sorted by their billing account
        all_accounts_all_names = self.nexus_util.all_names_for_accounts(accounts)
        name_dicts = sorted(all_accounts_all_names.iteritems())
        return name_dicts


    def get_all_utilbills_json(self, account, start=None, limit=None):
        # result is a list of dictionaries of the form {account: account
        # number, name: full name, period_start: date, period_end: date,
        # sequence: reebill sequence number (if present)}
        utilbills, total_count = self.state_db.list_utilbills(account,
                start, limit)
        data = [ub.column_dict() for ub in utilbills]
        return data, total_count

    def update_reebill_readings(self, account, sequence):
        '''Replace the readings of the reebill given by account, sequence
        with a new set of readings that matches the reebill's utility bill.
        '''
        reebill = self.state_db.get_reebill(account, sequence)
        if reebill.issued:
            raise IssuedBillError("Can't modify an issued reebill")
        if reebill.processed:
            raise ProcessedBillError("Can't modify processed reebill")
        reebill.replace_readings_from_utility_bill_registers(reebill.utilbill)

    def bind_renewable_energy(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        if reebill.issued:
            raise IssuedBillError("Can't modify an issued reebill")
        if reebill.processed:
            raise ProcessedBillError("Can't modify processed reebill")
        self.ree_getter.update_renewable_readings(
                self.nexus_util.olap_id(account), reebill, use_olap=True)

    def mail_reebills(self, account, sequences, recipient_list):
        all_reebills = [self.state_db.get_reebill(account, sequence)
                for sequence in sequences]

        # render all the bills
        for reebill in all_reebills:
            the_path = self.billupload.get_reebill_file_path(account,
                    reebill.sequence)
            dirname, basename = os.path.split(the_path)
            self.renderer.render_max_version(reebill.customer.account,
                    reebill.sequence, dirname, basename)

        # "the last element" (???)
        most_recent_reebill = all_reebills[-1]
        bill_file_names = ["%.5d_%.4d.pdf" % (int(account), int(sequence)) for
                sequence in sequences]
        bill_dates = ', '.join(["%s" % (b.get_period()[0])
                for b in all_reebills])
        merge_fields = {
            'street': most_recent_reebill.service_address.street,
            'balance_due': round(most_recent_reebill.balance_due, 2),
            'bill_dates': bill_dates,
            'last_bill': bill_file_names[-1],
        }
        bill_file_paths = [self.billupload.get_reebill_file_path(account,
                    s) for s in sequences]
        self.bill_mailer.mail(recipient_list, merge_fields, bill_file_paths,
                bill_file_paths)

    def get_issuable_reebills_dict(self, processed=False):
        """ Returns a list of issuable reebill dictionaries
            of the earliest unissued version-0 reebill account. If
            proccessed == True, only processed Reebills are returned
            account can be used to get issuable bill for an account
        """
        session = Session()
        unissued_v0_reebills = session.query(ReeBill.sequence, ReeBill.customer_id)\
                .filter(ReeBill.issued == 0, ReeBill.version == 0)
        if processed is True:
            unissued_v0_reebills = unissued_v0_reebills.filter(
                ReeBill.processed == 1)
        unissued_v0_reebills = unissued_v0_reebills.subquery()
        min_sequence = session.query(
                unissued_v0_reebills.c.customer_id.label('customer_id'),
                func.min(unissued_v0_reebills.c.sequence).label('sequence'))\
                .group_by(unissued_v0_reebills.c.customer_id).subquery()
        reebills = session.query(ReeBill)\
                .filter(ReeBill.customer_id==min_sequence.c.customer_id)\
                .filter(ReeBill.sequence==min_sequence.c.sequence)

        issuable_reebills = [r.column_dict() for r in reebills.all()]
        return issuable_reebills

    def issue_and_mail(self, apply_corrections, account=None,
                       sequence=None, recipients=None,
                       processed=False):
        """If account, sequence, and recipients are given,
        this function issues a single reebill and sends out a confirmation
        email. If processed is given, this function  issues and mails all
        processed Reebills instead
        """
        if processed:
            assert sequence is None and account is None and recipients is None
            bills = self.get_issuable_reebills_dict(processed=True)
        else:
            assert not (
                sequence is None and account is None and recipients is None)
            bills = [{'account': account, 'sequence': sequence,
                      'mailto': recipients}]


        for bill in bills:
            # If there are unissued corrections and the user has not confirmed
            # to issue them, we will return a list of those corrections and the
            # sum of adjustments that have to be made so the client can create
            # a confirmation message

            unissued_corrections = self.get_unissued_corrections(bill['account'])
            if len(unissued_corrections) > 0 and not apply_corrections:
                # The user has confirmed to issue unissued corrections.
                return {
                    'success': False,
                    'unissued_corrections': [c[0] for c in
                                             unissued_corrections]}

            result = {'issued': []}
            # Let's issue
            if len(unissued_corrections) > 0:
                assert apply_corrections is True
                try:
                    self.issue_corrections(bill['account'], bill['sequence'])
                except Exception, e:
                    self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                        bill['account'], bill['sequence'],
                        e.__class__.__name__),) + e.args)
                    raise
                for cor in unissued_corrections:
                    result['issued'].append((
                        bill['account'], cor[0],
                        self.state_db.max_version(bill['account'], cor[0])
                    ))

            try:
                if not processed:
                    self.compute_reebill(bill['account'], bill['sequence'])
                self.issue(bill['account'], bill['sequence'])
                result['issued'].append((
                    bill['account'], bill['sequence'], 0, bill['mailto']))
            except Exception, e:
                self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                        bill['account'], bill['sequence'],
                        e.__class__.__name__),) + e.args)
                raise

            # Let's mail!
            # Recepients can be a comma seperated list of email addresses
            recipient_list = [rec.strip() for rec in bill['mailto'].split(',')]
            self.mail_reebills(bill['account'], [bill['sequence']],
                               recipient_list)
        return result

    def update_bill_email_recipient(self, account, sequence, recepients):
        """ Finds a particular reebill by account and sequence,
            finds the connected customer and updates the customer's default
            email recipient(s)
        """
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.customer.bill_email_recipient = recepients

    def upload_interval_meter_csv(self, account, sequence, csv_file,
        timestamp_column, timestamp_format, energy_column, energy_unit,
        register_binding, **args):
        '''Takes an upload of an interval meter CSV file (cherrypy file upload
        object) and puts energy from it into the shadow registers of the
        reebill given by account, sequence. Returns reebill version number.
        '''
        reebill = self.state_db.get_reebill(account, sequence)

        # convert column letters into 0-based indices
        if not re.match('[A-Za-z]', timestamp_column):
            raise ValueError('Timestamp column must be a letter')
        if not re.match('[A-Za-z]', energy_column):
            raise ValueError('Energy column must be a letter')
        timestamp_column = ord(timestamp_column.lower()) - ord('a')
        energy_column = ord(energy_column.lower()) - ord('a')

        # extract data from the file (assuming the format of AtSite's
        # example files)
        self.ree_getter.fetch_interval_meter_data(reebill, csv_file.file,
                register_binding=register_binding,
                timestamp_column=timestamp_column,
                energy_column=energy_column,
                timestamp_format=timestamp_format, energy_unit=energy_unit)
        return reebill.version

    def get_utilbill_image_path(self, utilbill_id, resolution):
        utilbill= self.state_db.get_utilbill_by_id(utilbill_id)
        return self.billupload.getUtilBillImagePath(utilbill,resolution)

    def list_account_status(self, account=None):
        """ Returns a list of dictonaries (containing Account, Nexus Codename,
          Casual name, Primus Name, Utility Service Address, Date of last
          issued bill, Days since then and the last event) and the length
          of the list for all accounts. If account is given, the only the
          accounts dictionary is returned """
        grid_data = self.state_db.get_accounts_grid_data(account)
        name_dicts = self.nexus_util.all_names_for_accounts(
            [row[0] for row in grid_data])

        rows_dict = {}
        for acc, _, _, issue_date, rate_class, service_address, periodend in \
                grid_data:
            rows_dict[acc] ={
                'account': acc,
                'codename': name_dicts[acc].get('codename', ''),
                'casualname': name_dicts[acc].get('casualname', ''),
                'primusname': name_dicts[acc].get('primus', ''),
                'lastperiodend': periodend,
                'provisionable': False,
                'lastissuedate': issue_date if issue_date else '',
                'lastrateclass': rate_class if rate_class else '',
                'utilityserviceaddress': str(service_address) if service_address else ''
            }

        if account is not None:
            events = [self.journal_dao.last_event_summary(account)]
        else:
            events = self.journal_dao.get_all_last_events()
        for acc, last_event in events:
            if acc in rows_dict:
                rows_dict[acc]['lastevent'] = last_event

        rows = list(rows_dict.itervalues())
        return len(rows), rows
