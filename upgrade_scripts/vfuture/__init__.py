"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.extraction import Applier
from core.extraction.applier import UtilBillApplier
from core.extraction.extraction import LayoutExtractor, Field
from core.model import BoundingBox
from upgrade_scripts import alembic_upgrade
from core import init_model, initialize, init_config
from util.layout import Corners

log = logging.getLogger(__name__)

    # TODO: add charge_name_map's for other utilities

def upgrade():
    alembic_upgrade('4d54d21b2c7a')

    initialize()
    from core.model import Base, Session
    print '\n'.join(sorted(t for t in Base.metadata.tables))

    s = Session()
    create_layout_extractors(s)
    s.commit()

