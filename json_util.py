#!/usr/bin/python

import simplejson as json
import datetime
from decimal import Decimal
from mutable_named_tuple import MutableNamedTuple

import re

date_pattern = re.compile("^\d\d\d\d+-\d+-\d+$")

def __encode_date__(obj):
    if type(obj) is datetime.date:
        return obj.strftime("%Y-%m-%d")


# can't use object_hook when object_pairs_hook is being used
def __decode_date__(d):
    for name, value in d.items():
        if type(value) is str:
            # TODO:  and the name of this string is in a dict of fields to be converted to dates
            if date_pattern.match(value) is not None: 
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    return d

def __convert_to_mnt__(obj):
    new_pairs = []
    for name, value in obj:
        if type(value) is str:
            # TODO:  and the name of this string is in a dict of fields to be converted to dates
            if date_pattern.match(value) is not None: 
                value = datetime.datetime.strptime(value, "%Y-%m-%d").date()
        new_pairs.append((name, value))
    return MutableNamedTuple(new_pairs)


def dumps(obj):
    return json.dumps(obj, default=__encode_date__, use_decimal=True)

def loads(obj):
    return json.loads(dump, object_pairs_hook=__convert_to_mnt__, use_decimal=True)


if __name__ == "__main__":

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

