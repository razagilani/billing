"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.extraction import Applier, Extractor
from core.extraction.applier import UtilBillApplier
from core.extraction.extraction import LayoutExtractor, Field
from core.model import BoundingBox
from upgrade_scripts import alembic_upgrade
from core import init_model, initialize, init_config
from util.layout import Corners

log = logging.getLogger(__name__)

    # TODO: add charge_name_map's for other utilities

    # TODO: these extractors were already created in the version 30
    # upgrade script, so they should be updated instead
def create_layout_extractors(s):
    # sort extractors by id, based on the v30 upgrade script
    layout_extractors = s.query(LayoutExtractor).order_by(
        Extractor.extractor_id.asc()).all()
    [washington_gas_layout, pepco_2015_layout, pepco_old_layout, bge_layout] \
        = layout_extractors

    washington_gas_layout.representative_bill_id = 24153
    washington_gas_layout.origin_y=757.755
    for f in washington_gas_layout.fields:
        if f.applier_key == UtilBillApplier.START:
            f.bounding_box = BoundingBox(x0=411, y0=713, x1=441, y1=723)
        elif f.applier_key == UtilBillApplier.END:
            f.bounding_box = BoundingBox(x0=411, y0=713, x1=441, y1=723)
        elif f.applier_key == UtilBillApplier.ENERGY:
            f.bounding_box = BoundingBox(x0=225, y0=624, x1=300, y1=647)
        elif f.applier_key == UtilBillApplier.NEXT_READ:
            f.bounding_box = BoundingBox(x0=280, y0=713, x1=330, y1=723)
        elif f.applier_key == UtilBillApplier.SERVICE_ADDRESS:
            f.bounding_box = BoundingBox(x0=411, y0=690, x1=480, y1=711)
        elif f.applier_key == UtilBillApplier.BILLING_ADDRESS:
            f.bounding_box = BoundingBox(x0=66, y0=51, x1=203, y1=103)
        elif f.applier_key == UtilBillApplier.RATE_CLASS:
            f.bounding_box = BoundingBox(x0=39, y0=725, x1=105, y1=735)
        elif f.applier_key == UtilBillApplier.CHARGES:
            f.bounding_box = BoundingBox(x0=99, y0=230, x1=372, y1=620)
            f.table_start_regex=r"balance brought forward"
        elif f.applier_key == UtilBillApplier.TOTAL:
            f.bounding_box = BoundingBox(x0=0, y0=0, x1=170, y1=10)
        elif f.applier_key == UtilBillApplier.SUPPLIER:
            f.bounding_box = BoundingBox(x0=413, y0=725, x1=595, y1=758)

    pepco_2015_layout.representative_bill_id = 18541
    pepco_2015_layout.origin_y=631.872
    for f in pepco_2015_layout.fields:
        if f.applier_key == UtilBillApplier.START:
            f.bounding_box = BoundingBox(x0=310, y0=744, x1=470, y1=756)
        elif f.applier_key == UtilBillApplier.END:
            f.bounding_box = BoundingBox(x0=310, y0=744, x1=470, y1=756)
        elif f.applier_key == UtilBillApplier.ENERGY:
            f.bounding_box = BoundingBox(x0=348, y0=328, x1=361, y1=639)
        elif f.applier_key == UtilBillApplier.NEXT_READ:
            # doesn't use a bounding box
            f.bounding_box = None
            pass
        elif f.applier_key == UtilBillApplier.SERVICE_ADDRESS:
            f.bounding_box = BoundingBox(x0=45, y0=575, x1=260, y1=594)
        elif f.applier_key == UtilBillApplier.BILLING_ADDRESS:
            f.bounding_box = BoundingBox(x0=36, y0=61, x1=206, y1=107)
        elif f.applier_key == UtilBillApplier.RATE_CLASS:
            f.bounding_box = BoundingBox(x0=35, y0=671, x1=280, y1=696)
        elif f.applier_key == UtilBillApplier.CHARGES:
            f.bounding_box = BoundingBox(x0=35, y0=246, x1=354, y1=527)
            f.nextpage_top = 710
        elif f.applier_key == UtilBillApplier.TOTAL:
            f.bounding_box = BoundingBox(x0=0, y0=-10, x1=318, y1=0)
        elif f.applier_key == UtilBillApplier.SUPPLIER:
            # doesn't use a bounding box
            f.bounding_box = None
            pass

    pepco_old_layout.representative_bill_id = 219
    for f in pepco_old_layout.fields:
        if f.applier_key == UtilBillApplier.START:
            f.bounding_box = BoundingBox(x0=435, y0=725, x1=535, y1=739)
        elif f.applier_key == UtilBillApplier.END:
            f.bounding_box = BoundingBox(x0=435, y0=725, x1=535, y1=739)
        elif f.applier_key == UtilBillApplier.ENERGY:
            f.bounding_box = BoundingBox(x0=280, y0=490, x1=315, y1=500)
        elif f.applier_key == UtilBillApplier.NEXT_READ:
            f.bounding_box = BoundingBox(x0=13, y0=456, x1=234, y1=470)
        elif f.applier_key == UtilBillApplier.SERVICE_ADDRESS:
            f.bounding_box = BoundingBox(x0=435, y0=704, x1=555, y1=716)
        elif f.applier_key == UtilBillApplier.BILLING_ADDRESS:
            f.bounding_box = BoundingBox(x0=80, y0=66, x1=231, y1=123)
        elif f.applier_key == UtilBillApplier.RATE_CLASS:
            f.bounding_box = BoundingBox(x0=94, y0=491, x1=144, y1=499)
        elif f.applier_key == UtilBillApplier.CHARGES:
            f.bounding_box = BoundingBox(x0=259, y0=446, x1=576, y1=672)
        elif f.applier_key == UtilBillApplier.TOTAL:
            f.bounding_box = BoundingBox(x0=0, y0=-10, x1=252, y1=0)

    bge_layout.representative_bill_id = 7567
    for f in bge_layout.fields:
        if f.applier_key == UtilBillApplier.START:
            f.bounding_box = BoundingBox(x0=0, y0=-2, x1=175, y1=15)
        if f.applier_key == UtilBillApplier.END:
            f.bounding_box = BoundingBox(x0=0, y0=-2, x1=175, y1=15)
        if f.applier_key == UtilBillApplier.NEXT_READ:
            f.bounding_box = BoundingBox(x0=460, y0=676, x1=586, y1=697)
        if f.applier_key == UtilBillApplier.SERVICE_ADDRESS:
            f.bounding_box = BoundingBox(x0=310, y0=732, x1=555, y1=754)
            f.bbregex = r"(.*)\s+Service\s+Address\s(.*)"
        if f.applier_key == UtilBillApplier.BILLING_ADDRESS:
            f.bounding_box = BoundingBox(x0=40, y0=100, x1=200, y1=161)
        if f.applier_key == UtilBillApplier.TOTAL:
            f.bounding_box = BoundingBox(x0=0, y0=-10, x1=255, y1=0)

def upgrade():
    alembic_upgrade('4d54d21b2c7a')

    initialize()
    from core.model import Base, Session
    print '\n'.join(sorted(t for t in Base.metadata.tables))

    s = Session()
    create_layout_extractors(s)
    s.commit()

