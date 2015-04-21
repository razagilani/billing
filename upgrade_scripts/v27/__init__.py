"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging

from alembic.config import Config

from sqlalchemy import create_engine

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Register
from upgrade_scripts.v27.postgres import migrate_to_postgres


REVISION = '58383ed620d3'

log = logging.getLogger(__name__)

def upgrade():
    log.info('Beginning upgrade to version 27')

    # the OLD database URL must be used in order to upgrade the old database
    # before copying to the new database. but the URL for general use (and for
    # "stamping" the alembic revision on the new database) be the new one, so
    # it is necessary to overwrite the "sqlalchmy.url" key in the config object
    # after moving the file.
    from core import config
    old_uri = config.get('db', 'old_uri')
    new_uri = config.get('db', 'uri')
    assert old_uri.startswith('mysql://')
    assert new_uri.startswith('postgresql://')
    old_db_config = Config('alembic.ini')
    old_db_config.set_main_option("sqlalchemy.url", old_uri)

    log.info('Cleaning up reading.register_binding values')
    # clean up reading.register_binding before changing the column type.
    # this enables converting reading.register_binding to the same type as
    # register.register_binding to enable comparisons.
    mysql_engine = create_engine(old_uri)
    mysql_engine.execute(
        "update reading set register_binding = 'REG_TOTAL' where "
        "register_binding is null or register_binding in ('None', '')"
        "or register_binding not in %s" % str(
            tuple(Register.REGISTER_BINDINGS)))

    log.info('Upgrading schema to revision %s' % REVISION)
    alembic_upgrade(REVISION, config=old_db_config)

    init_model(uri=old_uri, schema_revision=REVISION)

    log.info('Migrating to PostgreSQL')
    migrate_to_postgres(old_db_config, old_uri, new_uri)
