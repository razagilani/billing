#!/usr/bin/env python
import os
from billing.util.email_util import send_email

TEMPLATE_FILE_NAME = 'issue_email_template.html'

class Mailer(object):
    def __init__(self, config_dict):
        self._config_dict = config_dict

    def mail(self, recipients, merge_fields, bill_path, bill_files):
        from_user = self._config_dict["mail_from"]
        originator = self._config_dict["originator"]
        password = self._config_dict["password"]
        subject = "Nextility: Your Monthly Bill for %s" % (merge_fields["street"])
        attachment_paths = [os.path.join(bill_path, file_name) for file_name in
                bill_files]
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
            'reebill', 'ui', TEMPLATE_FILE_NAME)) as template_file:
            template_html = template_file.read()
            send_email(from_user, recipients, subject, originator, password,
                    self._config_dict['smtp_host'],
                    self._config_dict['smtp_port'], template_html, merge_fields,
                    bcc_addrs=self._config_dict.get("bcc_list"),
                    attachment_paths=attachment_paths)
