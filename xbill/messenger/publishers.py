from mq import Publisher, TaskPublisher
from xbill.settings import xbill_account_publisher, \
    xbill_individual_publisher, make_scrape_request_publisher,\
    utility_provider_publisher
from datetime import datetime

class XBillAccountPublisher(Publisher):

    def __init__(self):
        super(XBillAccountPublisher, self).__init__(xbill_account_publisher)


class XBillIndividualPublisher(Publisher):

    def __init__(self):
        super(XBillIndividualPublisher, self).__init__(
            xbill_individual_publisher)


class MakeScrapeRequestPublisher(TaskPublisher):

    def __init__(self):
        super(MakeScrapeRequestPublisher, self).__init__(
            make_scrape_request_publisher
        )

    def scrape_bills(self, account_guids, utility_guid, username, password,
                     since, force_download=False):
        assert isinstance(since, datetime)
        assert utility_guid is not None
        assert username is not None
        assert password is not None
        assert isinstance(force_download, bool)

        msg = {
            'message_version': [3, 0],
            'account_guids': account_guids,
            'utility_guid': utility_guid,
            'username': username,
            'password': password,
            'since': since.isoformat(),
            'force_download': force_download}
        tasks = self.publish_task(msg)
        return tasks


class UtilityProviderPublisher(Publisher):

    def __init__(self):
        super(UtilityProviderPublisher, self).__init__(
            utility_provider_publisher
        )

    def publish_utility_provider(self, name, guid):
        msg = {
            'message_version': [1, 0],
            'name': name,
            'guid': guid
        }
        self.publish(msg)