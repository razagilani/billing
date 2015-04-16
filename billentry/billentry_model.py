"""SQLAlchemy model classes used by the Bill Entry application.
"""
import datetime
import bcrypt
from flask.ext.login import UserMixin
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean, \
    inspect
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, backref

from core.model import Base, UtilBill, Session


class BillEntryUser(Base, UserMixin):
    """Placeholder for table for users of the BillEntry application.
    """
    __tablename__ = 'billentry_user'

    _anonymous_user = None

    @classmethod
    def get_anonymous_user(cls):
        """Return the anonymous user, which should only be used when
        authentication is disabled.
        """
        from core import config
        # the anonymous user should never be created when authentication is
        # turned on
        assert config.get('billentry', 'disable_authentication') == True
        if cls._anonymous_user is None:
            cls._anonymous_user = BillEntryUser(email='anonymous@example.com')
            cls._anonymous_user.is_anonymous = lambda: True
        return cls._anonymous_user

    id = Column(Integer, primary_key=True)
    password = Column(String(60), nullable=False)
    email = Column(String(50),unique=True, index=True, nullable=False)
    registered_on = Column('registered_on', DateTime, nullable=False)
    authenticated = Column(Boolean, default=False)

    # association proxy of "role_beuser" collection
    # to "role" attribute
    roles = association_proxy('billentry_role_user', 'billentry_role')

    def __init__(self, email='', password=''):
        self.email = email
        self.password = self.get_hashed_password(password)
        self.registered_on = datetime.datetime.utcnow()

    def get_hashed_password(self, plain_text_password):
        # Hash a password for the first time
        #   (Using bcrypt, the salt is saved into the hash itself)
        return bcrypt.hashpw(plain_text_password, bcrypt.gensalt(10))

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
    __tablename__ = 'billentry_role_user'

    billentry_user_id = Column(Integer, ForeignKey('billentry_user.id'), primary_key=True)
    billentry_role_id = Column(Integer, ForeignKey('billentry_role.id'), primary_key=True)

    # bidirectional attribute/collection of "billentry_user"/"role_beuser"
    beuser = relationship(BillEntryUser,
                          backref=backref('billentry_role_user'))

    # reference to the "Role" object
    billentry_role = relationship("Role")

    def __init__(self, billentry_role=None, beuser=None):

        # RoleBEUSer has only 'role' in its __init__ because the
        # relationship goes Role -> RoleBEUser -> BILLEntryUser. NOTE if the
        # 'role' argument is actually a BillEntryUser, Role's relationship to
        # RoleBEUser will cause a stack overflow in SQLAlchemy code
        # (without this check).

        assert isinstance(billentry_role, (Role, type(None)))

        self.billentry_role = billentry_role
        self.beuser = beuser


class Role(Base):
    __tablename__ = 'billentry_role'
    id = Column(Integer, primary_key=True)
    name = Column(String(20), unique=True)
    description = Column(String(100))


    def __init__(self, name='', description=''):
        self.name = name
        self.description = description

    def __repr__(self):
        return '<Role %s>' % self.name

class BEUtilBill(UtilBill):
    """UtilBill subclass that tracks when a bill became "entered" in the
    Bill Entry application and by whom.
    """
    POLYMORPHIC_IDENTITY = 'beutilbill'

    __mapper_args__ = {
        # single-table inheritance
        'polymorphic_identity': POLYMORPHIC_IDENTITY,
        'polymorphic_on': 'discriminator',
    }

    billentry_date = Column(DateTime)
    billentry_user_id = Column(Integer, ForeignKey('billentry_user.id'))
    billentry_user = relationship(BillEntryUser)
    flagged = Column(Boolean)

    # TODO remove--no longer necessary
    @classmethod
    def create_from_utilbill(cls, utilbill):
        """Return a new BEUtilBill, identical to 'utilbill' except for its
        class.
        """
        assert type(utilbill) is UtilBill
        assert utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY
        new_beutilbill = BEUtilBill(utilbill.utility_account, utilbill.utility,
                                    utilbill.rate_class)
        # https://stackoverflow.com/questions/2537471/
        # method-of-iterating-over-sqlalchemy-models-defined-columns
        mapper = inspect(utilbill)
        for col_name, value in mapper.attrs.items():
            if col_name in ('discriminator',):
                continue
            # NOTE it should be OK to share the same child objects between
            # 'utilbill' and 'new_beutilbill' because utilbill is going to be
            #  deleted
            utilbill_value = mapper.attrs[col_name].value
            setattr(new_beutilbill, col_name, utilbill_value)
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
        self.billentry_user = None if user.is_anonymous() else user

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
        # consistency check: normally all values must be either None or
        # filled in, but 'billentry_user' will be None when the user is
        # anonymous.
        assert self.billentry_user is None or self.billentry_date is not None

        return self.processed or (self.billentry_date is not None)

    def flag(self):
        """ 'Flag' a utility bill, i.e. mark a bill as difficult to process
        """
        assert not self.is_flagged()
        self.flagged = True

    def un_flag(self):
        """ 'Unflag' a utility bill, i.e. mark the processing difficulty as
        resolved
        """
        assert self.is_flagged()
        self.flagged = False

    def is_flagged(self):
        """Return True if the bill has been flagged. False otherwise"""
        return self.flagged is True

    def editable(self):
        if self.is_entered():
            return False
        return True

