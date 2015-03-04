"""SQLAlchemy model classes and other business objects for both
brokerage-related data and for the "Bill Entry" application.

It might be a good idea to separate these.
"""
import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, class_mapper
from core.model import Base, UtilityAccount, UtilBill

class BrokerageAccount(Base):
    '''Table for storing Power & Gas-related data associated with a
    UtilityAccount. May represent the same thing as one of the "accounts",
    "customers" etc. in other databases. The current purpose is only to keep
    track of which UtilityAccounts are "PG related" for exporting PG data.
    '''
    __tablename__ = 'brokerage_account'
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'),
                                primary_key=True)
    utility_account = relationship(UtilityAccount)

    def __init__(self, utility_account):
        self.utility_account = utility_account

class BillEntryUser(Base):
    """Placeholder for table for users of the BillEntry application.
    """
    __tablename__ = 'billentry_user'
    id = Column(Integer, primary_key=True)

    # TODO: add necessary columns. right now this only exists because it's
    # required by billentry_event.

class BEUtilBill(UtilBill):
    """UtilBill subclass that tracks when a bill became "entered" in the
    Bill Entry application and by whom.
    """
    POLYMORPHIC_IDENTITY = 'beutilbill'

    __mapper_args__ = {
        # single-table inheritance
        'polymorphic_identity': 'beutilbill',
        'polymorphic_on': 'discriminator',
    }

    billentry_date = Column(DateTime)
    billentry_user_id = Column(Integer, ForeignKey('billentry_user.id'))
    billentry_user = relationship(BillEntryUser)

    def __init__(self, *args, **kwargs):
        """No-argument constructor is necessary for create_from_utilbill.
        """
        pass

    @classmethod
    def create_with_utilbill_args(cls, utility_account, state, utility, supplier,
                                  rate_class, billing_address, service_address,
                                  period_start=None, period_end=None,
                                  target_total=0, date_received=None,
                                  processed=False, sha256_hexdigest='',
                                  due_date=None, next_meter_read_date=None):
        """UtilBill constructor interface."""
        new_instance = cls()
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        new_instance.utility_account = utility_account
        new_instance.state = state
        new_instance.utility = utility
        new_instance.rate_class = rate_class
        new_instance.supplier = supplier
        new_instance.billing_address = billing_address
        new_instance.service_address = service_address
        new_instance.period_start = period_start
        new_instance.period_end = period_end
        new_instance.target_total = target_total
        new_instance.date_received = date_received
        new_instance.processed = processed
        new_instance.due_date = due_date
        new_instance.account_number = utility_account.account_number
        new_instance.next_meter_read_date = next_meter_read_date

        # TODO: empty string as default value for sha256_hexdigest is
        # probably a bad idea. if we are writing tests that involve putting
        # UtilBills in an actual database then we should probably have actual
        # files for them.
        new_instance.sha256_hexdigest = sha256_hexdigest

        new_instance.date_modified = datetime.utcnow()

    @classmethod
    def create_from_utilbill(cls, utilbill):
        """Return a new BEUtilBill, identical to 'utilbill' except for its
        class.
        """
        print type(UtilBill)
        assert type(utilbill) is UtilBill
        assert utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY
        new_beutilbill = BEUtilBill()
        for col_name in UtilBill.column_names():
            if col_name in ('id', ):
                continue
            # NOTE it should be OK to share the same child objects between
            # 'utilbill' and 'new_beutilbill' because utilbill is going to be
            #  deleted
            setattr(new_beutilbill, col_name, getattr(UtilBill, col_name))
        return new_beutilbill

    def get_user(self):
        return self.billentry_user

    def get_date(self):
        return self.billentry_date

    def enter(self, user, date):
        """Mark an "un-entered" bill as "entered" by the given user at a
        particular datetime.
        """
        assert not self.is_entered()
        self.billentry_date = date
        self.billentry_user = user

    def un_enter(self):
        """Mark an "entered" bill as an "un-entered" by clearing data about
        bill entry.
        """
        assert self.is_entered()
        self.billentry_date = None
        self.billentry_user = None

    def is_entered(self):
        """Return True if the subset of utility bill's data editable in
        Bill Entry is complete, False otherwise. This probably also means the
        bill is complete enough to be submitted to request quotes for brokerage
        customers.

        Any bill that is "processed" is also "entered", even if it has no
        'billentry_date' or 'billentry_user'.

        If True, the following data about the bill can be considered accurate:
        - period_start
        - period_end
        - utility
        - rate class
        - supplier
        - supply_choice_id
        - total energy, i.e. 'quantity' field of the Register whose
          'register_binding' is "REG_TOTAL"
        - target_total
        - existence and 'rsi_binding' of supply charges
        - 'target_total' of supply charges
        """
        # consistency check: all values must be either None or filled in
        entry_values = (self.billentry_date, self.billentry_user)
        assert all(x is None for x in entry_values) or all(
            x is not None for x in entry_values)

        return self.processed or (self.billentry_date is not None)

