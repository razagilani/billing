  
__all__ = ['util', 'processing', 'init_logging', 'init_config', 'init_model',
           'initialize', 'config']

log = None
config = None

def init_logging(path='settings.cfg'):
    """Initializes logging"""
    import logging, logging.config
    global log
    
    logging.config.fileConfig(path)
    log = logging.getLogger(__name__)
    log.debug('Initialized logging')
    
def init_config(path='settings.cfg'):
    """Sets `billing.config` to an instance of 
    :class:`billing.lib.config.ValidatedConfigParser`.
    
    :param path: The configuration file path; default `settings.cfg`.
    """
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
    
def init_model():
    """Initializes the data model
    """
    from billing.processing.state import Session, Base
    from sqlalchemy import create_engine
    engine = create_engine(config.get('statedb', 'uri'))
    Session.configure(bind=engine)
    Base.metadata.bind = engine

def initialize():
    init_logging()
    init_config()
    init_model()

