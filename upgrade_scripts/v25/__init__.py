"""Upgrade script for version 25.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import logging
from alembic.command import stamp
from alembic.config import Config
from os import path
from sqlalchemy import create_engine
from billentry.billentry_model import Role

from upgrade_scripts import alembic_upgrade
from core import init_model, root_path
from core.model import Session, Base


log = logging.getLogger(__name__)


def set_discriminator(s):
    s.execute('update utilbill set discriminator = "utilbill"')
    s.execute('update utilbill join utility_account '
              'on utilbill.utility_account_id = utility_account.id '
              'join brokerage_account '
              'on brokerage_account.utility_account_id = utility_account.id '
              'set utilbill.discriminator = "beutilbill"')

def create_admin_role(s):
    admin_role = Role('admin', 'admin role for accessing Admin UI')
    s.add(admin_role)

def migrate_to_postgres(s):
    # import all modules that contain model classes, to make Base recognize
    # their tables
    import core.altitude
    import reebill.state
    import brokerage.brokerage_model
    import billentry.billentry_model

    mysql_engine = create_engine(MYSQL_URI)
    pg_engine = create_engine(PG_URI)
    sorted_tables = Base.metadata.sorted_tables
    assert len(sorted_tables) == 19

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
        assert mysql_engine.execute(count_query).fetchall() \
               == pg_engine.execute(count_query).fetchall()

    alembic_cfg = Config(path.join(root_path, "alembic.ini"))
    stamp(alembic_cfg, '2d65c7c19345')
    init_model()

def upgrade():
    log.info('Beginning upgrade to version 25')

    log.info('Upgrading schema to revision 52a7069819cb')
    alembic_upgrade('52a7069819cb')

    init_model(schema_revision='52a7069819cb')
    s = Session()
    set_discriminator(s)
    create_admin_role(s)
    s.commit()
