import sys
import os.path as path
from os.path import dirname, realpath

__version__ = '21'

__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config']

config = None


def init_config(filepath='settings.cfg', fp=None):
    """Sets `billing.config` to an instance of 
    :class:`billing.lib.config.ValidatedConfigParser`.
    
    :param filepath: The configuration file path; default `settings.cfg`.
    :param fp: A configuration file pointer to be used in place of filename
    """
    from billing.data.validation import configuration as vns
    from billing.lib.config import ValidatedConfigParser
    import logging

    log = logging.getLogger(__name__)
    
    global config
    config = ValidatedConfigParser(vns)
    if fp:
        log.debug('Reading configuration fp')
        config.readfp(fp)
    else:
        log.debug('Reading configuration file %s' % filepath)
        absolute_path = path.join(dirname(realpath(__file__)), filepath)
        config.read(absolute_path)
    
    if not config.has_section('main'):
        config.add_section('main')
    config.set('main', 'appdir', dirname(realpath(__file__)))
    log.debug('Initialized configuration')


def init_logging(filepath='settings.cfg'):
    """Initializes logging"""
    import logging, logging.config
    absolute_path = path.join(dirname(realpath(__file__)), filepath)
    logging.config.fileConfig(absolute_path)
    log = logging.getLogger(__name__)
    log.debug('Initialized logging')


def init_model(uri=None, schema_revision=None):
    """Initializes the sqlalchemy data model. 
    """
    from billing.core.model import Session, Base, check_schema_revision
    from sqlalchemy import create_engine
    import logging
    log = logging.getLogger(__name__)


    uri = uri if uri else config.get('statedb', 'uri')
    log.debug('Intializing sqlalchemy model with uri %s' % uri)
    Session.rollback()
    Session.remove()
    engine = create_engine(uri)
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    check_schema_revision(schema_revision=schema_revision)
    log.debug('Initialized sqlalchemy model')

def initialize():
    init_logging()
    init_config()
    init_model()