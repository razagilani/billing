import sys
import os.path as path

__version__ = '21'

__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config', 'update_path']

config = None


def init_config(filename='settings.cfg', fp=None):
    """Sets `billing.config` to an instance of 
    :class:`billing.lib.config.ValidatedConfigParser`.
    
    :param filename: The configuration file path; default `settings.cfg`.
    :param fp: A configuration file pointer to be used in place of filename
    """
    from billing.data.validation import configuration as vns
    from billing.lib.config import ValidatedConfigParser
    from os.path import dirname, realpath
    import logging

    log = logging.getLogger(__name__)
    
    global config
    config = ValidatedConfigParser(vns)
    if fp:
        log.debug('Reading configuration fp')
        config.readfp(fp)
    else:
        log.debug('Reading configuration file %s' % filename)
        config.read(filename)
    if not config.has_section('main'):
        config.add_section('main')
    config.set('main', 'appdir', dirname(realpath(__file__)))
    log.debug('Initialized configuration')


def init_logging(path='settings.cfg'):
    """Initializes logging"""
    import logging, logging.config
    logging.config.fileConfig(path)
    log = logging.getLogger(__name__)
    log.debug('Initialized logging')


def init_model(uri=None, schema_revision=None):
    """Initializes the sqlalchemy data model. 
    """
    from billing.processing.state import Session, Base, check_schema_revision
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