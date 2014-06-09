from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String, Boolean, DateTime
from billing.processing.state import Base
from processing.state import Session
from billing.exc import DatabaseError

class EnergyCompany(Base):
    __tablename__ = 'energy_company'

    id = Column(Integer, primary_key=True)
    discriminator = Column(String(50))

    name = Column(Integer)
    address_id = Column(Integer)

    __mapper_args__ = {'polymorphic_on': discriminator}


class EnergySupplier(EnergyCompany):
    __mapper_args__ = {'polymorphic_identity': 'energy_supplier'}


class SupplierRate(Base):
    __tablename__ = 'supplier_rate'

    id = Column(Integer)
    energy_company_id = Column(Integer, ForeignKey('energy_compay.id'))
    discriminator = Column(String(50))
    active = Column(Boolean)

    __mapper_args__ = {'polymorphic_on': discriminator}

    relationship('EnergyCompany', backref='supplier_rates')

    def __init__(self, session, energy_company, active=True):
        if session.query(self.__class__).first():
            raise DatabaseError("Feed %s already exists" %
                                self.__class__.__name__)
        self.energy_company = energy_company
        self.active = active

    def calculate(self, use_period):
        raise NotImplementedError


class SupplierRateData(Base):
    __tablename__ = 'supplier_rate_data'

    id = Column(Integer)
    supplier_rate_id = Column(Integer, ForeignKey('supplier_rate.id'))
    time = Column(DateTime)
    key = Column(String(50))
    value = Column(String(50))


