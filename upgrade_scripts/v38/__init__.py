import logging
from brokerage.brokerage_model import MatrixFormat
from upgrade_scripts import alembic_upgrade
from reebill.reebill_model import ReeBillCustomer, ReeBill
from sqlalchemy import desc
from core.model import Session, Base, Address
from core import init_model

log = logging.getLogger(__name__)

def upgrade():
    alembic_upgrade('366f5ed78b68')
    s = Session()
    init_model()
    s.commit()
