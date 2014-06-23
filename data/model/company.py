from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String, Boolean, DateTime, Enum
from billing.data.model.orm import Base
from data.model.brokerage import RateClass
from data.model.orm import Session


class Company(Base):
    __tablename__ = 'company'

    id = Column(Integer, primary_key=True)
    address_id = Column(Integer)

    name = Column(Integer)
    discriminator = Column(String(50))
    service = Column(Enum('gas', 'electric', name='supplier_offer_source'))
    address = relationship("Address")

    def __init__(self, name, address, service):
        self.name = name
        self.address = address
        self.service = service

    __mapper_args__ = {'polymorphic_on': discriminator}


class Supplier(Company):
    __mapper_args__ = {'polymorphic_identity': 'supplier'}


class Utility(Company):
    __mapper_args__ = {'polymorphic_identity': 'utility'}

    def __init__(self, name, address, service, rate_classes=[]):
        """Construct a :class:`Utility` instance"""
        for s in rate_classes:
            self.rate_classes.append(RateClass(s))
        super(Utility, self).__init__(name, address, service)

