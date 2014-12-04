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
from billing.core.model import Base, Session, Utility

class AltitudeGUID(String):
    def __init__(self):
        super(AltitudeGUID, self).__init__(length=35)

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

def get_utility_from_guid(guid):
    '''Returns the Utility corresponding to the given Altitude GUID.
    '''
    s = Session()
    return s.query(Utility).join(AltitudeUtility).filter_by(guid=guid).one()
