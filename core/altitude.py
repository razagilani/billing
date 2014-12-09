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
all almost identical.
'''
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from billing.core.model import Base, Session, Utility, UtilityAccount


class AltitudeGUID(String):
    LENGTH = 36
    REGEX = '[0-9A-F\\-]{%d}' % LENGTH
    def __init__(self):
        super(AltitudeGUID, self).__init__(length=self.LENGTH)

class AltitudeUtility(Base):
    '''Holds foreign keys from Utility to Altitude utilities.'''
    __tablename__ = 'altitude_utility'

    id = Column('id', Integer(), primary_key=True, nullable=False)
    utility_id = Column('utility_id', Integer(), ForeignKey('company.id'),
                        nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)
    utility = relationship('Utility')

    def __init__(self, utility, guid):
        self.utility = utility
        self.guid = guid

class AltitudeSupplier(Base):
    '''Holds foreign keys from Supplier to Altitude suppliers.'''
    __tablename__ = 'altitude_supplier'

    id = Column('id', Integer(), primary_key=True, nullable=False)
    utility_id = Column('supplier', Integer(), ForeignKey('company.id'),
                        nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)
    supplier = relationship('Supplier')

    def __init__(self, supplier, guid):
        self.supplier = supplier
        self.guid = guid

class AltitudeAccount(Base):
    '''Holds foreign keys from UtilityAccount to Altitude "accounts" (not to
    be confused with ReeBillCustomers or their "Nexitility account numbers").
    '''
    __tablename__ = 'altitude_account'

    id = Column('id', Integer(), primary_key=True, nullable=False)
    utility_account_id = Column('utility_account_id', Integer(),
                        ForeignKey('utility_account.id'), nullable=False)
    guid = Column('guid', AltitudeGUID, nullable=False)
    utility_account = relationship('UtilityAccount')

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
    for guid in guids:
        try:
            altitude_account = s.query(AltitudeAccount).filter_by(
                guid=guid).one()
        except NoResultFound:
            # if this AltitudeAccount does not exist, create it and associate
            # it with 'utility_account
            s.add(AltitudeAccount(utility_account, guid))
        else:
            # if this GUID does exist, and is associated with another
            # utility account, change it.
            # TODO: find out if this is the desired behavior. alternatives
            # could include: raise an exception if it's not the same utility
            # account as before, because it shouldn't change, or ignore the
            # new value and keep the old one
            altitude_account.utility_account = utility_account
