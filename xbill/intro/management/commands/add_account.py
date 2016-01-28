from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Q
from xbill import settings
from intro.models import Account,User
import logging
import os
import csv
import os.path


class Command(BaseCommand):
    help = 'Imports all new altitude CSV files in the ' \
           'skyline-etl/xbill/add_account/ directory as new accounts'

    """
    There are 7 cases we need to cover:
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
        => Update account, drop User, create new user and link
           to account
    """

    @transaction.commit_manually
    def handle(self, *args, **options):
        log = logging.getLogger('xbill-etl')
        path = os.path.join(settings.XBILL_ETL_DIR,
                            settings.XBILL_ETL_ADD_ACCOUNT_DIR)
        for f in os.listdir(path):

            if f.endswith('.csv'):
                filepath=os.path.join(path, f)
                try:
                    with open(filepath, 'rb') as csvfile:
                        reader = csv.DictReader(csvfile)
                        record = reader.next()
                except IOError as e:
                    log.error("I/O error({0}): {1} {2}".format(e.errno, e.strerror,
                                                           e.filename))
                except StopIteration as e:
                    log.error("(StopIteration) Malformed CSV file %s " %
                              filepath)
                    # This is a show stopper. Let's go to the next file!
                    continue

                token = os.path.splitext(f)[0]
                try:
                    guid = record['guid']
                except KeyError:
                    log.error('KeyError! %s did not contain a valid guid' %
                              filepath)
                    continue
                first_name = record.get('first name', None)
                last_name = record.get('last name', None)
                email_address = record.get('email', None)
                if first_name is None and last_name is None:
                    acc_name = None
                else:
                    acc_name = ' '.join([x for x in [first_name, last_name]
                                         if x is not None]).strip()
                try:
                    acc = Account.objects.get(Q(guid=guid) | Q(token=token))

                    # The Account already exists; let's update:
                    acc.name = acc_name
                    acc.guid = guid
                    acc.token = token
                    acc.save()
                    log.info('Account %s was updated. Record: %s' %
                            (token, record))

                    users = User.objects.filter(account=acc)
                    if email_address:
                        try:
                            # Let's see if there is an existing user with that
                            # email address. if thats the case
                            # 1) If user.account is none assign him to the acc
                            # 2) If user.account is acc, update the name
                            # 3) If user.account is something else raise an
                            # integrity error
                            existing_user = User.objects.get(
                                email_address=email_address)
                            if existing_user.account is None:
                                existing_user.account = acc
                                existing_user.save()
                                log.info('User %s was assigned to account %s.'
                                         ' Record: %s' % (email_address, token,
                                                          record))
                            elif existing_user.account == acc:
                                existing_user.first_name = first_name
                                existing_user.last_name = last_name
                                existing_user.save()
                                log.info('User %s was updated. Record:'
                                         ' %s' % (email_address, record))
                            elif existing_user.account is not acc:
                                log.error('Integrity Error! User with E-mail'
                                          ' address %s already exists in'
                                          ' Database and is already linked to'
                                          'an Account. Record: %s' %
                                          (email_address, record))
                                transaction.rollback()
                                continue
                        except User.DoesNotExist:
                            # Check if there is a user connected to the
                            # account whose first name, last name match the
                            # imported record
                            user_updated = False
                            for user in users:
                                if user.first_name == first_name and \
                                   user.last_name == last_name:
                                    # We assume the user is the same and his
                                    # email address was just updated
                                    user.email_address = email_address
                                    user.save()
                                    log.info('User %s was updated. Record: %s' %
                                             (email_address, record))
                                    user_updated = True
                                    break
                            if not user_updated:
                                user = User(email_address=email_address,
                                            user_state=User.INACTIVE,
                                            first_name=first_name,
                                            last_name=last_name,
                                            imported=True,
                                            account=acc)
                                user.save()
                                log.info('User %s created. Record: %s' %
                                             (email_address, record))
                        # Lastly drop all users that are associated with the
                        # account that are imported, whose email_adress is not
                        # email_address
                        for user in users:
                            if user.imported \
                                and user.email_address != email_address:
                                    log.info('Deleting imported user %s because'
                                             'email address is no longer '
                                             'associated with this account. '
                                             'Associated email address: %s '
                                             'Record: %s' %
                                             (user.email_address,
                                              email_address, record))
                                    user.delete()
                    else:
                        for user in users:
                            if user.imported:
                                log.info('Deleting imported user %s '
                                         'because there is no email address '
                                         'associated with the account. '
                                         'Record: %s' % (user.email_address,
                                                         record))
                                user.delete()
                            else:
                                log.info('User %s was not imported and has no'
                                         'Account associated. '
                                         'Record: %s' % (user.email_address,
                                                         record))
                                user.account = None
                                user.save()
                except Account.DoesNotExist:
                    # Create a new Account
                    acc = Account(guid=guid,
                                  name=acc_name,
                                  token=token,
                                  tou_signed=None)
                    if email_address:
                        # Check if the email Address is already registered
                        # currently, there is a 1-to-Many relationship between
                        # Accounts and Users. In the future this will be many
                        # to many. For now raise an error if the email address
                        # will exists and is linked to another account
                        try:
                            user = User.objects.get(email_address=email_address)
                            if user.account is None:
                                # The user exists, but is not connected to
                                # any account. Let's connect him to the new
                                # one
                                acc.save()
                                log.info('Account %s was created. Record: %s' %
                                    (token, record))
                                user.account = acc
                                user.save()
                                log.info('User %s was assigned to account %s.'
                                         ' Record: %s' % (email_address, token,
                                                          record))
                            else:
                                log.error('Integrity Error! User with E-mail'
                                          ' address %s already exists in'
                                          ' Database and is already linked to'
                                          'an Account. Record: %s' %
                                          (email_address, record))
                                transaction.rollback()
                                continue
                        except User.DoesNotExist:
                            # Let's create a new User
                            acc.save()
                            log.info('Account %s was created. Record: %s' %
                                    (token, record))
                            user = User(email_address=email_address,
                                        user_state=User.INACTIVE,
                                        first_name=first_name,
                                        last_name=last_name,
                                        imported=True,
                                        account=acc)
                            user.save()
                            log.info('User %s was created. Record: %s' %
                                    (email_address, record))
                    else:
                        # Account didn't exist and no email_address was provided
                        # Just save the account!
                        acc.save()
                        log.info('Account %s was created. Record: %s' %
                                    (token, record))
                # At this point all transactions should either be rolled back or
                # good to go
                try:
                    transaction.commit()
                    os.remove(filepath)
                except Exception as e:
                    transaction.rollback()
                    log.error("Exception: %s" % e.strerror)
