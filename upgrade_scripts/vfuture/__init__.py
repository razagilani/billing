"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.extraction import TextExtractor, Field, Applier

from upgrade_scripts import alembic_upgrade
from core import init_model, initialize

log = logging.getLogger(__name__)

def create_extractors(s):
    date_format = r'[A-Za-z]+ [0-9]{1,2}, [0-9]{4}'
    start_regex = 'Your electric bill - [A-Za-z]+ [0-9]{4}for the period (%s)' % date_format
    end_regex = 'Your electric bill - [A-Za-z]+ [0-9]{4}for the period %s to (%s)' % (date_format, date_format)
    energy_regex = r'.*([0-9]{4})Your next meter'
    next_meter_read_regex = r'.*Your next meter reading is scheduled for (%s)' % date_format
    e =  TextExtractor(name='pepco extractor')
    e.fields.append(TextExtractor.TextField(regex=start_regex, type=Field.DATE, applier_key=Applier.START))
    e.fields.append(TextExtractor.TextField(regex=end_regex, type=Field.DATE, applier_key=Applier.END))
    e.fields.append(TextExtractor.TextField(regex=energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    e.fields.append(TextExtractor.TextField(regex=next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))

    s.add(e)

def upgrade():
    initialize()
    from core.model import Base, Session
    Base.metadata.create_all()
    print '\n'.join(sorted(t for t in Base.metadata.tables))

    s = Session()
    create_extractors(s)
    s.commit()

