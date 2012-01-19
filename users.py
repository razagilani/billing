import sys
import pymongo

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

    # this is a class variable because all instances of UserDAO (if there's
    # more than one) should have the same _default_user (otherwise
    # save-prevention would not work)
    _default_user = User({
        '_id':'default',
        'username':'Default User',
        'preferences': {
            'bill_image_resolution': 250
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
        finally:
            if connection is not None:
                #self.connection.disconnect()
                # TODO when to disconnect from the database?
                pass
            
        self.collection = connection[self.config['database']][self.config['collection']]
    
    def load_user(self, identifier):
        '''Returns a User object representing the user given by 'identifier'
        (generally an OpenID URL).'''
        user_dict = self.collection.find_one({'_id': identifier})

        if user_dict is None:
            return None

        return User(user_dict)

    def get_default_user(self, identifier):
        '''A user not in the database with default values for all preferences,
        used when authentication is turned off.'''
        return self._default_user

    def save_user(self, user):
        '''Saves the User object 'user' into the database. This overwrites any
        existing user with the same identifier.'''
        # for the default user, do nothing
        if user is self._default_user:
            return

        self.collection.save(user.dictionary)

