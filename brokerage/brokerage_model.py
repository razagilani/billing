"""SQLAlchemy model classes related to the brokerage/Power & Gas business.
"""
from sqlalchemy import Column, Integer, ForeignKey, inspect
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

    POLYMORPHIC_IDENTITY = 'beutilbill'


    @classmethod
    def create_from_utilbill(cls, utilbill):
        """Return a new BEUtilBill, identical to 'utilbill' except for its
        class.
        """
        print type(UtilBill)
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
