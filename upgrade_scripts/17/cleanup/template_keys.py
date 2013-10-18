'''Removes the keys "sequence" and "version" from all template utility bill
documents (ones whose "sequence" is 0)
'''
import pymongo
#from billing.util.mongo_utils import check_error

db = pymongo.Connection('localhost')['skyline-dev']

db.utilbills.update({'sequence': 0},
        {'$unset': {'sequence': 1, 'version':1}}, multi=True)

