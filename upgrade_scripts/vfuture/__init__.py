"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.extraction.extraction import TextExtractor, Field, Applier, Extractor, \
    LayoutExtractor, BoundingBox
from core.model import Utility

from upgrade_scripts import alembic_upgrade
from core import init_model, initialize, init_config

log = logging.getLogger(__name__)

    # TODO: add charge_name_map's for other utilities

def upgrade():
    # initialize()
    # from core.model import Base, Session
    # s = Session()
    # s.execute('drop type if exists field_type')
    # Field.__table__.drop(Session.bind, checkfirst=True)
    # Extractor.__table__.drop(Session.bind, checkfirst=True)
    # Base.metadata.drop_all()
    # Base.metadata.create_all()
    alembic_upgrade('30597f9f53b9')

    initialize()
    from core.model import Base, Session
    print '\n'.join(sorted(t for t in Base.metadata.tables))
    s = Session()


    # s.query(Field).delete()
    # s.query(Extractor).delete()
    # hstore won't work unless it's specifically turned on
    s.execute('create extension if not exists hstore')
    s.commit()

