"""SQLAlchemy model classes and other business objects for both
brokerage-related data and for the "Bill Entry" application.

It might be a good idea to separate these.
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from core.model import Base, UtilityAccount, UtilBill, Session


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

class BillEntryEvent(Base):
    """Table for recording when bills become "entered" and who entered them.
    Named for the Bill Entry application and also because the only event
    is that of a bill becoming entered.
    """
    __tablename__ = 'billentry_event'

    # separate primary key is present just in case there is ever more than
    # one of these per utility bill.
    id = Column(Integer, primary_key=True)

    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), nullable=False)
    date = Column(DateTime, nullable=False)
    billentry_user_id = Column(Integer, ForeignKey('billentry_user.id'),
                               nullable=False)

    utilbill = relationship(UtilBill)
    user = relationship(BillEntryUser)


class BEUtilBill(UtilBill):
    """BillEntry-specific extensions to the core.model.UtilBill class, not added
    there because only BillEntry cares about this.
    """
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

        Any bill that is "processed" is also entered
        """
        # 'processed' is a superset of 'entered', meaning all data can be
        # considered accurate.
        if self.processed:
            return True

        s = Session.object_session(self)
        count = s.query(BillEntryEvent).count()
        if count == 1:
            return True

        assert count == 0
        return False