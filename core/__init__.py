import os.path as path
from os.path import dirname, realpath
from pint import UnitRegistry

import configuration as config_file_schema


__version__ = '23'

__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config', 'import_all_model_modules', 'ROOT_PATH']

ROOT_PATH = dirname(dirname(realpath(__file__)))

config = None

def init_config(filepath='settings.cfg', fp=None):
    """Sets `billing.config` to an instance of 
    :class:`billing.lib.config.ValidatedConfigParser`.
    
    :param filepath: The configuration file path; default `settings.cfg`.
    :param fp: A configuration file pointer to be used in place of filename
    """
    from util.validated_config_parser import ValidatedConfigParser
    import logging

    log = logging.getLogger(__name__)
    
    global config
    config = ValidatedConfigParser(config_file_schema)
    if fp:
        log.debug('Reading configuration fp')
        config.readfp(fp)
    else:
        absolute_path = path.join(ROOT_PATH, filepath)
        log.debug('Reading configuration file %s' % absolute_path)
        config.read(absolute_path)
    
    if not config.has_section('main'):
        config.add_section('main')
    config.set('main', 'appdir', dirname(realpath(__file__)))
    log.debug('Initialized configuration')

    # set boto's options for AWS HTTP requests according to the aws_s3
    # section of the config file.
    # it is necessary to override boto's defaults because the default
    # behavior is to repeat every request 6 times with an extremely long
    # timeout and extremely long interval between attempts, making it hard to
    # tell when the server is not responding.
    # this will override ~/.boto and/or /etc/boto.cfg if they exist (though we
    # should not have those files).
    import boto
    if not boto.config.has_section('Boto'):
        boto.config.add_section('Boto')
    for key in ['num_retries', 'max_retry_delay', 'http_socket_timeout']:
        value = config.get('aws_s3', key)
        if value is not None:
            boto.config.set('Boto', key, str(value))


def init_logging(filepath='settings.cfg'):
    """Initializes logging"""
    import logging, logging.config
    absolute_path = path.join(ROOT_PATH, filepath)
    logging.config.fileConfig(absolute_path)
    log = logging.getLogger(__name__)
    log.debug('Initialized logging')


def import_all_model_modules():
    """Import all modules that contain SQLAlchemy model classes. In some
    cases SQLAlchemy requires these classes to be imported so it can be aware
    of them, even if they are not used.
    """
    import core.model
    import core.altitude
    import reebill.reebill_model
    import brokerage.brokerage_model
    import billentry.billentry_model

def init_model(uri=None, schema_revision=None):
    """Initializes the sqlalchemy data model. 
    """
    from core.model import Session, Base, check_schema_revision
    from sqlalchemy import create_engine
    import logging
    log = logging.getLogger(__name__)

    import_all_model_modules()

    uri = uri if uri else config.get('db', 'uri')
    log.debug('Intializing sqlalchemy model with uri %s' % uri)
    Session.rollback()
    Session.remove()
    engine = create_engine(uri, echo=config.get('db', 'echo'),
                           # recreate database connections every hour, to avoid
                           # "MySQL server has gone away" error when they get
                           # closed due to inactivity
                           pool_recycle=3600)
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    check_schema_revision(schema_revision=schema_revision)
    log.debug('Initialized sqlalchemy model')

def initialize():
    init_logging()
    init_config()
    init_model()

ROOT_PATH = dirname(dirname(realpath(__file__)))
