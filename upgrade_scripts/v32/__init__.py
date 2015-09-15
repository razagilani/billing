"""Upgrade script for version 32.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import re
from sqlalchemy.orm import joinedload
from core import init_model
from core.extraction.applier import UtilBillApplier
from core.extraction.extraction import LayoutExtractor, Field
from core.model import Session, UtilBill, BoundingBox, Supplier
from reebill.reebill_model import ReeBill
from upgrade_scripts import alembic_upgrade, log
from util.layout import Corners

# TODO replace with "prod" when ready to deploy
ENVIRONMENT_NAME = 'dev'

def upgrade():
    alembic_upgrade('482dddf4fe5d')

    init_model()
    s = Session()

    # TODO: still doesn't create the right aliases--either hard-code them or
    # just do it manually
    from brokerage.quote_parsers import CLASSES_FOR_SUPPLIERS
    for supplier_id in CLASSES_FOR_SUPPLIERS:
        supplier = s.query(Supplier).filter_by(id=supplier_id).one()
        email_address = 'matrix-%s@billing-%s.nextility.net' % (
            re.sub('\W+', '', supplier.name.lower()), ENVIRONMENT_NAME)
        supplier.matrix_email_recipient = email_address
    s.commit()
