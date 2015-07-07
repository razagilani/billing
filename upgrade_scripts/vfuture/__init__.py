"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.extraction import Applier
from core.extraction.extraction import LayoutExtractor, Field

from upgrade_scripts import alembic_upgrade
from core import init_model, initialize, init_config

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
        origin_y=746.91)
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)-%s" % (date_format, date_format), page_num=1,
        bbminx=411, bbminy=712, bbmaxx=441, bbmaxy=717,
        corner=0, type=Field.DATE,
        applier_key=Applier.START))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s-(%s)" % (date_format, date_format), page_num=1,
        bbminx=411, bbminy=712, bbmaxx=441, bbmaxy=717,
        corner=0, type=Field.DATE,
        applier_key=Applier.END))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % num_format, page_num=2,
        bbminx=225, bbminy=624, bbmaxx=300, bbmaxy=640,
        corner=0, type=Field.FLOAT,
        applier_key=Applier.ENERGY))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % date_format, page_num=2,
        bbminx=280, bbminy=702, bbmaxx=330, bbmaxy=715,
        corner=0, type=Field.DATE,
        applier_key=Applier.NEXT_READ))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(.*)Service address:\s+(.*)$", page_num=1,
        bbminx=411, bbminy=690, bbmaxx=480, bbmaxy=706,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.SERVICE_ADDRESS))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=66, bbminy=61, bbmaxx=203, bbmaxy=91,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.BILLING_ADDRESS))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"Rate Class:\s+(.*)$", page_num=2,
        bbminx=39, bbminy=715, bbmaxx=105, bbmaxy=725,
        corner=0, type=Field.STRING,
        applier_key=Applier.RATE_CLASS))
    washington_gas_layout.fields.append(LayoutExtractor.TableField(
        page_num=2,
        bbminx=99, bbminy=437, bbmaxx=372, bbmaxy=571,
        table_stop_regex=r"total washington gas charges|ways to pay",
        corner=0, type=Field.TABLE_CHARGES,
        applier_key=Applier.CHARGES))
    washington_gas_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1,
        offset_regex="total charges this period",
        bbminx=0, bbminy=0, bbmaxx=170, bbmaxy=10,
        corner=0, type=Field.FLOAT,
        applier_key=Applier.PERIOD_TOTAL))

    pepco_2015_layout = LayoutExtractor(
        name='Layout Extractor for Pepco bills in 2015 id 18541',
        origin_regex="How to contact us",
        origin_x="333",
        origin_y="617.652")
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s) to %s" % (date_format, date_format), page_num=2,
        bbminx=310, bbminy=720, bbmaxx=470, bbmaxy=740,
        corner=0, type=Field.DATE,
        applier_key=Applier.START))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s to (%s)" % (date_format, date_format), page_num=2,
        bbminx=310, bbminy=720, bbmaxx=470, bbmaxy=740,
        corner=0, type=Field.DATE,
        applier_key=Applier.END))
    #non-residential bills have a whole list of subtotals, and the actual
    # total is at the end of this. Hence the very tall bounding box
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)\s*Amount" % num_format, page_num=2,
        bbminx=348, bbminy=328, bbmaxx=361, bbmaxy=623,
        corner=1, type=Field.FLOAT,
        applier_key=Applier.ENERGY))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="your next meter reading is scheduled for (%s)" % date_format,
        page_num=2, type=Field.DATE,
        applier_key=Applier.NEXT_READ))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"Your service address:\s+(.*)$", page_num=1,
        bbminx=45, bbminy=554, bbmaxx=260, bbmaxy=577,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.SERVICE_ADDRESS))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=36, bbminy=61, bbmaxx=206, bbmaxy=95,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.BILLING_ADDRESS))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(.*) - service number", page_num=2,
        bbminx=35, bbminy=671, bbmaxx=280, bbmaxy=681,
        corner=0, type=Field.STRING,
        applier_key=Applier.RATE_CLASS))
    # TODO position of pepco 2015 charges changes with each bill, and spans
    # multiple pages
    pepco_2015_layout.fields.append(LayoutExtractor.TableField(
        page_num=2,
        table_start_regex=r"how we calculate this charge",
        table_stop_regex=r"total electric charges",
        bbminx=35, bbminy=246, bbmaxx=354, bbmaxy=512,
        multipage_table=True, maxpage=3,
        nextpage_top = 710,
        corner=0, type=Field.TABLE_CHARGES,
        applier_key=Applier.CHARGES))
    pepco_2015_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1, maxpage=3,
        offset_regex="total electric charges",
        bbminx=0, bbminy=0, bbmaxx=318, bbmaxy=10,
        corner=0, type=Field.FLOAT,
        applier_key=Applier.PERIOD_TOTAL))

    pepco_old_layout = LayoutExtractor(
        name='Layout Extractor Pepco bills before 2015, blue logo id 2631')
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s) to %s" % (date_format, date_format), page_num=1,
        bbminx=435, bbminy=716, bbmaxx=535, bbmaxy=726,
        corner=0, type=Field.DATE,
        applier_key=Applier.START))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s to (%s)" % (date_format, date_format), page_num=1,
        bbminx=435, bbminy=716, bbmaxx=535, bbmaxy=726,
        corner=0, type=Field.DATE,
        applier_key=Applier.END))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % num_format, page_num=1,
        bbminx=280, bbminy=481, bbmaxx=305, bbmaxy=491,
        corner=0, type=Field.FLOAT,
        applier_key=Applier.ENERGY))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % date_format, page_num=1,
        bbminx=13, bbminy=448, bbmaxx=234, bbmaxy=458,
        corner=0, type=Field.DATE,
        applier_key=Applier.NEXT_READ))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=435, bbminy=694, bbmaxx=555, bbmaxy=704,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.SERVICE_ADDRESS))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=86, bbminy=66, bbmaxx=224, bbmaxy=108,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.BILLING_ADDRESS))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=97, bbminy=480, bbmaxx=144, bbmaxy=490,
        corner=0, type=Field.STRING,
        applier_key=Applier.RATE_CLASS))
    pepco_old_layout.fields.append(LayoutExtractor.TableField(
        page_num=2,
        bbminx=259, bbminy=446, bbmaxx=576, bbmaxy=657,
        table_stop_regex=r"current charges this period",
        corner=0, type=Field.TABLE_CHARGES,
        applier_key=Applier.CHARGES))
    pepco_old_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1,
        offset_regex="current charges this period",
        bbminx=0, bbminy=0, bbmaxx=252, bbmaxy=10,
        corner=0, type=Field.FLOAT,
        applier_key=Applier.PERIOD_TOTAL))


    #TODO determine how to tell if we want gas or electric info
    bge_layout = LayoutExtractor(
        name='Layout Extractor BGE bills id 7657')
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s) - %s" % (date_format, date_format), page_num=2,
        bbminx=25, bbminy=725, bbmaxx=195, bbmaxy=735,
        corner=0, type=Field.DATE,
        applier_key=Applier.START))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"%s - (%s)" % (date_format, date_format), page_num=2,
        bbminx=25, bbminy=725, bbmaxx=195, bbmaxy=735,
        corner=0, type=Field.DATE,
        applier_key=Applier.END))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"(%s)" % date_format, page_num=1,
        bbminx=460, bbminy=672, bbmaxx=586, bbmaxy=682,
        corner=0, type=Field.DATE,
        applier_key=Applier.NEXT_READ))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=370, bbminy=716, bbmaxx=555, bbmaxy=740,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.SERVICE_ADDRESS))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex=r"", page_num=1,
        bbminx=40, bbminy=100, bbmaxx=200, bbmaxy=161,
        corner=0, type=Field.ADDRESS,
        applier_key=Applier.BILLING_ADDRESS))
    bge_layout.fields.append(LayoutExtractor.BoundingBoxField(
        bbregex="(%s)" % num_format, page_num=1,
        offset_regex="total charges this period",
        bbminx=0, bbminy=0, bbmaxx=255, bbmaxy=10,
        corner=0, type=Field.FLOAT,
        applier_key=Applier.PERIOD_TOTAL))

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

