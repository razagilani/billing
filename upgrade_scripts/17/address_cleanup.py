from itertools import chain
from pymongo import Connection

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

db = Connection('localhost')['skyline-dev']

ALL_KEYS = ['addressee', 'street', 'city', 'state', 'postal_code']

for collection in (db.utilbills, db.reebills):
    for doc in collection.find():
        modified = False
        for subdoc in (doc['billing_address'], doc['service_address']):
            for key in ALL_KEYS:
                if key not in subdoc:
                    subdoc[key] = 'https://www.pivotaltracker.com/story/show/55045748'
                    modified = True
        if modified:
            collection.save(doc)
