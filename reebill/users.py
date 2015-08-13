import json

import bcrypt
from sqlalchemy.orm.exc import NoResultFound

from core.model import Session
from reebill.reebill_model import User


class UserDAO(object):
    """Data Access Object for user accounts."""

    # default user account: the one you get when authentication is turned off,
    # and the template for newly-created accounts. this is a class variable
    # because all instances of UserDAO (if there's more than one) should have
    # the same _default_user (otherwise save-prevention would not work)
    default_user = User(
        identifier='default', username='Default User',
        _preferences=json.dumps({'bill_image_resolution': 80,
                                'difference_threshold': 0.01,
                                'default_account_sort_field': 'account',
                                'default_account_sort_direction': 'ASC'}))

    def create_user(self, identifier, password, name=None):
        '''Creates a new user with the given identifier and password and saves
        it in the database. The user's human-readable name is 'identifier' by
        default.'''
        if name is None:
            name = identifier

        # make sure this user doesn't already exist:
        if self.user_exists(identifier):
            raise ValueError('A user with identifier "%s" already exists' %
                    identifier)

        # TODO externalize
        # generate a salt, and hash the password + salt
        salt = bcrypt.gensalt()
        pw_hash = bcrypt.hashpw(password, salt)

        # new user is based on default user
        new_user = User(identifier=identifier, username=name,
                        password_hash=pw_hash, salt=salt)

        Session().add(new_user)
        return new_user

    def user_exists(self, identifier):
        '''Returns True if there is a user with the given identifier (no
        password needed because user's data is not accessed).'''
        return Session().query(User).filter_by(
            identifier=identifier).count() != 0

    def load_user(self, identifier, password):
        '''Returns a User object representing the user given by 'identifier' and
        'password'. Returns None if the identifier/password combination was
        wrong.'''
        # get user (authentication fails if there isn't one with the given
        # identifier)
        try:
            user = Session().query(User).filter_by(identifier=identifier).one()
        except NoResultFound:
            return None

        # hash the given password using the salt from the user document
        pw_hash = bcrypt.hashpw(password, user.salt)

        # authentication succeeds iff the result matches the password hash
        # stored in the document
        if pw_hash == user.password_hash:
            return user
        return None

    def load_by_session_token(self, token):
        return Session().query(User).filter_by(session_token=token).first()

    def set_session_token_for_user(self, user, token):
        u = Session().query(User).filter_by(
            reebill_user_id=user.reebill_user_id).one()
        u.session_token = token

    def change_password(self, identifier, old_password, new_password):
        '''Sets a new password for the given user. Returns True for success,
        false for failure.'''
        user = self.load_user(identifier, old_password)
        if user == None:
            return False
        # salt stays the same
        user.password_hash = bcrypt.hashpw(new_password, user.salt)
        return True
