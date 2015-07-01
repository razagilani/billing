import os
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from core import import_all_model_modules, ROOT_PATH
from core.model import Session, Base


def init_test_config():
    from core import init_config
    from os.path import realpath, join, dirname
    init_config(filepath=join(dirname(realpath(__file__)), 'tstsettings.cfg'))

__all__ = ['BillMailerTest', 'ReebillFileHandlerTest', 'ProcessTest',
           'ReebillProcessingTest', 'BillUploadTest', 'ChargeUnitTests',
           'RateStructureDAOTest', 'UtilBillTest', 'UtilbillLoaderTest',
           'UtilbillProcessingTest', 'ExporterTest', 'FetchTest',
           'JournalTest', 'ReebillTest', 'StateDBTest', 'DateUtilsTest',
           'HolidaysTest', 'MonthmathTest']


def create_tables():
    """Drop and (re-)create tables in the test database according to the
    SQLAlchemy schema.

    Call this after init_test_config() and before init_model(). Call this
    only once before running all tests; it doesn't need to be re-run before
    each test.
    """
    # there must be no open transactions in order to drop tables
    Session.remove()

    from core import config
    uri = config.get('db', 'uri')
    engine = create_engine(uri, echo=config.get('db', 'echo'))

    # blank database has hstore disabled by default; enable it
    engine.execute('create extension if not exists hstore')

    import_all_model_modules()
    Base.metadata.bind = engine
    Base.metadata.reflect()
    Base.metadata.drop_all()
    Base.metadata.create_all(checkfirst=True)

    cur_dir = os.getcwd()
    os.chdir(ROOT_PATH)
    alembic_cfg = Config(os.path.join(ROOT_PATH, 'alembic.ini'))

    # use current database URI (Postgres) instead of alembic upgrade URI (MySQL)
    # TODO: remove this after Postgres is in production because these two
    # will be the same
    alembic_cfg.set_main_option('sqlalchemy.url', config.get('db', 'uri'))

    command.stamp(alembic_cfg, 'head')
    os.chdir(cur_dir)
    Session().commit()


def clear_db():
    """Remove all data from the test database. This should be called before and
    after running any test that inserts data.
    """
    session = Session()
    Session.rollback()
    # because of the call to Base.metadata.reflect() in create_tables(),
    # this now also deletes the "alembic_version" table
    for t in reversed(Base.metadata.sorted_tables):
        session.execute(t.delete())
    session.commit()