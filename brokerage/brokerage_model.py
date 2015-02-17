"""SQLAlchemy model classes and other business objects for both
brokerage-related data and for the "Bill Entry" application.

It might be a good idea to separate these.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
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
    __mapper_args__ = {
        # single-table inheritance
        'polymorphic_identity': 'beutilbill',
        'polymorphic_on': 'discriminator',
    }

    billentry_date = Column(DateTime)
    billentry_user_id = Column(Integer, ForeignKey('billentry_user.id'))
    billentry_user = relationship(BillEntryUser)

    def get_user(self):
        return self.billentry_user

    def get_date(self):
        return self.billentry_date

    def enter(self, user, date=None):
        """Mark an "un-entered" bill as "entered" by the given user at a
        particular datetime (defaults to utcnow).
        """
        assert not self.is_entered()
        if date is None:
            date = datetime.utcnow()
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
        """Return True if this utility bill's data are complete enough to be
        used for requesting quotes for brokerage customers, False otherwise.

        If True, the following data about this bill can be considered accurate:
        - period_start
        - period_end
        - utility
        - rate class
        - supplier
        - supply_choice_id
        - total energy, i.e. 'quantity' field of the Register whose
          'register_binding' is "REG_TOTAL"
        - target_total
        - existence and 'rsi_binding' of supply charges (NOT distribution charges)
        - 'target_total' of supply charges (NOT distribution charges)

        Any bill that is "processed" is also entered.
        """
        # consistency check: all values must be either None or filled in
        entry_values = (self.billentry_date, self.billentry_user)
        assert all(x is None for x in entry_values) or all(
            x is not None for x in entry_values)

        return self.processed or (self.billentry_date is not None)

