#!/usr/bin/python
'''Upgrade script to remove all user passwords and replace them with a secure
hash and salt.'''
import bcrypt
import pymongo
from pymongo.objectid import ObjectId
from billing.users import UserDAO

# change these parameters to staging/production when running
config = {
    'host': 'localhost',
    'port': 27017,
    'database': 'skyline',
    'collection': 'users',
    'user': 'dev',
    'password': 'dev',
}

connection = pymongo.Connection(config['host'], config['port'])
collection = connection[config['database']][config['collection']]

for user in collection.find():
    if 'password' in user:
        password = user['password']
        del user['password']
        salt = bcrypt.gensalt()
        pw_hash = bcrypt.hashpw(password, salt)
        user['password_hash'] = pw_hash
        user['salt'] = salt
        collection.save(user)
        print 'updated user %s' % user['username']
    else:
        print 'skipped user %s' % user['username']
