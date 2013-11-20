#!/usr/bin/python

import simplejson as json
import datetime
from decimal import Decimal
import dateutil.parser
from bson.objectid import ObjectId
import re

date_pattern = re.compile("^\d\d\d\d+-\d+-\d+$")

#2011-11-01 15:33:52.997167
# TODO: determine what javascript sends via Ajax
datetime_pattern = re.compile("^\d\d\d\d+-\d\d-\d\d \d\d:\d\d:\d\d\.\d+$")

def __encode_obj__(obj):
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise ValueError('Object of type "%s" is not JSON serializable' %
            type(obj))


# can't use object_hook when object_pairs_hook is being used
def __decode_str__(d):
    for name, value in d.items():
        if isinstance(value, basestring):
            # TODO:  and the name of this string is in a dict of fields to be converted to dates
            # otherwise we could very well parse an incoming text field...
            if date_pattern.match(value) is not None: 
                print "encountered date"
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
            if datetime_pattern.match(value) is not None:
                print "encountered datetime"
                iso8601 = dateutil.parser.parse(value)
                return iso8601.astimezone(dateutil.tz.tzutc())
            if name == "_id":
                return ObjectId(value)
    return d

def dumps(obj):
    return json.dumps(obj, default=__encode_obj__, use_decimal=True)

def loads(obj):
    return json.loads(obj, object_hook=__decode_str__, use_decimal=True)


if __name__ == "__main__":

    import pdb; pdb.set_trace()

    iso8601_str = dumps(datetime.datetime.now())
    print type(iso8601_str)

    iso8601_obj = loads(iso8601_str)
    print type(iso8601_obj)

    my_struct = MutableNamedTuple()
    my_struct.prop1 = 1
    my_struct.prop2 = Decimal("1.1")
    my_struct.prop2a = Decimal("1.1")
    my_struct.prop3 = "3"
    child = MutableNamedTuple()
    child.begindate = datetime.datetime.now().date()
    my_struct.prop4 = child

    print "The structure: %s" % my_struct

    dump = dumps(my_struct)
    print "my_struct dumped to json %s " % dump

    load = loads(dump)
    print "my_struct loaded from json %s" % load

    print load == my_struct

