from sqlalchemy import Column, Integer, ForeignKey
from billing.core.model import Base, UtilityAccount

class PGAccount(Base):
    '''Table for storing Power & Gas-related data associated with a
    UtilityAccount. May represent the same thing as one of the "accounts",
    "customers" etc. in other databases. The current purpose is only to keep
    track of which UtilityAccounts are "PG related" for exporting PG data.
    '''
    __tablename__ = 'pg_account'
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'),
                                primary_key=True)
