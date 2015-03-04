"""SQLAlchemy model classes and other business objects for both
brokerage-related data and for the "Bill Entry" application.

It might be a good idea to separate these.
"""
import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, backref
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
    password = Column(String(10))
    email = Column(String(50),unique=True, index=True)
    registered_on = Column('registered_on', DateTime)
    authenticated = Column(Boolean, default=False)

    # association proxy of "role_beuser" collection
    # to "role" attribute
    roles = association_proxy('role_beuser', 'role')


    def __init__(self, email='', password=''):
        self.email = email
        self.password = password
        self.registered_on = datetime.datetime.utcnow()

    def is_authenticated(self):
        """Return True if the user is authenticated."""
        return self.authenticated

    def is_active(self):
        """True, as all users are active."""
        return True

    def is_anonymous(self):
        """False, as anonymous users aren't supported."""
        return False

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<User %s>' % self.email


class RoleBEUser(Base):
    '''Class corresponding to the "roles_user" table which represents the
    many-to-many relationship between "billentry_user" and "roles"'''
    __tablename__ = 'role_beuser'

    billentry_user_id = Column(Integer, ForeignKey('billentry_user.id'), primary_key=True)
    role_id = Column(Integer, ForeignKey('role.id'), primary_key=True)

    # bidirectional attribute/collection of "billentry_user"/"role_beuser"
    beuser = relationship(BillEntryUser,
                          backref=backref('role_beuser'))

    # reference to the "Role" object
    role = relationship("Role")

    def __init__(self, role=None, beuser=None):
        # RoleBEUSer has only 'role' in its __init__ because the
        # relationship goes Role -> RoleBEUser -> BILLEntryUser. NOTE if the
        # 'role' argument is actually a BillEntryUser, Role's relationship to
        # RoleBEUser will cause a stack overflow in SQLAlchemy code
        # (without this check).
        assert isinstance(role, Role)

        self.role = role
        self.beuser = beuser


class Role(Base):
    __tablename__ = 'role'
    id = Column(Integer, primary_key=True)
    name = Column(String(10), unique=True)
    description = Column(String(100))


    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        return '<Role %s>' % self.name

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

