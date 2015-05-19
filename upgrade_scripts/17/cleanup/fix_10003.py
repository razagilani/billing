import pymongo
import datetime
from bson import ObjectId

db = pymongo.Connection('localhost')['skyline-dev']
db.utilbills.update({'_id':ObjectId("5081b53957b1176a8e9c0850")},
                    {'$set':{'start':datetime.datetime(2012,6,14),
                             'end':datetime.datetime(2012,7,16)}})
db.utilbills.update({'_id':ObjectId("5081b53957b1176a8e9c084e")},
                    {'$set':{'start':datetime.datetime(2012,6,14),
                             'end':datetime.datetime(2012,7,16)}})
