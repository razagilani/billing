'''SQLAlchemy model classes for Altitude integration, along with related
data-access code. These model classes just hold foreign keys. They should not
hold any data other than foreign keys, especially if it is redundant with data
stored elsewhere.

These are separate classes and separate tables because the billing
database tables have a one-to-many relationship with them. They are not in
model.py so that all the Altitude-related code can be together and will not
permeate the codebase.

If there ends up being more than a small number of these classes, some kind of
abstraction should be used to remove the duplicate code because they are
all almost identical (all their code is determined just by a billing table
name).
'''
from sqlalchemy import Column, Integer, String, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound

from core.model import Base, Session, Utility, UtilityAccount, Supplier, UtilBill


class AltitudeGUID(String):
    LENGTH = 36
    REGEX = '[0-9a-f\\-]{%d}' % LENGTH
    def __init__(self):
        super(AltitudeGUID, self).__init__(length=self.LENGTH)

class AltitudeUtility(Base):
    '''Holds foreign keys from Utility to Altitude utilities.'''
    __tablename__ = 'altitude_utility'

    utility_id = Column('utility_id', Integer(), ForeignKey('utility.id'),
                        nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)
    utility = relationship('Utility')

    # compound primary key
    __table_args__ = (
        PrimaryKeyConstraint('utility_id', 'guid'),
        {},
    )

    def __init__(self, utility, guid):
        self.utility = utility
        self.guid = guid

class AltitudeSupplier(Base):
    '''Holds foreign keys from Supplier to Altitude suppliers.'''
    __tablename__ = 'altitude_supplier'

    supplier_id = Column('supplier_id', Integer(), ForeignKey('supplier.id'),
                        nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)
    supplier = relationship('Supplier')

    # compound primary key
    __table_args__ = (
        PrimaryKeyConstraint('supplier_id', 'guid'),
        {},
    )

    def __init__(self, supplier, guid):
        self.supplier = supplier
        self.guid = guid

class AltitudeAccount(Base):
    '''Holds foreign keys from UtilityAccount to Altitude "accounts" (not to
    be confused with ReeBillCustomers or their "Nexitility account numbers").
    '''
    __tablename__ = 'altitude_account'

    utility_account_id = Column('utility_account_id', Integer(),
                        ForeignKey('utility_account.id'), nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)
    utility_account = relationship('UtilityAccount')

    # compound primary key
    __table_args__ = (
        PrimaryKeyConstraint('utility_account_id', 'guid'),
        {},
    )

    def __init__(self, utility_account, guid):
        self.utility_account = utility_account
        self.guid = guid

    def get_altitude_account(self):
        return self.utility_account


class AltitudeBill(Base):
    __tablename__ = 'altitude_bill'

    utilbill_id = Column('utilbill_id', Integer(), ForeignKey('utilbill.id'),
                         nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)

    utilbill = relationship(
        'UtilBill',
        # delete-orphan so AltitudeBills go away when their UitilBill is deleted,
        # instead of preventing UtilBills from being deleted.
        backref=backref('altitude_bills', cascade='all, delete-orphan'))

    def __init__(self, utilbill, guid):
        self.utilbill = utilbill
        self.guid = guid

    # compound primary key
    __table_args__ = (
        PrimaryKeyConstraint('utilbill_id', 'guid'),
        {},
    )

# conversion functions: look up billing entities via Altitude GUIDs
def _altitude_to_billing(altitude_class, billing_class):
    return lambda guid: Session().query(billing_class).join(
        altitude_class).filter(altitude_class.guid==guid).one()
get_utility_from_guid = _altitude_to_billing(AltitudeUtility, Utility)
get_account_from_guid = _altitude_to_billing(AltitudeAccount, UtilityAccount)
get_utilbill_from_guid = _altitude_to_billing(AltitudeBill, UtilBill)


def _billing_to_altitude(billing_class, altitude_class):
    def query_func(billing_obj):
        if billing_obj is None:
            return None
        attr_name = billing_class.__name__.lower() + '_id'
        return Session().query(altitude_class).join(billing_class).filter(
            getattr(altitude_class, attr_name) == billing_obj.id).first()
    return query_func

# TODO try to avoid writing a lot of repeated code like this
def get_guid_for_utility(x):
    result = _billing_to_altitude(Utility, AltitudeUtility)(x)
    return None if result is None else result.guid
def get_guid_for_utilbill(x):
    result = _billing_to_altitude(UtilBill, AltitudeBill)(x)
    return None if result is None else result.guid

def get_one_altitude_account_guid_for_utility_account(utility_account):
    """Return one AltitudeAccount for the given UtilityAccount if there is
    exactly one, or None otherwise.
    """
    s = Session()
    q = s.query(AltitudeAccount).filter_by(utility_account=utility_account)
    if q.count() == 1:
        return q.one().guid
    return None

def update_altitude_account_guids(utility_account, guids):
    '''For each GUID (string) in 'guids', either associate the AltitudeAccount
    identified by the GUID with the given UtilityAccount, or create a new
    AltitudeAccount associated with it.
    '''
    s = Session()
    # there seems to be no good way to do an "upsert" in SQLAlchemy (SQL
    # "merge"--not to be confused with SQLAlchemy session merge). instead,
    # store every AltitudeAccount that should not be added while looking for
    # the ones that should be deleted, then add ones that were not already seen.
    existing_account_guids = set()
    for aa in s.query(AltitudeAccount).filter(
                    AltitudeAccount.utility_account_id == utility_account.id):
        if aa.guid in guids:
            existing_account_guids.add(aa.guid)
        else:
            s.delete(aa)
    s.add_all([AltitudeAccount(utility_account, guid)
               for guid in set(guids) - existing_account_guids])
    s.flush()

def get_or_create_guid_for_utilbill(utilbill, guid_func, session):
    """Find and return a GUID string for the given UtilBill, or if one does
    not exist, generate one using 'guid_func', store a new AltitudeBill with
    the GUID string, and return it.
    """
    altitude_bill = _billing_to_altitude(UtilBill, AltitudeBill)(utilbill)
    if altitude_bill is None:
        altitude_bill =  AltitudeBill(utilbill, str(guid_func()))
        session.add(altitude_bill)

    return altitude_bill.guid

def get_or_create_guid_for_supplier(supplier, guid_func, session):
    """Find and return a GUID string for the given Supplier, or if one does
    not exist, generate one using 'guid_func', store a new AltitudeSupplier with
    the GUID string, and return it.
    """
    if supplier is None:
        return
    altitude_supplier = _billing_to_altitude(Supplier, AltitudeSupplier)(supplier)
    if altitude_supplier is None:
        altitude_supplier = AltitudeSupplier(supplier, str(guid_func()))
        session.add(altitude_supplier)
    return altitude_supplier.guid
