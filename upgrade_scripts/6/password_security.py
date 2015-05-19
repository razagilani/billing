#!/usr/bin/python
'''Upgrade script to remove all user passwords and replace them with a secure
hash and salt. Also changes the "username" key to "name" for clarity.'''
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
    # username -> name
    if 'username' in user:
        user['name'] = user['username']
        del user['username']
        print '%s: fixed name' % user['name']
    else:
        print '%s: name already OK' % user['name']

    # password security
    if 'password' in user:
        password = user['password']
        del user['password']
        salt = bcrypt.gensalt()
        pw_hash = bcrypt.hashpw(password, salt)
        user['password_hash'] = pw_hash
        user['salt'] = salt
        print '%s: fixed password' % user['name']
    else:
        print '%s password already OK' % user['name']

    collection.save(user)
