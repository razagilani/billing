"""Upgrade script for version 26.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import csv
import logging
from alembic.command import stamp
from alembic.config import Config
from os import path
from billentry.billentry_model import Role
from core.altitude import AltitudeSupplier
from core.model.model import RegisterTemplate
from sqlalchemy import create_engine

from upgrade_scripts import alembic_upgrade
from core import init_model, ROOT_PATH
from core.model import Session, Base, RateClass, Register, Supplier

log = logging.getLogger(__name__)

REVISION = '58383ed620d3'

def migrate_to_postgres(old_db_config, old_uri, new_uri):
    """Create all tables in the Postgres database defined by "uri" in the
    config file and copy data from MySQL (the database defined by "old_uri").
    """
    # import all modules that contain model classes, to make Base recognize
    # their tables
    from core import import_all_model_modules
    import_all_model_modules()

    mysql_engine = create_engine(old_uri)
    pg_engine = create_engine(new_uri)
    sorted_tables = Base.metadata.sorted_tables
    assert len(sorted_tables) == 29 # alembic_version not included

    log.info('Dropping/creating PostgreSQL tables')
    for table in reversed(sorted_tables):
        pg_engine.execute('drop table if exists %s' % table.name)
    Base.metadata.bind = pg_engine
    Base.metadata.create_all()

    for table in sorted_tables:
        log.info('Copying table %s' % table.name)
        data = mysql_engine.execute(table.select()).fetchall()

        count_query = 'select count(*) from %s' % table.name

        # prevents "IntegrityError: (IntegrityError) null value in
        # column "supplier_id" violates not-null constraint"
        if data == []:
            assert mysql_engine.execute(count_query).fetchall()[0][0] == 0
            continue

        # MySQL's enum type has some problems with case, which can't be fixed
        # by "set unit = 'kWD' where unit = 'KWD'" ("matched N rows,
        # changed 0").
        # all rows in a given table the same keys, so skip this table if the
        # first row doesn't have "unit"
        if 'unit' in data[0]:
            # data is a list of RowProxy objects, which are immutable and
            # must be converted to dicts in order to be modified. (yes, 2
            # copies of the whole table in memory at once)
            data = [dict(row.items()) for row in data]
            for row in data:
                if row['unit'] == 'KWD':
                    row['unit'] = 'kWD'

        pg_engine.execute(table.insert(), data)

        # verify row count
        pg_count = pg_engine.execute(count_query).fetchone()[0]
        assert mysql_engine.execute(count_query).fetchone()[0] == pg_count

        # manually update value of primary key sequence: prevents constraint
        # violation errors when new rows are inserted after the migration
        pk_col_names = table.primary_key.columns.keys()
        pk_cols = table.primary_key.columns.values()
        if any(len(c.foreign_keys) > 0 for c in pk_cols):
            # some tables (especially many-many mapping tables) have foreign
            # keys as primary keys; these don't have their own sequences
            log.info('Assuming table %s has no primary key sequence for %s' % (
                table.name, pk_col_names))
            continue
        sequence_name = '_'.join([table.name, pk_col_names[0], 'seq'])
        print pg_engine.execute("select setval('%s', %s)" % (sequence_name, pg_count)).fetchall()
        #print pg_engine.execute("select lastval('%s')" % sequence_name)

    # "stamp" the new database with the current revision as described here:
    # http://alembic.readthedocs.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
    alembic_cfg = Config(path.join(ROOT_PATH, "alembic.ini"))
    alembic_cfg.set_section_option('alembic', 'sqlalchemy.url', new_uri)
    stamp(alembic_cfg, 'head')

    # just to check that it worked
    init_model(uri=new_uri)
