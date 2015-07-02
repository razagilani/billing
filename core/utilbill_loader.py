from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from core.model import UtilBill, UtilityAccount, Session, RateClass
from exc import NoSuchBillException


class UtilBillLoader(object):
    '''Data access object for utility bills, used to hide database details
    from other classes so they can be more easily tested.
    '''

    def get_utilbill_by_id(self, utilbill_id):
        '''Return utilbill with the given id.'''
        return Session().query(UtilBill).filter_by(id=utilbill_id).one()

    def load_utilbills(self, **kwargs):
        """Load UtilBills matching the criteria given by **kwargs.
        :param: kwargs: UtilBill attributes and their values to filter by,
        or "service" to include only electric or gas bills, or "join" with a
        relationship attribute or list/tuple of attributes to eagerly load
        other tables.
        :return: Query object of UtilBills
        """
        cursor = Session().query(UtilBill)
        for key, value in kwargs.iteritems():
            if key == 'join':
                # list or tuple is requred because general iterable is hard
                # to distinguish from an iterable SQLAlchemy attribute
                if not isinstance(value, (list, tuple)):
                    value = [value]
                for attr in value:
                    cursor = cursor.options(joinedload(attr))
            elif key == 'service':
                cursor = cursor.join(RateClass).filter(
                    RateClass.service == value)
            else:
                cursor = cursor.filter(getattr(UtilBill, key) == value)
        return cursor

    def get_last_real_utilbill(self, account, end=None, service=None,
            utility=None, rate_class=None, processed=None):
        '''Returns the latest-ending UtilBill, optionally limited to those
        whose end date is before/on 'end', and optionally with
        the given service, utility, rate class, and 'processed' status.
        '''
        utility_account = Session().query(UtilityAccount).filter_by(
            account=account).one()
        cursor = Session().query(UtilBill) \
            .filter(UtilBill.utility_account == utility_account)
        if end is not None:
            cursor = cursor.filter(UtilBill.period_end <= end)
        if service is not None:
            cursor = cursor.join(RateClass).filter(
                RateClass.service == service)
        if utility is not None:
            cursor = cursor.filter(UtilBill.utility == utility)
        if rate_class is not None:
            cursor = cursor.filter(UtilBill.rate_class == rate_class)
        if processed is not None:
            assert isinstance(processed, bool)
            cursor = cursor.filter(UtilBill.processed == processed)
        result = cursor.order_by(desc(UtilBill.period_end)).first()
        if result is None:
            raise NoSuchBillException
        return result

    def count_utilbills_with_hash(self, hash):
        '''Return the number of utility bills having the given SHA-256 hash.
        '''
        return Session().query(UtilBill).filter_by(
            sha256_hexdigest=hash).count()

    def get_utilbills_for_account_id(self, utility_account_id):
        '''Return an iterator containing utility bills whose UtilityAccount
        is identified by utility_account_id.
        '''
        return Session().query(UtilBill).join(
            UtilityAccount).filter(UtilityAccount.id == utility_account_id)

