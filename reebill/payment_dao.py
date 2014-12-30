from datetime import datetime

from sqlalchemy import and_

from billing.core.model import Session, UtilityAccount
from billing.reebill.state import ReeBillCustomer, Payment


class PaymentDAO(object):
    def create_payment(self, account, date_applied, description,
                       credit, date_received=None):
        '''Adds a new payment, returns the new Payment object. By default,
        'date_received' is the current datetime in UTC when this method is
        called; only override this for testing purposes.'''
        # NOTE a default value for 'date_received' can't be specified as a
        # default argument in the method signature because it would only get
        # evaluated once at the time this module was imported, which means its
        # value would be the same every time this method is called.
        if date_received is None:
            date_received = datetime.utcnow()
        session = Session()
        utility_account = session.query(UtilityAccount) \
            .filter(UtilityAccount.account==account).one()
        reebill_customer = session.query(ReeBillCustomer) \
            .filter(ReeBillCustomer.utility_account==utility_account) \
            .one()
        new_payment = Payment(reebill_customer, date_received, date_applied,
                              description, credit)
        session.add(new_payment)
        session.flush()
        return new_payment

    def delete_payment(self, oid):
        '''Deletes the payment with id 'oid'.'''
        session = Session()
        payment = session.query(Payment).filter(Payment.id == oid).one()
        session.delete(payment)

    def find_payment(self, account, periodbegin, periodend):
        '''Returns a list of payment objects whose date_applied is in
        [periodbegin, period_end).'''
        # periodbegin and periodend must be non-overlapping between bills. This
        # is in direct opposition to the reebill period concept, which is a
        # period that covers all services for a given reebill and thus overlap
        # between bills.  Therefore, a non overlapping period could be just the
        # first utility service on the reebill. If the periods overlap,
        # payments will be applied more than once. See 11093293
        session = Session()
        utility_account = session.query(UtilityAccount) \
            .filter(UtilityAccount.account==account).one()
        reebill_customer = session.query(ReeBillCustomer) \
            .filter(ReeBillCustomer.utility_account==utility_account) \
            .one()
        payments = session.query(Payment) \
            .filter(Payment.reebill_customer == reebill_customer) \
            .filter(and_(Payment.date_applied >= periodbegin,
                         Payment.date_applied < periodend)).all()
        return payments

    def get_total_payment_since(self, account, start, end=None, payment_objects=False):
        '''Returns sum of all account's payments applied on or after 'start'
        and before 'end' (today by default). If 'start' is None, the beginning
        of the interval extends to the beginning of time.
        '''
        assert isinstance(start, datetime)
        if end is None:
            end=datetime.utcnow()
        session = Session()
        reebill_customer = session.query(ReeBillCustomer).join(
            UtilityAccount).filter_by(account=account).one()
        payments = session.query(Payment) \
            .filter(Payment.reebill_customer==reebill_customer) \
            .filter(Payment.date_applied < end)
        if start is not None:
            payments = payments.filter(Payment.date_applied >= start)
        if payment_objects:
            return payments.all()
        return float(sum(payment.credit for payment in payments.all()))

    def payments(self, account):
        '''Returns list of all payments for the given account ordered by
        date_received.'''
        session = Session()
        payments = session.query(Payment).join(ReeBillCustomer) \
            .join(UtilityAccount) \
            .filter(UtilityAccount.account == account).order_by(
            Payment.date_received).all()
        return payments

    get_payments = payments

    def get_payments_for_reebill_id(self, reebill_id):
        session = Session()
        payments = session.query(Payment) \
            .filter(Payment.reebill_id == reebill_id).order_by(
            Payment.date_received).all()
        return payments