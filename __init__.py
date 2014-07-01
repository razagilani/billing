<<<<<<< local
  
__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config']
=======
import sys
import os.path as path
>>>>>>> other

<<<<<<< local
log = None
=======
__version__ = '21'

__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config', 'update_path']

>>>>>>> other
config = None

<<<<<<< local
=======

def init_config(filename='settings.cfg', fp=None):
    """Sets `billing.config` to an instance of 
    :class:`billing.lib.config.ValidatedConfigParser`.
    
    :param filename: The configuration file path; default `settings.cfg`.
    :param fp: A configuration file pointer to be used in place of filename
    """
    from billing.data.validation import configuration as vns
    from billing.lib.config import ValidatedConfigParser
    from os.path import dirname
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
    config.set('main', 'appdir', "/".join(dirname(__file__).split("/")[:-1]))
    log.debug('Initialized configuration')


>>>>>>> other
def init_logging(path='settings.cfg'):
    """Initializes logging"""
    import logging, logging.config
<<<<<<< local
    global log
    
=======
>>>>>>> other
    logging.config.fileConfig(path)
    log = logging.getLogger(__name__)
    log.debug('Initialized logging')
<<<<<<< local
    
def init_config(path='settings.cfg'):
    """Sets `billing.config` to an instance of 
    :class:`billing.lib.config.ValidatedConfigParser`.
    
    :param path: The configuration file path; default `settings.cfg`.
=======


def init_model(uri=None):
    """Initializes the sqlalchemy data model. 
>>>>>>> other
    """
<<<<<<< local
    from billing.data.validation import configuration as vns
    from billing.lib.config import ValidatedConfigParser
    from os.path import dirname
    
    global config
    config = ValidatedConfigParser(vns)
    log.debug('Reading configuration file %s' % path)
    config.read(path)
    if not config.has_section('main'):
        config.add_section('main')
    config.set('main', 'appdir', "/".join(dirname(__file__).split("/")[:-1]))
    log.debug('Initialized configuration')
    
def init_model(uri=None):
    """Initializes the data model
    """
    from billing.processing.state import Session, Base
=======
    from billing.processing.state import Session, Base, check_schema_revision
>>>>>>> other
    from sqlalchemy import create_engine
<<<<<<< local
=======
    import logging
    log = logging.getLogger(__name__)

>>>>>>> other
    uri = uri if uri else config.get('statedb', 'uri')
<<<<<<< local
    log.debug('Intializing model with uri %s' % uri)
=======
    log.debug('Intializing sqlalchemy model with uri %s' % uri)
>>>>>>> other
    engine = create_engine(uri)
    Session.configure(bind=engine)
    Base.metadata.bind = engine
<<<<<<< local
    log.debug('Initialized model')
=======
    check_schema_revision()
    log.debug('Initialized sqlalchemy model')
>>>>>>> other

def initialize():
    init_logging()
    init_config()
    init_model()
<<<<<<< local

=======
>>>>>>> other
