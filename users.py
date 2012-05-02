import sys
import copy
import pymongo
import bcrypt
import argparse

class User:
    '''A class representing a user account. This is a thin wrapper around a
    Mongo document.'''

    def __init__(self, dictionary):
        self.dictionary = dictionary

    @property
    def identifier(self):
        # OpenID URL/Mongo document id: this should be read-only once the
        # account is created
        return self.dictionary['_id']

    @property
    def username(self):
        # we get this from the OpenID identity provider
        return self.dictionary['username']

    @property
    def preferences(self):
        return self.dictionary['preferences']

#    def get_preference(self, key):
#        '''Get a user preference using its name (e.g.
#        "bill_image_resolution").'''
#        return self.dictionary['preferences'][key]
#
#    def set_preference(self, key, value):
#        '''Set (or create) a user preference using its name.'''
#        self.dictionary['preferences'][key] = value

    
class UserDAO:
    '''Data Access Object for reading and writing user data.'''

    # default user account: the one you get when authentication is turned off,
    # and the template for newly-created accounts. this is a class variable
    # because all instances of UserDAO (if there's more than one) should have
    # the same _default_user (otherwise save-prevention would not work)
    default_user = User({
        '_id':'default',
        'username':'Default User',
        'preferences': {
            'bill_image_resolution': 80
        }
    })

    def __init__(self, config):
        self.config = config
        connection = None

        try:
            connection = pymongo.Connection(self.config['host'], int(self.config['port'])) 
        except Exception as e: 
            print >> sys.stderr, "Exception when connecting to Mongo:" + str(e)
            raise
            
        self.collection = connection[self.config['database']][self.config['collection']]
    
    def create_user(self, username, password):
        '''Creates a new user with the given username and password and saves it
        in the database.'''
        # generate a salt, and hash the password + salt
        salt = bcrypt.gensalt()
        pw_hash = bcrypt.hashpw(password, salt)

        # new user is based on default user
        new_user = copy.deepcopy(UserDAO.default_user)
        new_user.dictionary['username'] = username
        new_user.dictionary['identifier'] = username
        new_user.dictionary['password_hash'] = pw_hash
        new_user.dictionary['salt'] = salt

        # save in db
        self.save_user(new_user)

    def load_user(self, username, password):
        '''Returns a User object representing the user given by 'username' and
        'password'. Returns None if the username/password combination was
        wrong.'''
        # get user document from mongo (authentication fails if there isn't one
        # with the given username)
        user_dict = self.collection.find_one({
            '_id': username,
        })
        if user_dict is None:
            return None

        # hash the given password using the salt from the user document
        pw_hash = bcrypt.hashpw(password, user_dict['salt'])

        # authentication succeeds iff the result matches the password hash
        # stored in the document
        if pw_hash == user_dict['password_hash']:
            return User(user_dict)
        return None

    def load_openid_user(self, identifier):
        '''Returns a User object representing the user given by 'identifier'
        (username or an OpenID URL), or None if the user is not found.'''
        user_dict = self.collection.find_one({'_id': identifier})
        if user_dict is None:
            return None

        if password != None:
            if 'password' in user_dict:
                if password != user_dict['password']:
                    return None
            else:
                # if password is provided but not needed, ignore it
                pass

        return User(user_dict)

    def save_user(self, user):
        '''Saves the User object 'user' into the database. This overwrites any
        existing user with the same identifier.'''
        # for the default user, do nothing
        if user is UserDAO.default_user:
            return

        self.collection.save(user.dictionary)

if __name__ == '__main__':
    # command-line arguments
    #parser = argparse.ArgumentParser(description='Create and authenticate user accounts')
    #parser.add_argument('create', dest=username)
    from sys import argv
    dao = UserDAO({
        'host': 'localhost',
        'port': 27017,
        'database': 'skyline',
        'collection': 'users',
        'user': 'dev',
        'password': 'dev',
    })
    command = argv[1]
    username = argv[2]
    password = argv[3]

    if command == 'add':
        dao.create_user(username, password)
        print 'created'

    elif command == 'check':
        result = dao.load_user(username, password)
        if result is None:
            print 'authentication failed'
        else:
            print 'authentication succeeded:', result
