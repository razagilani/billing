import datetime
from datetime import date, time, datetime
from decimal import Decimal
from billing.mutable_named_tuple import MutableNamedTuple
from bson.objectid import ObjectId

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

