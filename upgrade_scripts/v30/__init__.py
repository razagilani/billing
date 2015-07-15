"""Upgrade script for version 30.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
from sqlalchemy.orm import joinedload
from core import init_model, init_altitude_db
from core.model import Session, UtilBill
from reebill.reebill_model import ReeBill
from upgrade_scripts import alembic_upgrade



def upgrade():
    alembic_upgrade('1eca0edc1fb7')

    init_model()
    s = Session()
    s.execute('''update reebill as r
    set utilbill_id = utilbill.id
    from reebill join utilbill_reebill on r.id = utilbill_reebill.reebill_id
    join utilbill on utilbill_reebill.utilbill_id = utilbill.id''')

    # just to check that the above update worked
    s.query(ReeBill).options(joinedload('utilbill')).all()

    s.commit()
