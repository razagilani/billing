from ConfigParser import RawConfigParser

class ValidatedConfigParser(RawConfigParser):
    """A ConfigParser class with built-in validation logic and type conversion.
    """
    
    def __init__(self, vns, **kwargs):
        """Construct a new :class:`.ValidatedConfigParser`.
        
        :param vns: a namespace containing formencode Schemas for each
         config file section. If a schema does not exist for a given section, 
         the section values are read as strings without validation/conversion.
        """
        self._vns = vns
        RawConfigParser.__init__(self, **kwargs)
    
    def read(self, filenames):
        """Calls :meth:`ConfigParser.read` to read the file(s) and then 
        runs the validation conversion. 
        """
        RawConfigParser.read(self, filenames)
        for section in self.sections():
            validator = getattr(self._vns, section, None)
            if not validator: continue
            raw_section_vals = dict(self.items(section))
            for k, v in validator.to_python(raw_section_vals).iteritems():
                self.set(section, k, v)