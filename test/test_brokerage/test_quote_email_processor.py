from unittest import TestCase


class EmailUtilsTest(TestCase):

    EMAIL_FILE_PATH = None # TODO

    def setUp(self):
        self.email_file = open(self.EMAIL_FILE_PATH)

    def tearDown(self):
        self.email_file.close()

    def test_process_email(self):
        pass # TODO
