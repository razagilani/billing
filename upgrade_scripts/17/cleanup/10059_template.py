import pymongo
from bson import ObjectId
from billing.util.mongo_utils import check_error

db = pymongo.Connection('localhost')['skyline-dev']

check_error(db.utilbills.remove({'_id': ObjectId('516c6b7d99b10c29a08e01aa')},
        safe=True))
