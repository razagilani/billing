"""Upgrade script for version 32.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
from sqlalchemy.orm import joinedload
from core import init_model
from core.extraction.applier import UtilBillApplier
from core.extraction.extraction import LayoutExtractor, Field
from core.model import Session, UtilBill, BoundingBox
from reebill.reebill_model import ReeBill
from upgrade_scripts import alembic_upgrade, log
from util.layout import Corners


def upgrade():
    alembic_upgrade('1226d67c4c53')

    init_model()
    s = Session()
