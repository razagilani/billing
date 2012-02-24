#!/usr/bin/python
import pymongo
#from mongo import ReebillDAO, NoRateStructureError, NoUtilityNameError

host = 'tyrell'
port = 27017
db = 'skyline-prod'

keys = set()

def add_keys(x):
    if type(x) is dict:
        for key, value in x.iteritems():
            if '_' not in key and ' ' not in key:
                keys.add(key)
            add_keys(value)
    elif type(x) is list:
        for element in x:
            add_keys(element)

#dao = ReebillDAO()
#for account in range(10001, 10020):
    #for seq in range(1, 20):
connection = pymongo.Connection(host, port)
collection = connection[db]['reebills']
for reebill in collection.find():
    #print reebill['account'], reebill['sequence']
    add_keys(reebill)

for key in sorted(keys):
    print key

'''
candidate tags found on tyrell skyline-prod:
Delivery
Distribution
Generation/Supply
Surcharges
Transmission
account
addressee
billingaddress
branch
city
country
description
estimated
factor
identifier
message
meters
month
postalcode
priorreading
processingnote
quantity
rate
registers
sequence
service
serviceaddress
shadow
state
statistics
street
total
totalrenewableproduced
type
utilbills
uuid

filtering out ones i know are ok:
billingaddress
postalcode
priorreading
processingnote
serviceaddress
totalrenewableproduced

util bill addresses aren't added anymore but we won't delete the old ones now.
processingnote is also vestigial
priorreading, totalrenewableproduced are definitely wrong.
the rest are address-related
'''
