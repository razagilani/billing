"""SQLAlchemy model classes used by the Bill Entry application.
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from core.model import Base, UtilBill


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

