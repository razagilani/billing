"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
import re
from core.extraction import Applier
from core.extraction.applier import UtilBillApplier
from core.extraction.extraction import LayoutExtractor, Field
from core.model import BoundingBox, Session
from core.model.model import ChargeNameMap
from upgrade_scripts import alembic_upgrade
from core import init_model, initialize, init_config
from util.layout import Corners

log = logging.getLogger(__name__)

    # TODO: add charge_name_map's for other utilities

def upgrade():
    alembic_upgrade('1226d67c4c53')

    init_model()
    s = Session()
    cnm_filename = 'upgrade_scripts/vfuture/charge names map.txt'
    cnm_infile = open(cnm_filename, 'r')
    for line in cnm_infile.readlines():
        (regex, rsi_binding) = re.split(r"\s+\|\s+", line)
        s.add(ChargeNameMap(display_name_regex=regex, rsi_binding=rsi_binding))

    s.commit()

