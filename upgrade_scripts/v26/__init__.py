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

def create_project_manager_role(s):
    s.add(Role('Project Manager',
                        'Role for accessing reports view of billentry app'))

def create_register_templates(s):
    for rate_class in s.query(RateClass).all():
        unit = 'therms' if rate_class.service == 'gas' else 'kWh'
        rate_class.register_templates.append(
            RegisterTemplate.get_total_register_template(unit))

def clean_up_register_names(s):
    register_table = Register.__table__
    names = {
        'REG_THERMS': 'REG_TOTAL',

        'REG_ONPEAK': 'REG_PEAK',
        'REG_ON_PK': 'REG_PEAK',

        'REG_INT_PK': 'REG_INTERMEDIATE',
        'REG_INTPEAK': 'REG_INTERMEDIATE',

        'REG_OFF_PK': 'REG_OFFPEAK',

        # what look like "time-of-use demand" meter readings (in only 3
        # bills, none of them processed) are actually just regular demand
        'REG_ONPEAK_DEMAND': 'REG_DEMAND',
        'REG_DEMAND': 'REG_DEMAND',
        'REG_PEAKKW': 'REG_DEMAND',

        'REG_MAX_DEMAND': 'REG_DEMAND',
        'DEMAND_TOTAL': 'REG_DEMAND',

        # bills with blank register_binding are all from 2010 and also have
        # blank "quantity_formula" so charges could not be recalculated anyway
        '': 'REG_TOTAL'
    }
    for old_name, new_name in names.iteritems():
        statement = register_table.update().values(
            register_binding=new_name).where(
            register_table.c.register_binding == old_name)
        s.execute(statement)

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
    assert len(sorted_tables) == 22

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

    # "stamp" the database with the current revision as described here:
    # http://alembic.readthedocs.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
    alembic_cfg = Config(path.join(ROOT_PATH, "alembic.ini"))
    stamp(alembic_cfg, 'head')

    # just to check that it worked
    init_model()

def upgrade():
    log.info('Beginning upgrade to version 26')

    # the OLD database URL must be used in order to upgrade the old  database
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

    log.info('Upgrading schema to revision %s' % REVISION)
    alembic_upgrade(REVISION, config=old_db_config)

    init_model(uri=old_uri, schema_revision=REVISION)

    log.info('Migrating to PostgreSQL')
    migrate_to_postgres(old_db_config, old_uri, new_uri)

    # init model with Postgres just to check that it worked correctly
    init_model(new_uri)
    s = Session()
    clean_up_register_names(s)

    # it is necessary to commit and start a new transaction between changing
    # the data under the old schema and upgrading to the new
    # schema--otherwise MySQL will wait forever. i think this is because the
    # schema-change commands are not part of the transaction, and MySQL wants
    # to wait until all transactions on relevant tables are finished before
    # changing those tables.
    s.commit()

    log.info('upgrading to 100f25ab057f')
    alembic_upgrade('100f25ab057f')

    init_model(schema_revision='100f25ab057f')
    create_project_manager_role(s)
    create_register_templates(s)
    rename_suppliers(s)
    match_supplierswith_altitude_suppliers(s)
    import_altitude_suppliers(s)
    s.commit()

def rename_suppliers(s):
    supplier1 = s.query(Supplier).filter_by(id=2).first()
    assert supplier1.name == 'washington gas'
    supplier1.name = 'WGL'
    supplier2 = s.query(Supplier).filter_by(id=6).first()
    assert supplier2.name == 'dominion'
    supplier2.name = 'Dominion Energy Solutions'

def match_supplierswith_altitude_suppliers(s):
    supplier = s.query(Supplier).filter_by(id=2).first()
    altitude_supplier = AltitudeSupplier(supplier, '2ac56bff-fb88-4ac8-8b7f-f97b903750f4')
    s.add(altitude_supplier)
    supplier = s.query(Supplier).filter_by(id=14).first()
    altitude_supplier = AltitudeSupplier(supplier, 'e2830d1f-a59f-49d5-b445-35ccc9ddf036')
    s.add(altitude_supplier)
    supplier = s.query(Supplier).filter_by(id=9).first()
    altitude_supplier = AltitudeSupplier(supplier, '91f09f4a-7d11-41c9-a368-aa586d5d53eb')
    s.add(altitude_supplier)

def import_altitude_suppliers(s):
    with open('upgrade_scripts/v26/utilities.csv', 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        existing_guids = ['2ac56bff-fb88-4ac8-8b7f-f97b903750f4',
            'e2830d1f-a59f-49d5-b445-35ccc9ddf036',
            '91f09f4a-7d11-41c9-a368-aa586d5d53eb']
        for row in reader:
            if row[2] == '4' and row[1] not in existing_guids:
                supplier = Supplier(row[0])
                s.add(supplier)
                altitude_supplier = AltitudeSupplier(supplier, row[1])
                s.add(altitude_supplier)




