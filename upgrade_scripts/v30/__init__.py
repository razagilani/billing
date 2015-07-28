"""Upgrade script for version 30.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
from sqlalchemy.orm import joinedload
from core import init_model
from core.model import Session, UtilBill
from reebill.reebill_model import ReeBill
from upgrade_scripts import alembic_upgrade, log

def upgrade():
    alembic_upgrade('686dfe445fd')

    init_model()
    s = Session()

    log.info('Updating reebill.utilbill_id')
    # this must be executed in raw SQL because the utilbill_reebill table
    # object has been deleted
    s.execute('''
    update reebill r
    set utilbill_id = a.utilbill_id
    from
    (select reebill_id, utilbill_id from utilbill_reebill) as a
    where a.reebill_id = r.id''')

    # just to check that the above update worked
    log.info('Checking reebill.utilbill_id')
    s.query(ReeBill).join(UtilBill).all()

    s.commit()

    alembic_upgrade('1953b5abb480')

    # to do later:
    # - drop the utilbill_reebill table
