import logging
from brokerage.brokerage_model import MatrixFormat
from upgrade_scripts import alembic_upgrade
from reebill.reebill_model import ReeBillCustomer, ReeBill
from sqlalchemy import desc
from core.model import Session, Base, Address, AltitudeSession
from core import init_model, init_altitude_db

log = logging.getLogger(__name__)

def upgrade():
    alembic_upgrade('366f5ed78b68')

    init_altitude_db()
    a = AltitudeSession()
    url = str(a.bind.url)
    if url.startswith('mssql'):
        a.execute("alter table Rate_Matrix add file_reference varchar(1000)")
    else:
        assert url.startswith('postgresql')
    a.commit()

    s = Session()
    init_model()
    s.commit()
