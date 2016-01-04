import logging
from brokerage.brokerage_model import MatrixFormat
from upgrade_scripts import alembic_upgrade
from reebill.reebill_model import ReeBillCustomer, ReeBill
from sqlalchemy import desc
from core.model import Session, Base, Address, AltitudeSession
from core import init_model, init_altitude_db

log = logging.getLogger(__name__)

def upgrade():
    alembic_upgrade('2f0fca54f119')
    init_model(schema_revision='2f0fca54f119')

