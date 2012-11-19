#!/usr/bin/python

import simplejson as json
import datetime
from decimal import Decimal
from mutable_named_tuple import MutableNamedTuple
import dateutil.parser
from bson.objectid import ObjectId
import re

date_pattern = re.compile("^\d\d\d\d+-\d+-\d+$")

#2011-11-01 15:33:52.997167
# TODO: determine what javascript sends via Ajax
datetime_pattern = re.compile("^\d\d\d\d+-\d\d-\d\d \d\d:\d\d:\d\d\.\d+$")

def __encode_obj__(obj):
    if type(obj) is datetime.date:
        return obj.strftime("%Y-%m-%d")
    elif type(obj) is datetime.datetime:
        return obj.isoformat()
    elif type(obj) is ObjectId: 
        return str(obj)


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

def __convert_to_mnt__(obj):
    new_pairs = []
    for name, value in obj:
        #happens if your key's value is a string
        if isinstance(value, basestring):
            # TODO:  and the name of this string is in a dict of fields to be converted to dates
            if date_pattern.match(value) is not None: 
                value = datetime.datetime.strptime(value, "%Y-%m-%d").date()
        #happens if your key's value is a list
        elif type(value) is list:
            for n,i in enumerate(value):
                if isinstance(i, basestring):
                    if date_pattern.search(i) is not None:
                        value[n] = datetime.datetime.strptime(value,
                                                              "%Y-%m-%d").date()
        new_pairs.append((name, value))
    return MutableNamedTuple(new_pairs)


def dumps(obj):
    return json.dumps(obj, default=__encode_obj__, use_decimal=True)

def loads(obj):
    #return json.loads(obj, object_pairs_hook=__convert_to_mnt__, use_decimal=True)
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
    #object_pairs_hook=convert_to_mnt, object_hook=decode_date, 
    print "my_struct loaded from json %s" % load

    print load == my_struct

