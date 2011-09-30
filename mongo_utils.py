import datetime
from datetime import date, time, datetime
from decimal import Decimal
from lxml.etree import _ElementStringResult
from billing.mutable_named_tuple import MutableNamedTuple

def python_convert(x):
    '''Strip out the MutableNamedTuples since they are no longer 
    needed to preserve document order and provide dot-access notation.'''

    if type(x) in [str, float, int, bool]:
        return x
    if type(x) is Decimal:
        return x
    # lxml gives us string_result types for strings
    if type(x) is _ElementStringResult:
        return str(x)
    if type(x) is unicode:
        return str(x)
    if type(x) is time:
        return x
    if type(x) is date:
        return x
    if type(x) is dict or type(x) is MutableNamedTuple:
        return dict([(item[0], python_convert(item[1])) for item in \
            x.iteritems() if item[1] is not None])
    if type(x) is list:
        return map(python_convert, x)

    raise ValueError("type(%s) is %s: did not convert" % (x, type(x)))

def bson_convert(x):
    '''Returns x converted into a type suitable for Mongo.'''
    # TODO:  copy all or convert all in place?  Or, don't care and just keep
    # doing both scalars are converted in place, dicts are copied.

    if type(x) in [str, float, int, bool, datetime, unicode]:
        return x
    if type(x) is Decimal:
        return float(x)
    if type(x) is time:
        return str(x)
    if type(x) is date:
        return datetime(x.year, x.month, x.day)
    if type(x) is dict or type(x) is MutableNamedTuple:
        #TODO: don't copy dict
        return dict([(item[0], bson_convert(item[1])) for item in x.iteritems()
                if item[1] is not None])
    if type(x) is list:
        return map(bson_convert, x)

    raise ValueError("type(%s) is %s: can't convert that into bson" \
            % (x, type(x)))

