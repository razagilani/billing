from ConfigParser import RawConfigParser
from formencode.api import Invalid
from formencode.schema import Schema
from inspect import isclass


class ValidatedConfigParser(RawConfigParser):
    """A ConfigParser class with built-in validation logic and type conversion.
    """
    
    def __init__(self, config_file_schema, **kwargs):
        """Construct a new :class:`.ValidatedConfigParser`.
        
        :param config_file_schema: A namespace containing formencode Schemas for each
         config file section. If a schema does not exist for a given section, 
         the section values are read as strings without validation/conversion.
        """
        self._vns = config_file_schema
        RawConfigParser.__init__(self, **kwargs)

    def schema_dict(self):
        validation_schemas = {}
        for var in dir(self._vns):
            attribute = getattr(self._vns, var, None)
            if isclass(attribute) and issubclass(attribute, Schema) and \
                var != 'Schema':
                validation_schemas[var] = attribute
        return validation_schemas

    def _validate(self):
        """Runs formencode validators on each configuration section."""

        schemas = self.schema_dict()
        actual = set(self.sections())
        expected = set(schemas.keys())
        if actual != expected:
            symmetric_difference = actual.symmetric_difference(expected)
            diff = ', '.join(symmetric_difference)
            raise Invalid("Configuration sections mismatch: %s" % diff,
                          symmetric_difference, None)

        for section in self.sections():
            validator = schemas[section]
            if not validator: continue
            raw_section_vals = dict(self.items(section))
            try:
                validated = validator.to_python(raw_section_vals)
            except Invalid as e:
                raise Invalid("%s.%s" % (section, e.msg), e.value, e.state)
            for k, v in validated.iteritems():
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
