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

def create_layout_extractors(s):
    date_format = r'[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4}'
    num_format = r'[0-9,\.]+'
    washington_gas_layout = LayoutExtractor(
        name='Layout Extractor for Washington Gas bills with green and '
             'yellow and chart (after 2014) id 15311',
        origin_regex="account number",
        origin_x=411.624,
        origin_y=757.755)
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)-%s" % (date_format, date_format), page_num=1,
        bounding_box=BoundingBox(x0=411, y0=713, x1=441, y1=723),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.START))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s-(%s)" % (date_format, date_format), page_num=1,
        bounding_box=BoundingBox(x0=411, y0=713, x1=441, y1=723),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.END))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % num_format, page_num=2,
        bounding_box=BoundingBox(x0=225, y0=624, x1=300, y1=647),
        corner=Corners.TOP_LEFT, type=Field.FLOAT,
        applier_key=UtilBillApplier.ENERGY))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % date_format, page_num=2,
        bounding_box=BoundingBox(x0=280, y0=713, x1=330, y1=723),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.NEXT_READ))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(.*)Service address:\s+(.*)$", page_num=1,
        bounding_box=BoundingBox(x0=411, y0=690, x1=480, y1=711),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.SERVICE_ADDRESS))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=66, y0=51, x1=203, y1=103),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.BILLING_ADDRESS))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"Rate Class:\s+(.*)$", page_num=2,
        bounding_box=BoundingBox(x0=39, y0=725, x1=105, y1=735),
        corner=Corners.TOP_LEFT, type=Field.STRING,
        applier_key=UtilBillApplier.RATE_CLASS))
    washington_gas_layout.fields.append(LayoutExtractor.TableField(
        page_num=2,
        bounding_box=BoundingBox(x0=99, y0=437, x1=372, y1=571),
        table_stop_regex=r"total washington gas charges|ways to pay",
        corner=Corners.TOP_LEFT, type=Field.TABLE_CHARGES,
        applier_key=UtilBillApplier.CHARGES))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1,
        offset_regex="total charges this period",
        bounding_box=BoundingBox(x0=0, y0=0, x1=170, y1=10),
        corner=Corners.TOP_LEFT, type=Field.FLOAT,
        applier_key=UtilBillApplier.PERIOD_TOTAL))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="Your gas is supplied(?: and distributed)? by\s+(.+?)\.",
        page_num=2, corner=Corners.TOP_LEFT,
        bounding_box=BoundingBox(x0=413, y0=725, x1=595, y1=758),
        type=Field.SUPPLIER, applier_key=UtilBillApplier.SUPPLIER))

    pepco_2015_layout = LayoutExtractor(
        name='Layout Extractor for Pepco bills in 2015 id 18541',
        origin_regex="How to contact us",
        origin_x="333",
        origin_y="617.652")
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s) to %s" % (date_format, date_format), page_num=2,
        bounding_box=BoundingBox(x0=310, y0=720, x1=470, y1=740),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.START))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s to (%s)" % (date_format, date_format), page_num=2,
        bounding_box=BoundingBox(x0=310, y0=720, x1=470, y1=740),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.END))
    # non-residential bills have a whole list of subtotals, and the actual
    # total is at the end of this. Hence the very tall bounding box
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)\s*Amount" % num_format, page_num=2,
        bounding_box=BoundingBox(x0=348, y0=328, x1=361, y1=623),
        corner=Corners.TOP_RIGHT, type=Field.FLOAT,
        applier_key=UtilBillApplier.ENERGY))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="your next meter reading is scheduled for (%s)" % date_format,
        page_num=2, type=Field.DATE,
        applier_key=UtilBillApplier.NEXT_READ))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"Your service address:\s+(.*)$", page_num=1,
        bounding_box=BoundingBox(x0=45, y0=554, x1=260, y1=577),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.SERVICE_ADDRESS))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=36, y0=61, x1=206, y1=95),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.BILLING_ADDRESS))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(.*) - service number", page_num=2,
        bounding_box=BoundingBox(x0=35, y0=671, x1=280, y1=681),
        corner=Corners.TOP_LEFT, type=Field.STRING,
        applier_key=UtilBillApplier.RATE_CLASS))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"Your electricity is supplied by (?:the)?(.*?)(?: "
                r"administered by pepco|[.-])",
        page_num=2, maxpage=4,
        type=Field.SUPPLIER, applier_key=UtilBillApplier.SUPPLIER))
    # TODO position of pepco 2015 charges changes with each bill, and spans
    # multiple pages
    pepco_2015_layout.fields.append(LayoutExtractor.TableField(
        page_num=2,
        table_start_regex=r"how we calculate this charge",
        table_stop_regex=r"total electric charges",
        bounding_box=BoundingBox(x0=35, y0=246, x1=354, y1=512),
        multipage_table=True, maxpage=3,
        nextpage_top = 710,
        corner=Corners.TOP_LEFT, type=Field.TABLE_CHARGES,
        applier_key=UtilBillApplier.CHARGES))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1, maxpage=3,
        offset_regex="total electric charges",
        bounding_box=BoundingBox(x0=0, y0=-10, x1=318, y1=0),
        corner=Corners.TOP_LEFT, type=Field.FLOAT,
        applier_key=UtilBillApplier.PERIOD_TOTAL))

    pepco_old_layout = LayoutExtractor(
        name='Layout Extractor Pepco bills before 2015, blue logo id 2631')
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s) to %s" % (date_format, date_format), page_num=1,
        bounding_box=BoundingBox(x0=435, y0=716, x1=535, y1=726),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.START))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s to (%s)" % (date_format, date_format), page_num=1,
        bounding_box=BoundingBox(x0=435, y0=716, x1=535, y1=726),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.END))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % num_format, page_num=1,
        bounding_box=BoundingBox(x0=280, y0=481, x1=305, y1=491),
        corner=Corners.TOP_LEFT, type=Field.FLOAT,
        applier_key=UtilBillApplier.ENERGY))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % date_format, page_num=1,
        bounding_box=BoundingBox(x0=13, y0=448, x1=234, y1=458),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.NEXT_READ))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=435, y0=694, x1=555, y1=704),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.SERVICE_ADDRESS))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=86, y0=66, x1=224, y1=108),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.BILLING_ADDRESS))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=97, y0=480, x1=144, y1=490),
        corner=Corners.TOP_LEFT, type=Field.STRING,
        applier_key=UtilBillApplier.RATE_CLASS))
    pepco_old_layout.fields.append(LayoutExtractor.TableField(
        page_num=2,
        bounding_box=BoundingBox(x0=259, y0=446, x1=576, y1=657),
        table_stop_regex=r"current charges this period",
        corner=Corners.TOP_LEFT, type=Field.TABLE_CHARGES,
        applier_key=UtilBillApplier.CHARGES))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1,
        offset_regex="current charges this period",
        bounding_box=BoundingBox(x0=0, y0=-10, x1=252, y1=0),
        corner=Corners.TOP_LEFT, type=Field.FLOAT,
        applier_key=UtilBillApplier.PERIOD_TOTAL))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="Services by (.*?) for %s" % date_format, page_num=3,
        type=Field.SUPPLIER, applier_key=UtilBillApplier.SUPPLIER))

    # TODO determine how to tell if we want gas or electric info
    bge_layout = LayoutExtractor(
        name='Layout Extractor BGE bills id 7657')
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s) - %s" % (date_format, date_format), page_num=2,
        offset_regex=r"billing period:",
        bounding_box=BoundingBox(x0=0, y0=-10, x1=175, y1=0),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.START))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s - (%s)" % (date_format, date_format), page_num=2,
        offset_regex=r"billing period:",
        bounding_box=BoundingBox(x0=0, y0=-10, x1=175, y1=0),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.END))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % date_format, page_num=1,
        bounding_box=BoundingBox(x0=460, y0=672, x1=586, y1=682),
        corner=Corners.TOP_LEFT, type=Field.DATE,
        applier_key=UtilBillApplier.NEXT_READ))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=370, y0=716, x1=555, y1=740),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.SERVICE_ADDRESS))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bounding_box=BoundingBox(x0=40, y0=100, x1=200, y1=161),
        corner=Corners.TOP_LEFT, type=Field.ADDRESS,
        applier_key=UtilBillApplier.BILLING_ADDRESS))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="\$(%s)" % num_format, page_num=1,
        offset_regex="total charges this period|total new charges due",
        bounding_box=BoundingBox(x0=0, y0=-10, x1=255, y1=0),
        corner=Corners.TOP_LEFT, type=Field.FLOAT,
        applier_key=UtilBillApplier.PERIOD_TOTAL))

    s.add_all([washington_gas_layout, pepco_2015_layout, pepco_old_layout,
               bge_layout])

def upgrade():
    alembic_upgrade('4d54d21b2c7a')

    initialize()
    from core.model import Base, Session
    print '\n'.join(sorted(t for t in Base.metadata.tables))

    s = Session()
    create_layout_extractors(s)
    s.commit()

