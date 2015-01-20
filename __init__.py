import os.path as path
from os.path import dirname, realpath
from pint import UnitRegistry

import configuration as config_file_schema


__version__ = '23'

__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config', 'ureg']

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
        absolute_path = path.join(dirname(realpath(__file__)), filepath)
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


    uri = uri if uri else config.get('db', 'uri')
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

# pint unitregistry variable used for unit conversion
ureg = UnitRegistry()
ureg.define('thms = 1 * therm = therms')
ureg.define('kilowatthour = 0.0341214163313 * therm = kwh')
ureg.define('centumcubicfoot = 1 * therm = ccf = therms')
ureg.define('kilowattdaily = 0 * therm = kwd')