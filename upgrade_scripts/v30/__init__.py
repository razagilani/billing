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

    s = Session()
    init_model()

    log.info('Updating reebill.utilbill_id')
    # TODO: this sets reebill.utilbill_id to the same value in all rows. not
    # sure what is wrong with it.
    s.execute('''update reebill as r
    set utilbill_id = utilbill_reebill.utilbill_id
    from reebill
    join utilbill_reebill on reebill.id = utilbill_reebill.reebill_id
    join utilbill on utilbill_reebill.utilbill_id = utilbill.id''')

    # just to check that the above update worked
    log.info('Checking reebill.utilbill_id')
    s.query(ReeBill).join(UtilBill).all()

    s.commit()

    # to do later:
    # - set reebill.utilbill_id to not null
    # - drop the utilbill_reebill table
