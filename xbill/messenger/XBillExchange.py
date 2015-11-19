if __name__ == "__main__":
    # Setup Django before imports, if this is run as a script
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "xbill.settings")

import time
import random
import traceback
import logging

from intro.models import Account, UtilityWebsiteInformation, User
from mq.exceptions import InvalidRequest, UnsupportedVersion
from mq import MessageHandler, Exchange, init_logging, REJECT_MESSAGE
from django.db.models import Q
from django.db import transaction
from os.path import dirname, realpath, join


class CredentialsHandler(MessageHandler):

    @transaction.commit_on_success
    def handle(self, message):
        if 'message_version' not in message:
            raise InvalidRequest("Malformed message. Expected a"
                                 " message_version parameter")

        if message['message_version'][0] != 2:
            raise UnsupportedVersion("This message version is unsupported")

        utilities = message.get('utilities', None)
        account_guids = message.get('account_guids', None)
        reply = {
            "message_version": [3, 0],
        }
        records = []

        uwis = UtilityWebsiteInformation.objects.select_related(
            'utility_provider')

        # Chain uilities with OR
        if utilities is not None and len(utilities) >= 1:
            queries = [Q(utility_provider__guid__iexact=u) for u in utilities]
            query = queries.pop()
            for q in queries:
                query |= q
            uwis = uwis.filter(query)

        # Chain accounts with OR
        if account_guids is not None and len(account_guids) >= 1:
            queries = [Q(accounts__guid__iexact=a) for a in account_guids]
            query = queries.pop()
            for q in queries:
                query |= q
            uwis = uwis.filter(query)

        for uwi in uwis:
            records.append({
                'username': uwi.get_username(),
                'password': uwi.get_password(),
                'utility_guid': uwi.utility_provider.guid,
                'account_guids': [
                    str(a.guid) for a in uwi.accounts.exclude(guid__isnull=True)
                ]
            })
        reply['records'] = records
        return reply


class AccountCreateHandler(MessageHandler):

    on_error = REJECT_MESSAGE

    @transaction.commit_on_success
    def handle(self, message):
        self.logger.info( "Altitude handler handling message %s: " %
            message)
        account = Account(
            name=message['customer_account_name'],
            guid=message['customer_account_guid'],
            created=message['create_date']
            #modified=message['modified_date']
            )
        account.save()
        self.logger.info('Account %s created' % account.guid)


class AccountUpdateHandler(MessageHandler):

    on_error = REJECT_MESSAGE

    @transaction.commit_on_success
    def handle(self, message):
        acc, created = Account.objects.get_or_create(
            guid__iexact=message['customer_account_guid']
        )
        if created:
            self.logger.warning(
                'Update operation on non-existent record. Record created.'
            )

        acc.guid = message['customer_account_guid_updated']
        acc.name = message['customer_account_name_updated']
        acc.modified = message['modified_date_updated']
        acc.save()
        self.logger.info('Account %s updated' % acc.guid)


class AccountDeletedHandler(MessageHandler):

    on_error = REJECT_MESSAGE

    @transaction.commit_on_success
    def handle(self, message):
        account = Account.objects.get(guid__iexact=message[
            'customer_account_guid'])
        account.delete()
        self.logger.info("Account %s deleted" % account.guid)


# class IndividualHandler(MessageHandler):
#
#     def handle(self, message):
#         self.logger = logging.getLogger('exchange')
#         self.logger.info( "Altitude handler handling message %s: " %
#             message)
#         try:
#             individual_data = message
#             user = User(account=None,
#                     first_name=individual_data['First_Name'],
#                     last_name=individual_data['Last_Name'],
#                     created=individual_data['Date_Created'],
#                     guid=individual_data['GUID'],
#                     email_address=individual_data['Email'])
#             self.save_user(user)
#         except Exception as e:
#             print traceback.format_exc()
#         return "New User created"
#
#     @transaction.commit_on_success
#     def save_user(self,user):
#         user.save()
#         self.logger.info("Saved user object %s to User table" \
#         % user)

if __name__ == "__main__":
    init_logging(join(dirname(realpath(__name__)), 'logging.cfg'))
    e = Exchange('xbill')
    e.attach_handler('get_credentials', CredentialsHandler)
    e.attach_handler('create_account', AccountCreateHandler)
    e.attach_handler('update_account', AccountUpdateHandler)
    e.attach_handler('delete_account', AccountDeletedHandler)
    #e.attach_handler('individual_handler', IndividualHandler)
    e.run()