import email
from unittest import TestCase
from util.email_util import get_attachments


class EmailUtilsTest(TestCase):

    EMAIL_WITH_ATTACHMENT_PATH = 'example_email.txt'
    EMAIL_NO_ATTACHMENT_PATH = 'example_email_no_attachment.txt'

    def setUp(self):
        with open(self.EMAIL_WITH_ATTACHMENT_PATH) as email_file:
            self.message_with_attachment = email.message_from_file(email_file)
        with open(self.EMAIL_NO_ATTACHMENT_PATH) as email_file:
            self.message_no_attachment = email.message_from_file(email_file)

    def test_get_attachments_1(self):
        attachments = get_attachments(self.message_with_attachment)
        self.assertEqual(1, len(attachments))
        name, content = attachments[0]
        self.assertEqual('DailyReportCSV.csv', name)
        self.assertEqual(14768, len(content))

    def test_get_attachments_0(self):
        self.assertEqual(0, len(get_attachments(self.message_no_attachment)))
