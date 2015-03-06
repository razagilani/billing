"""SQLAlchemy model classes related to the brokerage/Power & Gas business.
"""
import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Boolean
from sqlalchemy.orm import relationship

from core.model import Base, UtilityAccount


class BrokerageAccount(Base):
    '''Table for storing brokerage-related data associated with a
    UtilityAccount. May represent the same thing as one of the "accounts",
    "customers" etc. in other databases. The current purpose is only to keep
    track of which UtilityAccounts are "brokerage-related".
    '''
    __tablename__ = 'brokerage_account'
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'),
                                primary_key=True)
    utility_account = relationship(UtilityAccount)

    def __init__(self, utility_account):
        self.utility_account = utility_account
