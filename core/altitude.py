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
from sqlalchemy.orm import relationship

from billing.core.model import Base, Session, Utility, UtilityAccount


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

# conversion functions: look up billing entities via Altitude GUIDs
def _altitude_to_billing(altitude_class, billing_class):
    return lambda guid: Session().query(billing_class).join(
        altitude_class).filter(altitude_class.guid==guid).one()
get_utility_from_guid = _altitude_to_billing(AltitudeUtility, Utility)
get_account_from_guid = _altitude_to_billing(AltitudeAccount, UtilityAccount)

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
