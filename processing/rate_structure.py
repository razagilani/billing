import yaml

class rate_structure(yaml.YAMLObject):
    yaml_tag = u'!rate_structure'
    def __init__(self, name, effective, expires, rates):
        self.name = name
        self.effective = effective
        self.expirse = expires
        self.rates = rates
    def __repr__(self):
        return "%s(name=%r, effective=%r, expires=%r, rates=%r)" % (
            self.__class__.__name__, self.name, self.effective, self.expires, self.rates)


class rate_structure_item(yaml.YAMLObject):
    yaml_tag = u'!rate_structure_item'
    def __init__(self, descriptor, description, quantity=None, rate=None):
        self.name = descriptor
        self.description = description
        self.quantity = quantity
        self.rate = rate
    def __repr__(self):
        return "%s(descriptor=%r, description=%r, quantity=%r, rate=%r)" % (
            self.__class__.__name__, self.descriptor, self.description, self.quantity, self.rate)

