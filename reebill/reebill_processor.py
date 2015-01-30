import os
import traceback
import re
from datetime import datetime, timedelta

from sqlalchemy.sql import desc, functions
from sqlalchemy import not_, and_
from sqlalchemy import func

from core.model import (UtilBill, Address, Session,
                           MYSQLDB_DATETIME_MIN, UtilityAccount)
from reebill.state import (ReeBill, ReeBillCharge, Reading, ReeBillCustomer)
from exc import IssuedBillError, NotIssuable, \
    NoSuchBillException, ConfirmAdjustment, FormulaError, RegisterError
from core.utilbill_processor import ACCOUNT_NAME_REGEX


class ReebillProcessor(object):
    ''''Does a mix of the following things:
    - Operations on reebills: create, delete, compute, etc.
    etc.
    - CRUD on child objects of ReeBill that are closely associated
    with ReeBills, like ReeBillCharges and Readings.
    - CRUD on Payments.
    - CRUD on ReeBillCustomers.
    - Generating JSON data for the ReeBill UI.
    Each of these things should be separated into its own class (especially
    the UI-related methods), except maybe the first two can stay in the same
    class.
    '''
    def __init__(self, state_db, payment_dao, nexus_util, bill_mailer,
                 reebill_file_handler, ree_getter, journal_dao, logger=None):
        self.state_db = state_db
        self.payment_dao = payment_dao
        self.nexus_util = nexus_util
        self.bill_mailer = bill_mailer
        self.ree_getter = ree_getter
        self.reebill_file_handler = reebill_file_handler
        self.logger = logger
        self.journal_dao = journal_dao

    # TODO rename this to something that makes sense
    def get_hypothetical_matched_charges(self, reebill_id):
        """Gets all hypothetical charges from a reebill for a service and
        matches the actual charge to each hypotheitical charge
        TODO: This method has no test coverage!"""
        reebill = self.state_db.get_reebill_by_id(reebill_id)
        return [{
            'rsi_binding': reebill_charge.rsi_binding,
            'description': reebill_charge.description,
            'actual_quantity': reebill_charge.a_quantity,
            'quantity': reebill_charge.h_quantity,
            'unit': reebill_charge.unit,
            'rate': reebill_charge.rate,
            'actual_total': reebill_charge.a_total,
            'total': reebill_charge.h_total,
        } for reebill_charge in reebill.charges]

    def get_sequential_account_info(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        return {
            'billing_address': reebill.billing_address.to_dict(),
            'service_address': reebill.service_address.to_dict(),
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
        reebill.check_editable()

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

    def compute_reebill(self, account, sequence, version='max'):
        '''Loads, computes, and saves the reebill
        '''
        reebill = self.state_db.get_reebill(account, sequence,
                version)
        reebill.check_editable()
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
                payments = self.payment_dao.get_total_payment_since(
                        account, MYSQLDB_DATETIME_MIN, payment_objects=True)
                self.compute_reebill_payments(payments, reebill)
            else:
                payments = self.payment_dao.get_total_payment_since(
                        account, MYSQLDB_DATETIME_MIN, end=present_v0_issue_date,
                        payment_objects=True)
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
            # predecessor's version 0 and issue date of current reebill's
            # version 0 (if current reebill is unissued, its version 0 has
            # None as its issue_date, meaning the payment period lasts up
            # until the present)
            if predecessor.issued:
                # if predecessor's version 0 is issued, gather all payments from
                # its issue date until version 0 issue date of current bill, or
                # today if this bill has never been issued
                if self.state_db.is_issued(account, reebill.sequence,
                        version=0):
                    present_v0_issue_date = self.state_db.get_reebill(account,
                            reebill.sequence, version=0).issue_date
                    payments = self.payment_dao.get_total_payment_since(
                        account, predecessor.issue_date,
                        end=present_v0_issue_date, payment_objects=True)
                    self.compute_reebill_payments(payments, reebill)
                else:
                    payments = self.payment_dao. \
                            get_total_payment_since(account,
                            predecessor.issue_date, payment_objects=True)
                    self.compute_reebill_payments(payments, reebill)
            else:
                # if predecessor is not issued, there's no way to tell what
                # payments will go in this bill instead of a previous bill, so
                # assume there are none (all payments since last issue date
                # go in the account's first unissued bill)
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
        reebill.payment_received = float(
                sum(payment.credit for payment in payments))

    def roll_reebill(self, account, start_date=None):
        """ Create first or roll the next reebill for given account.
        After the bill is rolled, this function also binds renewable energy data
        and computes the bill by default. This behavior can be modified by
        adjusting the appropriate parameters.
        'start_date': must be given for the first reebill.
        """
        session = Session()

        reebill_customer = self.state_db.get_reebill_customer(account)
        last_reebill_row = session.query(ReeBill)\
                .filter(ReeBill.reebill_customer == reebill_customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version)).first()

        new_utilbills = []
        if last_reebill_row is None:
            # No Reebills are associated with this account: Create the first one
            assert start_date is not None
            utilbill = session.query(UtilBill)\
                    .filter(UtilBill.utility_account ==
                            reebill_customer.utility_account)\
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
                    .filter(UtilBill.utility_account == reebill_customer.utility_account)\
                    .filter(not_(UtilBill._utilbill_reebills.any()))\
                    .filter(UtilBill.service == utilbill.service)\
                    .filter(UtilBill.utility == utilbill.utility)\
                    .filter(UtilBill.period_start >= utilbill.period_end)\
                    .order_by(UtilBill.period_end).first()
                if successor is None:
                    raise NoSuchBillException(("Couldn't find next "
                            "utility bill following %s") % utilbill)
                new_utilbills.append(successor)
            new_sequence = last_reebill_row.sequence + 1

        # currently only one service is supported
        assert len(new_utilbills) == 1

        # create reebill row in state database
        new_reebill = ReeBill(reebill_customer, new_sequence, 0,
                              utilbills=new_utilbills,
                              billing_address=Address.from_other(
                                new_utilbills[0].billing_address),
                              service_address=Address.from_other(
                                new_utilbills[0].service_address))

        # assign Reading objects to the ReeBill based on registers from the
        # utility bill document
        if last_reebill_row is None:
            # this is the first reebill: choose only REG_TOTAL complain if it
            # doesn't exist
            try:
                reg_total_register = next(r for r in utilbill.registers if
                                          r.register_binding == 'REG_TOTAL')
            except StopIteration:
                raise RegisterError('The utility bill must have a register '
                                    'called "REG_TOTAL"')
            new_reebill.readings = [Reading.make_reading_from_register(
                reg_total_register)]
        else:
            # not the first reebill: copy readings from the previous one
            new_reebill.update_readings_from_reebill(last_reebill_row.readings)
            new_reebill.copy_reading_conventional_quantities_from_utility_bill()
        session.add(new_reebill)
        session.add_all(new_reebill.readings)

        self.ree_getter.update_renewable_readings(
                self.nexus_util.olap_id(account), new_reebill, use_olap=True)

        try:
            self.compute_reebill(account, new_sequence)
        except FormulaError as e:
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
                    reebill.version, reebill.get_account(),
                    reebill.sequence, e, traceback.format_exc()))

        return reebill

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
        reebill = self.state_db.get_reebill(account, target_sequence,
                                            target_max_version)
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

    def get_late_charge(self, reebill, day=None):
        '''Returns the late charge for the given reebill on 'day', which is the
        present by default. ('day' will only affect the result for a bill that
        hasn't been issued yet: there is a late fee applied to the balance of
        the previous bill when only when that previous bill's due date has
        passed.) Late fees only apply to bills whose predecessor has been
        issued; 0 is returned if the predecessor has not been issued. (The
        first bill and the sequence 0 template bill always have a late charge
        of 0.)'''
        session = Session()
        if day is None:
            day = datetime.utcnow().date()
        acc, seq = reebill.get_account(), reebill.sequence

        if reebill.sequence <= 1:
            return 0

        # unissued bill has no late charge
        if not self.state_db.is_issued(acc, seq - 1):
            return 0

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
        reebill_customer = self.state_db.get_reebill_customer(acc)
        min_balance_due = session.query(func.min(ReeBill.balance_due))\
                .filter(ReeBill.reebill_customer == reebill_customer)\
                .filter(ReeBill.sequence == seq - 1).one()[0]
        source_balance = min_balance_due - \
                self.payment_dao.get_total_payment_since(acc,
                predecessor0.issue_date)
        #Late charges can only be positive
        return (reebill.late_charge_rate) * max(0, source_balance)

    def delete_reebill(self, account, sequence):
        '''Deletes the the given reebill and its utility bill associations.
        A reebill version has been issued can't be deleted. Returns the version
        of the reebill that was deleted.'''
        session = Session()
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()
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
            self.reebill_file_handler.delete_file(reebill, ignore_missing=True)
        return version

    def create_new_account(self, account, name, service_type, discount_rate,
            late_charge_rate, billing_address, service_address,
            template_account, utility_account_number):
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
        if service_type not in (None,) + ReeBillCustomer.SERVICE_TYPES:
            raise ValueError('Unknown service type "%s"' % service_type)

        session = Session()
        template_utility_account = session.query(UtilityAccount).filter_by(
                account=template_account).one()
        last_utility_bill = session.query(UtilBill)\
                .join(UtilityAccount).filter(UtilBill.utility_account==template_utility_account)\
                .order_by(desc(UtilBill.period_end)).first()
        if last_utility_bill is None:
            utility = template_utility_account.fb_utility
            supplier = template_utility_account.fb_supplier
            rate_class = template_utility_account.fb_rate_class
        else:
            utility = last_utility_bill.utility
            supplier = last_utility_bill.supplier
            rate_class = last_utility_bill.rate_class

        new_utility_account = UtilityAccount(
            name, account, utility, supplier, rate_class,
            Address(billing_address['addressee'],
                    billing_address['street'],
                    billing_address['city'],
                    billing_address['state'],
                    billing_address['postal_code']),
            Address(service_address['addressee'],
                    service_address['street'],
                    service_address['city'],
                    service_address['state'],
                    service_address['postal_code']),
                    account_number=utility_account_number)

        session.add(new_utility_account)

        if service_type is not None:
            new_reebill_customer = ReeBillCustomer(
                name, discount_rate, late_charge_rate, service_type,
                'example@example.com', new_utility_account)
            session.add(new_reebill_customer)
            session.flush()
            return new_reebill_customer

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
            self.compute_reebill(reebill.get_account(), reebill.sequence,
                                 version=reebill.version)

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
        reebill.email_recipient = reebill.reebill_customer.bill_email_recipient

    def update_reebill_readings(self, account, sequence):
        '''Replace the readings of the reebill given by account, sequence
        with a new set of readings that matches the reebill's utility bill.
        '''
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()
        reebill.replace_readings_from_utility_bill_registers(reebill.utilbill)
        return reebill

    def bind_renewable_energy(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()
        self.ree_getter.update_renewable_readings(
                self.nexus_util.olap_id(account), reebill, use_olap=True)

    def mail_reebills(self, account, sequences, recipient_list):
        all_reebills = [self.state_db.get_reebill(account, sequence)
                for sequence in sequences]

        # render all the bills
        for reebill in all_reebills:
            self.reebill_file_handler.render(reebill)

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
        bill_file_paths = [self.reebill_file_handler.get_file_path(r)
                for r in all_reebills]
        bill_file_dir_path = os.path.dirname(bill_file_paths[0])
        self.bill_mailer.mail(recipient_list, merge_fields, bill_file_dir_path,
                bill_file_paths)

    def _get_issuable_reebills(self):
        '''Return a Query of "issuable" reebills (lowest-sequence bill for
        each account that is unissued and is not a correction).
        '''
        session = Session()
        unissued_v0_reebills = session.query(
            ReeBill.sequence, ReeBill.reebill_customer_id).filter(
            ReeBill.issued == 0, ReeBill.version == 0)
        unissued_v0_reebills = unissued_v0_reebills.subquery()
        min_sequence = session.query(
            unissued_v0_reebills.c.reebill_customer_id.label(
                'reebill_customer_id'),
            func.min(unissued_v0_reebills.c.sequence).label('sequence')) \
            .group_by(unissued_v0_reebills.c.reebill_customer_id).subquery()
        return session.query(ReeBill).filter(
            ReeBill.reebill_customer_id == min_sequence.c.reebill_customer_id) \
            .filter(ReeBill.sequence == min_sequence.c.sequence)

    def get_issuable_reebills_dict(self):
        """ Returns a list of issuable reebill dictionaries
            of the earliest unissued version-0 reebill account. If
            proccessed == True, only processed Reebills are returned
            account can be used to get issuable bill for an account
        """
        return [r.column_dict() for r in self.get_issuable_reebills().all()]

    def issue_and_mail(self, apply_corrections, account, sequence,
                       recipients=None):
        """this function issues a single reebill and sends out a confirmation
        email.
        """
        # If there are unissued corrections and the user has not confirmed
        # to issue them, we will return a list of those corrections and the
        # sum of adjustments that have to be made so the client can create
        # a confirmation message
        unissued_corrections = self.get_unissued_corrections(account)
        if len(unissued_corrections) > 0 and not apply_corrections:
            # The user has confirmed to issue unissued corrections.
            sequences = [sequence for sequence, _, _
                        in unissued_corrections]
            total_adjustment = sum(adjustment
                        for _, _, adjustment in unissued_corrections)
            raise ConfirmAdjustment(sequences, total_adjustment)
        # Let's issue
        if len(unissued_corrections) > 0:
            assert apply_corrections is True
            try:
                self.issue_corrections(account, sequence)
            except Exception as e:
                self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                    account, sequence,
                    e.__class__.__name__),) + e.args)
                raise
        try:
            session = Session()
            reebill_object = (session.query(ReeBill)
                    .join(ReeBillCustomer)
                    .join(UtilityAccount)
                    .filter(UtilityAccount.account==account)
                    .filter(ReeBill.sequence==sequence)
                    .order_by(desc(ReeBill.version)).first())
            if not reebill_object.processed:
                self.compute_reebill(account, sequence)
            self.issue(account, sequence)
        except Exception, e:
            self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                    account, sequence,
                    e.__class__.__name__),) + e.args)
            raise
        # Let's mail!
        # Recepients can be a comma seperated list of email addresses
        if recipients is None:
            # this is not supposed to be allowed but somehow it happens
            # in a test
            recipient_list = ['']
        else:
            recipient_list = [rec.strip() for rec in
                              recipients.split(',')]
        self.mail_reebills(account, [sequence],
                           recipient_list)
        return reebill_object

    def issue_processed_and_mail(self, apply_corrections):
        '''This function issues all processed reebills'''
        bills = self._get_issuable_reebills().filter_by(processed=True).all()
        for bill in bills:
            # If there are unissued corrections and the user has not confirmed
            # to issue them, we will return a list of those corrections and the
            # sum of adjustments that have to be made so the client can create
            # a confirmation message
            unissued_corrections = self.get_unissued_corrections(
                bill.reebill_customer.utility_account.account)
            if len(unissued_corrections) > 0 and not apply_corrections:
                # The user has confirmed to issue unissued corrections.
                sequences = [sequence for sequence, _, _
                            in unissued_corrections]
                total_adjustment = sum(adjustment
                            for _, _, adjustment in unissued_corrections)
                raise ConfirmAdjustment(sequences, total_adjustment)
            # Let's issue
            if len(unissued_corrections) > 0:
                assert apply_corrections is True
                try:
                    self.issue_corrections(bill.get_account(), bill.sequence)
                except Exception as e:
                    self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                        bill.get_account(), bill.sequence,
                        e.__class__.__name__),) + e.args)
                    raise
            try:
                self.issue(bill.get_account(), bill.sequence)
            except Exception, e:
                self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                        bill.get_accont(), bill.sequence,
                        e.__class__.__name__),) + e.args)
                raise
            # Let's mail!
            # Recepients can be a comma seperated list of email addresses
            if bill.email_recipient is None:
                # this is not supposed to be allowed but somehow it happens
                # in a test
                recipient_list = ['']
            else:
                recipient_list = [rec.strip() for rec in
                                  bill.email_recipient.split(',')]
            self.mail_reebills(bill.get_account(), [bill.sequence],
                               recipient_list)
        bills_dict = [bill.column_dict() for bill in bills]
        return bills_dict

    # TODO this method has no test coverage. maybe combine it into
    # update_sequential_account_info and add to the test for that
    def update_bill_email_recipient(self, account, sequence, recepients):
        """ Finds a particular reebill by account and sequence,
            finds the connected customer and updates the customer's default
            email recipient(s)
        """
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.reebill_customer.bill_email_recipient = recepients

    def render_reebill(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        self.reebill_file_handler.render(reebill)
        
    def toggle_reebill_processed(self, account, sequence,
                apply_corrections):
        '''Make the reebill given by account, sequence, processed if
        it is not processed or un-processed if it is processed. If there are
        un-issued corrections for the given account, 'apply_corrections' must
        be True or ConfirmAdjustment will be raised.
        '''
        session = Session()
        reebill = self.state_db.get_reebill(account, sequence)

        if reebill.issued:
            raise IssuedBillError("Can't modify an issued bill")

        issuable_reebill = session.query(ReeBill).join(ReeBillCustomer) \
                .join(UtilityAccount)\
                .filter(UtilityAccount.account==account)\
                .filter(ReeBill.version==0, ReeBill.issued==False)\
                .order_by(ReeBill.sequence).first()

        if reebill.processed:
            reebill.processed = False
        else:
            if reebill == issuable_reebill:
                unissued_corrections = self.get_unissued_corrections(account)

                # if there are corrections that are not already processed and
                # user has not confirmed applying
                # them, send back data for a confirmation message
                unprocessed_corrections = False
                for sequence, version, _ in unissued_corrections:
                    correction = self.state_db.get_reebill(account, sequence,
                                                           version)
                    if not correction.processed:
                        unprocessed_corrections = True
                        break
                if len(unissued_corrections) > 0 and unprocessed_corrections \
                        and not apply_corrections:
                    sequences = [sequence for sequence, _, _
                            in unissued_corrections]
                    total_adjustment = sum(adjustment
                            for _, _, adjustment in unissued_corrections)
                    raise ConfirmAdjustment(sequences, total_adjustment)

                # otherwise, mark corrected bills as processed
                if unprocessed_corrections:
                    for sequence, version, _ in unissued_corrections:
                        unissued_reebill = self.state_db.get_reebill(account,
                                                                     sequence)
                        if not unissued_reebill.processed:
                            self.compute_reebill(account, sequence)
                            unissued_reebill.processed = True

            self.compute_reebill(account, reebill.sequence)
            reebill.processed = True

