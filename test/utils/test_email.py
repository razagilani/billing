import email
from unittest import TestCase
from util.email_util import get_attachments


class EmailUtilsTest(TestCase):

    EMAIL_FILE_PATH = 'example_email.txt'

    def setUp(self):
        with open(self.EMAIL_FILE_PATH) as email_file:
            #self.email_text = email_file.read()
            #self.message = email.message_from_string(self.email_text)
            self.message = email.message_from_file(email_file)

    def test_get_attachments(self):
        name, content = get_attachments(self.message)[0]
        self.assertEqual('DailyReportCSV.csv', name)
        self.assertEqual(14768, len(content))

