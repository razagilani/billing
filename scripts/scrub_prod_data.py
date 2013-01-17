#!/usr/bin/env python
import argparse

import pymongo

# Fields to scrub
# collection : [collection name]
# field: [fully resolved field name]
# e.g.
# {'collection': 'utilbills', 'field': 'chargegroups.Distribution'}
fields_to_scrub = [
    {'collection': 'reebills',
     'field': 'bill_recipients'},
    {'collection': 'reebills',
     'field': 'last_recipients'}
]

parser = argparse.ArgumentParser()
parser.add_argument('TOENV', type=str, choices=('dev', 'stage', 'prod'), help='Environment specified for the de-stage')
args = parser.parse_args()

database_name = 'skyline-' + args.TOENV

db = pymongo.Connection('localhost', 27017)[database_name]

for field_to_scrub in fields_to_scrub:
    collection = field_to_scrub['collection']
    field = field_to_scrub['field']

    print "Scrubbing {0} from {1}...".format(field, collection)
    db[collection].update({}, {'$unset': {field: 1}}, multi=True)