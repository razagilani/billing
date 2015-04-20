from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func
from sqlalchemy.sql.expression import desc

from exc import IssuedBillError
from core.model import Address, Session, UtilBill, UtilityAccount
from reebill.reebill_model import ReeBill
from reebill.reebill_model import ReeBillCustomer


class ReeBillDAO(object):

    def get_reebill_customer(self, account):
        session = Session()
        utility_account = session.query(UtilityAccount).filter(
            UtilityAccount.account == account).one()
        return session.query(ReeBillCustomer).filter(
            ReeBillCustomer.utility_account == utility_account).one()

    def max_version(self, account, sequence):
        # surprisingly, it is possible to filter a ReeBill query by a Customer
        # column even without actually joining with Customer. because of
        # func.max, the result is a tuple rather than a ReeBill object.
        session = Session()
        reebills_subquery = session.query(ReeBill).join(ReeBillCustomer) \
            .filter(ReeBill.reebill_customer_id == ReeBillCustomer.id) \
            .join(UtilityAccount) \
            .filter(UtilityAccount.account == account) \
            .filter(ReeBill.sequence == sequence)
        max_version = session.query(func.max(
            reebills_subquery.subquery().columns.version)).one()[0]
        # SQLAlchemy returns None when the reebill row doesn't exist, but that
        # should be reported as an exception
        if max_version == None:
            raise NoResultFound

        # SQLAlchemy returns a "long" here for some reason, so convert to int
        return int(max_version)

    def increment_version(self, account, sequence):
        '''Creates a new reebill with version number 1 greater than the highest
        existing version for the given account and sequence.

        The utility bill(s) of the new version are the same as those of its
        predecessor, but utility bill, UPRS, and document_ids are cleared
        from the utilbill_reebill table, meaning that the new reebill's
        utilbill/UPRS documents are the current ones.

        Returns the new state.ReeBill object.'''
        # highest existing version must be issued
        session = Session()
        current_max_version_reebill = self.get_reebill(account, sequence)
        if current_max_version_reebill.issued != True:
            raise ValueError(("Can't increment version of reebill %s-%s "
                    "because version %s is not issued yet") % (account,
                    sequence, current_max_version_reebill.version))

        new_reebill = ReeBill(current_max_version_reebill.reebill_customer, sequence,
            current_max_version_reebill.version + 1,
            discount_rate=current_max_version_reebill.discount_rate,
            late_charge_rate=current_max_version_reebill.late_charge_rate,
            utilbills=current_max_version_reebill.utilbills)

        # copy "sequential account info"
        new_reebill.billing_address = current_max_version_reebill\
            .billing_address.clone()
        new_reebill.service_address = current_max_version_reebill\
            .service_address.clone()
        new_reebill.discount_rate = current_max_version_reebill.discount_rate
        new_reebill.late_charge_rate = \
                current_max_version_reebill.late_charge_rate

        # copy readings (rather than creating one for every utility bill
        # register, which may not be correct)
        new_reebill.update_readings_from_reebill(
                current_max_version_reebill.readings)

        for ur in new_reebill._utilbill_reebills:
            ur.document_id, ur.uprs_id, = None, None

        session.add(new_reebill)
        return new_reebill

    def get_original_version(self, reebill):
        """Return a ReeBill object that is "the same bill" as the given one,
        but has version 0, meaning it is not a corrected version.
        """
        result = Session().query(ReeBill).filter_by(
            reebill_customer_id=reebill.reebill_customer_id,
            sequence=reebill.sequence, version=0).one()
        if reebill.version == 0:
            assert result is reebill
        return result

    def get_predecessor(self, reebill, version='max'):
        q = Session().query(ReeBill).filter_by(
            reebill_customer_id=reebill.reebill_customer_id,
            sequence=reebill.sequence - 1)
        if version == 'max':
            result = q.order_by(desc(ReeBill.version)).first()
        else:
            assert isinstance(version, int)
            result = q.filter(ReeBill.version==version).first()
        assert (result is None) == (reebill.sequence == 1)
        return result

    def get_unissued_corrections(self, account):
        '''Returns a list of (sequence, version) pairs for bills that have
        versions > 0 that have not been issued.'''
        session = Session()
        reebills = session.query(ReeBill).join(ReeBillCustomer) \
            .join(UtilityAccount) \
            .filter(UtilityAccount.account == account) \
            .filter(ReeBill.version > 0) \
            .filter(ReeBill.issued == False).order_by(ReeBill.sequence).all()
        return [(int(reebill.sequence), int(reebill.version)) for reebill
                in reebills]

    def last_sequence(self, account):
        '''Returns the sequence of the last reebill for 'account', or 0 if
        there are no reebills.'''
        session = Session()
        reebill_customer = self.get_reebill_customer(account)
        max_sequence = session.query(func.max(ReeBill.sequence)) \
            .filter(ReeBill.reebill_customer_id == reebill_customer.id).one()[0]
        # TODO: because of the way 0.xml templates are made (they are not in
        # the database) reebill needs to be primed otherwise the last sequence
        # for a new bill is None. Design a solution to this issue.
        if max_sequence is None:
            max_sequence = 0
        return max_sequence

    # deprecated: do not use!
    def issue(self, account, sequence, issue_date=None):
        '''Marks the highest version of the reebill given by account, sequence
        as issued.
        '''
        reebill = self.get_reebill(account, sequence)
        if issue_date is None:
            issue_date = datetime.utcnow()
        if reebill.issued == True:
            raise IssuedBillError(("Can't issue reebill %s-%s-%s because it's "
                    "already issued") % (account, sequence, reebill.version))
        reebill.issued = True
        reebill.processed = True
        reebill.issue_date = issue_date

    def is_issued(self, account, sequence, version='max'):
        '''Returns true if the reebill given by account, sequence, and version
        (latest version by default) has been issued, false otherwise. If
        'nonexistent' is given, that value will be returned if the reebill is
        not present in the state database (e.g. False when you want
        non-existent bills to be treated as unissued).'''
        # NOTE: with the old database schema (one reebill row for all versions)
        # this method returned False when the 'version' argument was higher
        # than max_version. that was probably the wrong behavior, even though
        # test_state:StateDBTest.test_versions tested for it.
        if version == 'max':
            reebill = self.get_reebill(account, sequence)
        elif isinstance(version, int):
            reebill = self.get_reebill(account, sequence, version)
        else:
            raise ValueError('Unknown version specifier "%s"' % version)
        # NOTE: reebill.issued is an int, and it converts the entire
        # expression to an int unless explicitly cast! see
        # https://www.pivotaltracker.com/story/show/35965271
        return bool(reebill.issued == True)

    def account_exists(self, account):
        session = Session()
        try:
           session.query(UtilityAccount).with_lockmode("read")\
                .filter(UtilityAccount.account == account).one()
        except NoResultFound:
            return False
        return True

    def get_all_reebills_for_account(self, account):
        """
        Returns a list of all Reebill objects for 'account' (string).
        odered by sequence and version ascending
        """
        session = Session()
        query = session.query(ReeBill).join(ReeBillCustomer).join(
            UtilityAccount).filter(UtilityAccount.account == account)\
            .order_by(ReeBill.sequence.asc(), ReeBill.version.asc())
        return query.all()

    def get_reebill(self, account, sequence, version='max'):
        '''Returns the ReeBill object corresponding to the given account,
        sequence, and version (the highest version if no version number is
        given).'''
        session = Session()
        if version == 'max':
            version = session.query(func.max(ReeBill.version)).join(
                ReeBillCustomer).join(UtilityAccount)\
                .filter(UtilityAccount.account == account) \
                .filter(ReeBill.sequence == sequence).one()[0]
        result = session.query(ReeBill).join(ReeBillCustomer)\
            .join(UtilityAccount) \
            .filter(UtilityAccount.account == account) \
            .filter(ReeBill.sequence == sequence) \
            .filter(ReeBill.version == version).one()
        return result

    def get_reebill_by_id(self, rbid):
        session = Session()
        return session.query(ReeBill).filter(ReeBill.id == rbid).one()

    # missing coverage because only called by dead code
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
        sequences_for_month = session.query(ReeBill.sequence).join(UtilBill) \
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

