"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import uuid
import os
from datetime import datetime

from django.test import TestCase
from dateutil.relativedelta import relativedelta
from django.core.urlresolvers import reverse
from django.core.management import call_command
import mock
from django.utils import timezone

from models import *


# Disable logging, except critical errors
# logging.disable(logging.CRITICAL)

#######################
#    Model Tests
#


class CreateUserTest(TestCase):
    def setUp(self):
        self.account = Account(guid="60esb1b2-4a2b-4b77-b3ee-57db898078e4")
        self.account.save()

    def test_create_user(self):
        user = User.objects.create_user(self.account, "test1@test.com", "password")
        user.first_name = "Arthur"
        user.last_name = "Dent"
        user.save()
        self.assertEqual(user.email_address, "test1@test.com")
        self.assertEqual(user.email_address_verified, False)
        self.assertEqual(user.get_full_name(), "Arthur Dent")
        self.assertEqual(user.get_short_name(), "Arthur")
        self.assertEqual(user.is_staff, False)
        self.assertEqual(user.is_admin, False)
        self.assertEqual(user.user_state, User.ACTIVE)

    def test_create_superuser(self):
        user = User.objects.create_superuser("test2@test.com", "password")
        user.save()
        self.assertEqual(user.email_address, "test2@test.com")
        self.assertEqual(user.email_address_verified, False)
        self.assertEqual(user.get_full_name(), "")
        self.assertEqual(user.get_short_name(), "")
        self.assertEqual(user.is_staff, True)
        self.assertEqual(user.is_admin, True)
        self.assertEqual(user.user_state, User.ACTIVE)

    def test_create_user_faulty(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(self.account, None, None)
        with self.assertRaises(ValueError):
            User.objects.create_superuser(None, None)


class CreateTokenTest(TestCase):
    def setUp(self):
        a = Account(guid="60e6b1b2-4a2b-4b77-b3ee-57db898078e4")
        a.save()
        u = User.objects.create_user(a, "test3@test.com", "password")
        u.save()

    def test_create_token(self):
        user = User.objects.get(email_address="test3@test.com")
        token = Token.create_token(user, 'verify-email', years=5, months=42,
                                   days=1324, weeks=435, hours=453,
                                   minutes=3456,
                                   seconds=3456, microseconds=234324)
        token.save()
        self.assertEqual(token.purpose, 'verify-email')
        d = date.today() + relativedelta(years=5, months=42, days=1324,
                                         weeks=435, hours=453, minutes=3456,
                                         seconds=3456, microseconds=234324)
        self.assertEqual(token.expires, d)


class UtilityWebsiteInformationTest(TestCase):
    def setUp(self):
        a = Account(guid="60e6b1b2-4a2b-4b77-b3ee-57db8a3078e4")
        a.save()
        up = UtilityProvider(name="Random Provider", registrationrule=2)
        up.save()

    def test_create(self):
        account = Account.objects.get(guid="60e6b1b2-4a2b-4b77-b3ee-57db8a3078e4")
        utilprovider = UtilityProvider.objects.get(name="Random Provider")
        uwi = UtilityWebsiteInformation.create('utility username',
                                               'utility password',
                                               utilprovider,
                                               account)
        self.assertEqual(uwi.get_username(), 'utility username')
        self.assertEqual(uwi.get_password(), 'utility password')
        self.assertEqual(uwi.utility_username_decrypted, 'utility username')
        self.assertEqual(uwi.utility_password_decrypted, 'utility password')
        self.assertNotEqual(uwi.utility_username, 'utility username')
        self.assertNotEqual(uwi.utility_password, 'utility password')
        uwi.set_username("another username")
        uwi.set_password("another password")
        self.assertEqual(uwi.get_username(), 'another username')
        self.assertEqual(uwi.get_password(), 'another password')
        self.assertEqual(uwi.utility_username_decrypted, 'another username')
        self.assertEqual(uwi.utility_password_decrypted, 'another password')
        self.assertNotEqual(uwi.utility_username, 'another username')
        self.assertNotEqual(uwi.utility_password, 'another password')

class AccountTest(TestCase):
    fixtures = ['states.json']

    def setUp(self):
        self.address = Address(street1="Somestreet", city="Somecity",
                               state=State.objects.get(id=7), zip='21221')
        content = Content(name='TOU',
                          content='',
                          version=4)
        content.save()

    def test_create(self):
        a = Account(guid="60e6b1b2-4a2b-4b77-b3ee-57db8a3078e4")
        a.save()
        self.assertIsNone(a.token)
        self.assertIsNone(a.name)
        self.assertIsNotNone(a.tou_signed)
        a = Account(token="btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal2tm36s4j7z",
                    guid=uuid.uuid4(),
                    address=self.address,
                    name="Arthur Dent",
                    tou_signed=None)
        a.save()
        self.assertIsNone(a.tou_signed)
        self.assertEqual(a.token, "btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal2tm36s4j7z")
        self.assertEqual(a.name, 'Arthur Dent')
        self.assertIsNotNone(a.guid)

    def test_tou_version(self):
        # First account signs tou by default, also adds version by default
        a1 = Account(guid="70e6b1b2-4a2b-4b77-b3ee-57db8a3078e4")
        a1.save()
        self.assertEqual(a1.tou_version_signed, 4)

        # Second account does not sign tou by default,
        #  don't add version by default
        a2 = Account(guid="72e6b1b2-4a2b-4b77-b3ee-57db8a3078e4",
                     tou_signed=None)
        a2.save()
        self.assertEqual(a2.tou_version_signed, None)
        content = Content(name='TOU',
                          content='',
                          version=5)
        content.save()
        # Third account was created after a new tou version created.
        # The account should use the newest version by default
        a3 = Account(guid="73e6b1b2-4a2b-4b77-b3ee-57db8a3078e4")
        a3.save()
        self.assertEqual(a3.tou_version_signed, 5)

        # Let's update the second account. The tou version should not be changed
        a2.first_name="John"
        a2.save()
        self.assertEqual(a2.tou_version_signed, None)

        # Let's update the tou_signed date of the second version. The tou
        # version should be updated to the latest version
        a2.tou_signed = timezone.now()
        a2.save()
        self.assertEqual(a2.tou_version_signed, 5)


#######################
#    View Tests
#

#######################
#    Scripts Tests
#


class ScriptsTest(TestCase):
    def test_accounts_tandc_export(self):
        """ The documentation/spec for this can be found in
            Dropbox/Teams/Everyone/ETL Specifications/XBill/ """

        content = Content(name='TOU',
                          content='',
                          version=4)
        content.save()
        a_date_guid = Account(guid="60e6b1b2-4a2b-4b77-b3ee-57db8a3078e4",
                              tou_signed=timezone.make_aware(
                                  datetime(2012, 12, 2, 2, 2, 2),
                                  timezone.get_default_timezone()
                              ))
        a_date_guid.save()

        content2 = Content(name='TOU',
                          content='sdfds',
                          version=5)
        content2.save()
        a_date_guid = Account(guid="70e7b1b2-4a2b-4b77-b3ee-57db8a307877",
                              tou_signed=timezone.make_aware(
                                  datetime(2013, 12, 20, 14, 57, 13),
                                  timezone.get_default_timezone()
                              ))
        a_date_guid.save()


        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            call_command('accounts_tandc_export')
        m.assert_called_once_with(
            os.path.join(settings.XBILL_ETL_DIR,
                         settings.XBILL_ETL_ACCOUNTS_DIR,
                        'accounts.csv'),
            'wb')
        handle = m()
        expected_write = [mock.call('guid,opt-in 1 signed date,opt-in 1 '
                                    'version\r\n'),
                          mock.call('70e7b1b2-4a2b-4b77-b3ee-57db8a307877,'
                                    '2013-12-20T19:57:13+00:00,5\r\n'),
                          mock.call('60e6b1b2-4a2b-4b77-b3ee-57db8a3078e4,'
                                    '2012-12-02T07:02:02+00:00,4\r\n')]
        self.assertEqual(handle.write.call_args_list, expected_write)

class ImportAccountsTest(TestCase):
    """
            The documentation/spec for this can be found in
            Dropbox/Teams/Everyone/ETL Specifications/XBill/

            There are 9 cases we need to cover:
                 1) Account doesn't exist, User doesn't exists
                 => Both are created
                 2) Account doesn't exist, email address is missing
                 => Only Account is created
                 3) Account exists, User was connected and imported,
                    import email_address is none
                 => Account updated, imported users get deleted,
                    not imported users get unlinked
                 4) Account exists, no user is linked, imported email address
                    coincides with a user that does not have a linked account
                 => User is linked to account; user not counted as imported
                 5) Account does not exist, imported email address conicides
                    with a user that does not have a linked account
                 => account is created and user is linked to account; user
                    not counted as imported
                 6) Account does exist, first_name & last_name coincides
                    with imported user, email_address different
                 => Update account, update user whose fn and ln coincides
                 7) Account does exist, first_name & last_name does not coincide
                    with imported user, email_address different
                 =>  Update account, drop User, create new user and link
                    to account
                 8) Altitude reconciliation: Account with only token is defined.
                    An import should update the account and add a User if
                    email address exists
    """
    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case1(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        1) Account doesn't exist, User doesn't exists
        => Both are created
        """
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name':'Arthur',
                'last name':'Dent',
                'email':'adent@skylineinnovations.com'}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc=Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        user=User.objects.get(email_address="adent@skylineinnovations.com")
        self.assertEqual(user.first_name, "Arthur")
        self.assertEqual(user.last_name, "Dent")
        self.assertEqual(user.account, acc)
        self.assertEqual(user.user_state, User.INACTIVE)
        self.assertEqual(acc.name, 'Arthur Dent')
        self.assertIsNone(acc.tou_signed)
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case2(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        2) Account doesn't exist, email address is missing
           => Only Account is created
        """
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': '',
                'last name': '',
                'email': ''}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc=Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        with self.assertRaises(User.DoesNotExist):
            u=User.objects.get(account=acc)
        self.assertEqual(acc.name, '')
        self.assertIsNone(acc.tou_signed)
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case3(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        3) Account exists, User was connected and imported,
           import email_address is none
        => Account updated, imported users get deleted,
           not imported users get unlinked
        """
        existing_acc = Account(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                               name='Charles Darwin',
                               token='Sometoken'
                               )
        existing_acc.save()
        u1 = User(email_address="test@test.com",
                  user_state=User.INACTIVE,
                  first_name='Charles',
                  last_name='Darwin',
                  imported=True,
                  account=existing_acc)
        u1.save()
        u2 = User(email_address="test2@test.com",
                  user_state=User.INACTIVE,
                  first_name='Fred Mayer',
                  last_name='',
                  imported=False,
                  account=existing_acc)
        u2.save()
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': 'Jack',
                'last name': 'Sparrow',
                'email': ''}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc=Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(account=acc)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(email_address="test@test.com")
        unlinked_user = User.objects.get(email_address="test2@test.com")
        self.assertEqual(unlinked_user.account, None)
        self.assertEqual(acc.name, 'Jack Sparrow')
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case4(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        4) Account exists, no user is linked, imported email address
           coincides with a user that does not have a linked account
        => User is linked to account; user not counted as imported
        """
        existing_acc = Account(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                               name='Charles Darwin',
                               token='Sometoken'
                               )
        existing_acc.save()
        u1 = User(email_address="test@test.com",
                  user_state=User.INACTIVE,
                  first_name='Charles',
                  last_name='Darwin',
                  imported=False,
                  account=None)
        u1.save()
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': 'Jack',
                'last name': 'Sparrow',
                'email': 'test@test.com'}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc=Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        linked_user = User.objects.get(account=acc)
        self.assertEqual(linked_user.email_address, "test@test.com")
        self.assertEqual(linked_user.first_name, "Charles")
        self.assertEqual(linked_user.last_name, "Darwin")
        self.assertEqual(linked_user.imported, False)
        self.assertEqual(acc.name, 'Jack Sparrow')
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case5(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        5) Account does not exist, imported email address conicides
           with a user that does not have a linked account
        => account is created and user is linked to account; user
           not counted as imported
        """
        u1 = User(email_address="test@test.com",
                  user_state=User.INACTIVE,
                  first_name='Charles',
                  last_name='Darwin',
                  imported=False,
                  account=None)
        u1.save()
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': 'Jack',
                'last name': 'Sparrow',
                'email': 'test@test.com'}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc=Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        linked_user = User.objects.get(account=acc)
        self.assertEqual(linked_user.email_address, "test@test.com")
        self.assertEqual(linked_user.first_name, "Charles")
        self.assertEqual(linked_user.last_name, "Darwin")
        self.assertEqual(linked_user.imported, False)
        self.assertEqual(acc.name, 'Jack Sparrow')
        self.assertIsNone(acc.tou_signed)
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case6(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        6) Account does exist, first_name & last_name coincides
           with imported user, email_address different
        => Update account, update user whose fn and ln coincides
        """
        existing_acc = Account(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                               name='Charles Darwin',
                               token='Sometoken'
                               )
        existing_acc.save()
        u1 = User(email_address="test@test.com",
                  user_state=User.INACTIVE,
                  first_name='Charles',
                  last_name='Darwin',
                  imported=True,
                  account=existing_acc)
        u1.save()
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': 'Charles',
                'last name': 'Darwin',
                'email': 'somethingelse@test.com'}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc=Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        linked_user = User.objects.get(account=acc)
        self.assertEqual(linked_user.id, u1.id)
        self.assertEqual(linked_user.email_address, "somethingelse@test.com")
        self.assertEqual(linked_user.first_name, "Charles")
        self.assertEqual(linked_user.last_name, "Darwin")
        self.assertEqual(linked_user.imported, True)
        self.assertEqual(acc.name, 'Charles Darwin')
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case7(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
        7) Account does exist, first_name & last_name does not coincide
           with imported user, email_address different
        => Update account, drop User, create new user and link
           to account
        """
        existing_acc = Account(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                               name='Charles Darwin',
                               token='Sometoken')
        existing_acc.save()
        u1 = User(email_address="test@test.com",
                  user_state=User.INACTIVE,
                  first_name='Charles',
                  last_name='Darwin',
                  imported=True,
                  account=existing_acc)
        u1.save()
        data = {'guid':'8055830C-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': 'C3PO',
                'last name': 'R2D2',
                'email': 'somethingelse@test.com'}
        mock_listdir.return_value = ["btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal.csv"]
        mock_path.splitext.return_value = ("btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc = Account.objects.get(guid='8055830C-6ADD-4EAA-9BE4C6EAAC6802E')
        users = User.objects.filter(account=acc)
        self.assertEqual(len(users), 1)
        self.assertNotEqual(users[0].id, u1.id)
        self.assertEqual(users[0].email_address, "somethingelse@test.com")
        self.assertEqual(users[0].first_name, "C3PO")
        self.assertEqual(users[0].last_name, "R2D2")
        self.assertEqual(users[0].imported, True)
        self.assertEqual(acc.name, 'C3PO R2D2')
        self.assertEqual(acc.token, 'btfkvp5du4a54l9ji18o3id11vyfg36alnr6f15h7tvkhlzyal')

    @mock.patch('csv.DictReader.next')
    @mock.patch('os.path')
    @mock.patch('os.listdir')
    @mock.patch('os.remove')
    def test_case8(self,mock_remove, mock_listdir, mock_path,
                                  mock_next):
        """
         8) Altitude reconciliation: Account with only token is defined.
            An import should update the account and add a User if
            email address exists
        """
        existing_acc = Account(token='sometoken')
        existing_acc.save()
        data = {'guid': '8055830D-6ADD-4EAA-9BE4C6EAAC6802E',
                'first name': 'C3PO',
                'last name': 'R2D2',
                'email': 'someone@test.com'}
        mock_listdir.return_value = ["sometoken.csv"]
        mock_path.splitext.return_value = ("sometoken",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc = Account.objects.get(guid='8055830D-6ADD-4EAA-9BE4C6EAAC6802E')
        users = User.objects.filter(account=acc)
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].email_address, "someone@test.com")
        self.assertEqual(users[0].first_name, "C3PO")
        self.assertEqual(users[0].last_name, "R2D2")
        self.assertEqual(users[0].imported, True)
        self.assertEqual(acc.token, 'sometoken')
        self.assertEqual(acc.name, 'C3PO R2D2')

        # What if the email address/name doesn't exists

        existing_acc = Account(token='someothertoken')
        existing_acc.save()
        data = {'guid': '8055830D-6AFF-4EAA-9BE4C6EAAC6802E'}
        mock_listdir.return_value = ["someothertoken.csv"]
        mock_path.splitext.return_value = ("someothertoken",".csv")
        m = mock.mock_open()
        with mock.patch('__builtin__.open', m, create=True):
            mock_next.return_value = data
            call_command('add_account')
        acc = Account.objects.get(guid='8055830D-6AFF-4EAA-9BE4C6EAAC6802E')
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(account=acc)
        self.assertEqual(acc.token, 'someothertoken')
        self.assertEqual(acc.name, None)


class TestAdminInterface(TestCase):
    """
    A class that simply tests if custom modifications to admin.py still
    result in the page being properly displayed. This also tests if the
    search fields are configured correctly. This function does not need to
    test wether objects added via the admin interface are actually added to
    the database since admin will simply read from the model definition and
    then call object.save(). Object.save() should be tested elsewhere
    """

    def setUp(self):
        settings.COMPRESS_ENABLED = True
        self.account = Account(guid="admin-4a2b-4b77-b3ee-57db8a3078r4")
        u = User.objects.create_user(self.account, "admin@test.com", "password")
        u.email_address_verified = True
        u.is_admin = True
        u.is_superuser = True
        u.save()
        self.user = u

    def login(self):
        self.client.get('admin:index')
        response = self.client.post(reverse('admin:index'), {
            'username': 'admin@test.com',
            'password': 'password',
            'this_is_the_login_form': 1,
            'next': reverse('admin:index')
        }, follow=True)

    def check_listing_for_model(self, model_str, app='intro'):
        response = self.client.get(
            reverse('admin:%s_%s_changelist' % (app, model_str)))
        self.assertTemplateUsed(response, 'admin/change_list.html')

    def check_searching_for_model(self, model_str, app='intro'):
        # I couldn't figure out how to pass the query string into reverse to
        # get the app/model/?q=query url
        response = self.client.get(
            reverse('admin:%s_%s_changelist' % (app, model_str)) +
            '?q=somequery')
        self.assertTemplateUsed(response, 'admin/change_list.html')

    def check_adding_model(self, model_str, app='intro'):
        response = self.client.get(
            reverse('admin:%s_%s_add' % (app, model_str)))
        self.assertTemplateUsed(response, 'admin/change_form.html')

    def test_admin_customizations(self):
        self.login()
        models = ['state', 'address', 'account', 'user',
                  'token', 'utilityprovider', 'utilitywebsiteinformation',]
        for model in models:
            print 'Testing admin interface for %s' % model
            self.check_listing_for_model(model)
            self.check_adding_model(model)
            self.check_searching_for_model(model)