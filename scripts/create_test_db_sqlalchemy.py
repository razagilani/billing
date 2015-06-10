"""Run this script to create a "test" database based on the SQLAlchemy
model classes. This does not use a copy of the dev database, like the old
create_test_db.py.
"""
from os import chdir
from os.path import join
from alembic import command
from argparse import ArgumentParser

from alembic.config import Config
from sqlalchemy import create_engine

from test import init_test_config
from core import init_model, ROOT_PATH, import_all_model_modules
from core.model import Base, Session

import_all_model_modules()

if __name__ == '__main__':
    init_test_config()
    from core import config

    parser = ArgumentParser(
        description='Create a "test" database based on theSQLAlchemy model '
                    'classes.')
    parser.add_argument('--echo', action='store_true',
                        help='Print SQL statements used to create the database')
    args = parser.parse_args()

    # note that core.init_model can't be called before
    # the alembic_version table exists
    # because it requires the alembic_version table
    # to already exist in the database
    uri = config.get('db', 'uri')
    engine = create_engine(uri, echo=args.echo)

    engine.execute('drop database if not exists test')
    engine.execute('create database test')
    engine.execute('create extension if not exists hstore')

    Base.metadata.bind = engine

    Base.metadata.drop_all()
    Base.metadata.create_all()

    # "stamp" with current alembic version
    # TODO: why doesn't this do anything?
    chdir(ROOT_PATH)
    alembic_cfg = Config('alembic.ini')
    alembic_cfg.set_main_option('sqlalchemy.url', uri)
    command.stamp(alembic_cfg, 'head')

    # check that it worked
    init_model()
