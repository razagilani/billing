from ConfigParser import RawConfigParser
import logging
log = logging.getLogger(__name__)

class ValidatedConfigParser(RawConfigParser):
    """A ConfigParser class with built-in validation logic and type conversion.
    """
    
    def __init__(self, vns, **kwargs):
        """Construct a new :class:`.ValidatedConfigParser`.
        
        :param vns: A namespace containing formencode Schemas for each
         config file section. If a schema does not exist for a given section, 
         the section values are read as strings without validation/conversion.
        """
        self._vns = vns
        RawConfigParser.__init__(self, **kwargs)

    def _validate(self):
        """Runs formencode validators on each configuration section."""
        for section in self.sections():
            validator = getattr(self._vns, section, None)
            if not validator: continue
            raw_section_vals = dict(self.items(section))
            for k, v in validator.to_python(raw_section_vals).iteritems():
                self.set(section, k, v)

    def readfp(self, fp, filename=None):
        """Reads the configuration file using :meth:`ConfigParser.readfp` and
        runs formencode validators on each configuration section.
        """
        RawConfigParser.readfp(self, fp, filename)
        self._validate()

    def read(self, filenames):
        """Reads the configuration file using :meth:`ConfigParser.read` and 
        runs formencode validators on each configuration section. 
        """
        RawConfigParser.read(self, filenames)
        self._validate()