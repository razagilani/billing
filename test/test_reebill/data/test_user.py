"""Tests related to User and UserDAO.
"""
from unittest import TestCase
from core import init_model
from core.model import Session
from reebill.reebill_model import User
from reebill.users import UserDAO
from test import init_test_config, create_tables, clear_db


class TestUser(TestCase):
    """Unit tests for User class.
    """
    def setUp(self):
        self.u = User(identifier='someone@example.com',
                      password_hash='passwordhash', salt='abc123')

    def test_set_preference(self):
        self.assertEqual({}, self.u.get_preferences())
        self.assertEqual({}, self.u.get_preferences())
        self.u.set_preference('a', 1)
        self.assertEqual({'a': 1}, self.u.get_preferences())

        # malformed JSON gets reset to empty
        self.u._preferences = '.'
        self.assertEqual({}, self.u.get_preferences())


class TestUserDAO(TestCase):
    """Tests for UserDAO with database.
    """
    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()

    def setUp(self):
        self.dao = UserDAO()
        clear_db()

    def test_create_load_users(self):
        # no users yet
        self.assertFalse(self.dao.user_exists('someone@example.com'))
        self.assertIsNone(self.dao.load_user('someone@example.com', 'secret'))
        self.assertFalse(
            self.dao.change_password('someone@example.com', 'secret', 'new'))

        # create and load user
        self.dao.create_user('someone@example.com', 'secret', name='someone')
        self.assertTrue(self.dao.user_exists('someone@example.com'))
        u = self.dao.load_user('someone@example.com', 'secret')
        self.assertIsNotNone(u)

        # change password
        self.assertTrue(
            self.dao.change_password('someone@example.com', 'secret', 'new'))
        self.assertIsNone(self.dao.load_user('someone@example.com', 'secret'))
        self.assertIsNotNone(self.dao.load_user('someone@example.com', 'new'))

        # recreate existing user
        with self.assertRaises(ValueError):
            self.dao.create_user('someone@example.com', 'secret',
                                 name='someone')

    def test_set_load_by_session_token(self):
        u = self.dao.create_user('someone@example.com', 'secret',
                                 name='someone')
        Session().flush()
        self.dao.set_session_token_for_user(u, 'sessiontoken')

        u2 = self.dao.load_by_session_token('sessiontoken')
        self.assertEqual(u, u2)
        self.assertEqual(u2.session_token, 'sessiontoken')
