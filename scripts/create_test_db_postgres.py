"""Run this script to create a "test" database based on the SQLAlchemy
model classes. This does NOT use a copy of the model classes.
"""
from argparse import ArgumentParser

from sqlalchemy import create_engine

from test import init_test_config
from core import init_model
from core.model import Base

# make sure all model classes are imported
import core.altitude
import reebill.state
import brokerage.brokerage_model

if __name__ == '__main__':
    init_test_config()
    from core import config

    parser = ArgumentParser()
    parser.add_argument('--echo', action='store_true',
                        help='Print SQL statements used to create the database')
    args = parser.parse_args()

    # note that core.init_model can't be called before
    # the alembic_version table exists
    # because it requires the alembic_version table
    # to already exist in the database
    uri = config.get('db', 'uri')
    engine = create_engine(uri, echo=args.echo)
    Base.metadata.bind = engine

    Base.metadata.drop_all()
    Base.metadata.create_all()

    # check that it worked
    init_model()
