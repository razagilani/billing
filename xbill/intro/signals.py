from django.dispatch import receiver
from django.db.models.signals import post_save, m2m_changed
from datetime import datetime

from intro.models import Account, User, UtilityWebsiteInformation, \
    UtilityProvider
from messenger.publishers import XBillAccountPublisher, \
    XBillIndividualPublisher, MakeScrapeRequestPublisher,\
    UtilityProviderPublisher
from xbill import settings

'''@receiver(post_save, sender=Account)
# These are commented for now as We don't yet want data originating in Portal to be sent to Altitude
def publish_accounts(sender, **kwargs):

    if kwargs.get('created', True):
        account = kwargs.get('instance')
        account_guid = str(account.guid) if account.guid is not None else None
        message = {'customer_account_name': account.name,
                   'create_date': account.created.strftime('%Y-%m-%d %H:%M:%S'),
                   'customer_account_guid': account_guid
        }
        publisher = XBillAccountPublisher()
        publisher.publish(message)

@receiver(post_save, sender=User)
def publish_individuals(sender, **kwargs):

    if kwargs.get('created', True):
        individual = kwargs.get('instance')
        message = {'Individual': {'First_Name': individual.first_name,
                                  'Last_Name': individual.last_name,
                                  'Email': individual.email_address,
                                  'Date_Created': individual.created.strftime('%Y-%m-%d %H:%M:%S'),
                                  'GUID': individual.guid,
                                  'Company': 2,
                                  'City': 4,
                                  'Emp_Dept': 1,
                                  'Emp_Office': 1
        }}
        publisher = XBillIndividualPublisher()
        publisher.publish(message)'''

@receiver(m2m_changed, sender=UtilityWebsiteInformation.accounts.through,
          dispatch_uid='make_scraping_request')
def make_scraping_request(sender, instance, action, **kwargs):
    if action != 'post_add':
        return
    uwi = instance
    publisher = MakeScrapeRequestPublisher()
    publisher.scrape_bills(
        [str(a.guid) for a in uwi.accounts.exclude(guid__isnull=True)],
        str(uwi.utility_provider.guid) if uwi.utility_provider.guid else None,
        uwi.get_username(),
        uwi.get_password(),
        datetime(1900, 1, 1))

@receiver(post_save, sender=UtilityProvider,
          dispatch_uid='publish_utility_provider')
def publish_utility_provider(sender, instance, **kwargs):
    up = instance
    if up.type == UtilityProvider.UTILITY:
        publisher = UtilityProviderPublisher()
        publisher.publish_utility_provider(up.name, up.guid)




