import datetime
from datetime import date, time, datetime
from decimal import Decimal
from billing.mutable_named_tuple import MutableNamedTuple
from bson.objectid import ObjectId
from billing.dictutils import deep_map
from billing.dateutils import date_to_datetime, ISO_8601_DATETIME

def python_convert(x):
    '''Strip out the MutableNamedTuples since they are no longer 
    needed to preserve document order and provide dot-access notation.'''

    if type(x) in [type(None), str, float, int, bool]:
        return x
    if type(x) is Decimal:
        return x
    if type(x) is unicode:
    # do not convert unicode strings to ascii when retrieving documents from mongo: https://www.pivotaltracker.com/story/show/28857505
    #    return str(x)
        return x
    if type(x) is time:
        return x
    if type(x) is date:
        return x
    if type(x) is datetime:
        return x
    if type(x) is ObjectId:
        return x
    if type(x) is dict or type(x) is MutableNamedTuple:
        return dict([(item[0], python_convert(item[1])) for item in \
            #x.iteritems() if item[1] is not None])
            x.iteritems()])
    if type(x) is list:
        return map(python_convert, x)

    raise ValueError("type(%s) is %s: did not convert" % (x, type(x)))

def bson_convert(x):
    '''Returns x converted into a type suitable for Mongo.'''
    # TODO:  copy all or convert all in place?  Or, don't care and just keep
    # doing both scalars are converted in place, dicts are copied.

    if type(x) in [type(None), str, float, int, bool, datetime, unicode, ObjectId]:
        return x
    if type(x) is Decimal:
        return float(x)
    if type(x) is time:
        return str(x)
    if type(x) is date:
        return datetime(x.year, x.month, x.day)
    if type(x) is dict or type(x) is MutableNamedTuple:
        #TODO: don't copy dict
        return dict([(item[0], bson_convert(item[1])) for item in x.iteritems()])
                #if item[1] is not None])
    if type(x) is list:
        return map(bson_convert, x)

    raise ValueError("type(%s) is %s: can't convert that into bson" \
            % (x, type(x)))

def format_query(query_dict):
    '''Un-pythonifies the given query dictionary so it can be pasted directly
    into the Mongo shell. (Good for error messages.)'''
    def unicode_to_ascii(x):
        if type(x) is unicode:
            return str(x)
        return x

    class ISODate(object):
        def __init__(self, d):
            if isinstance(d, date):
                d = date_to_datetime(d)
            self.dt = d
        def __repr__(self):
            return 'ISODate("%s")' % self.dt.strftime(ISO_8601_DATETIME)
    def datetime_to_isodate(x):
        if isinstance(x, datetime): # dates don't belong in Mongo queries anyway
            return ISODate(x)
        return x

    class MongoBoolean(object):
        def __init__(self, value):
            self.value = value
        def __repr__(self):
            return 'true' if self.value else 'false'
    def boolean_to_mongoboolean(x):
        if isinstance(x, bool):
            return MongoBoolean(x)
        return x

    #return deep_map(date_to_isodate, deep_map(unicode_to_ascii, query_dict))
    return deep_map(unicode_to_ascii, deep_map(datetime_to_isodate, deep_map(boolean_to_mongoboolean, query_dict)))
