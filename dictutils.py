#TODO: looks like this makes a by value copy of a dictionary causing references to be lost
# making difficult returning references to data that needs to be modified. (e.g. we return
# a meter dict which might have an identifier changed)
# See set_meter_read_date()
def deep_map(func, x):
    '''Applies the function 'func' througout the data structure x, or just
    applies it to x if x is a scalar. Used for type conversions from Mongo
    types back into the appropriate Python types.'''
    if type(x) is list:
        return [deep_map(func, item) for item in x]
    if type(x) is dict:
        return dict((deep_map(func, key), deep_map(func, value)) for key, value in x.iteritems())
    return func(x)

# dictionary-related utility functions

def dict_merge(*dicts, **kwargs):
    '''Returns a dictionary consisting of the key-value pairs in all the
    dictionaries passed as arguments. These dictionaries must not share any
    keys.'''
    overwrite = kwargs.get('overwrite', False)
    if not overwrite:
        # throw exception if they have the same keys
        for d in dicts:
            for key in d.keys():
                for other in [other for other in dicts if other is not d]:
                    if key in other.keys():
                        raise ValueError('dictionaries share key "%s"' % key)
    result = {}
    for d in dicts:
        result.update(d)
    return result

def subdict(d, keys, ignore_missing=True):
    '''Returns the "sub-dictionary" of 'd' consisting only of items whose keys
    are in 'keys'. If 'ignore_missing' is False, a KeyError will be raised if
    'd' is missing any key in 'keys'; otherwise missing keys are just
    ignored.'''
    return dict((key,d[key]) for key in keys if not ignore_missing or (key in d))
