#!/usr/bin/env python
import os
from billing.util.email_util import send_email

TEMPLATE_FILE_NAME = 'issue_email_template.html'

class Mailer(object):
    '''
    Class for sending out emails
    '''
    def __init__(self, mail_from, originator, password, template_html, smtp_host, smtp_port=587, bcc_list=None):
        '''
        :param mail_from: email address fdrom which emails are sent out
        :param originator: more descriptive email address for use as sender
        :param password: smtp password to connect to smtp_host
        :param template_html: html template used for formatting emails
        :param smtp_host: address of smtp_host
        :param smtp_port: port on which smtp_server is running
        :param bcc_list: list of addresses to which email is bcc'ed
        '''
        self._mail_from = mail_from
        self._originator = originator
        self._password = password
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._bcc_list = bcc_list
        self.template_html = template_html

    def mail(self, recipients, merge_fields, bill_path, bill_files):
        ''' Wrapper to send_mail method in email_utils that Send email to
        'recipients', using an HTML template 'template_html'
        populated with values from the dictionary 'merge_fields'.
        'bill_paths' and bill_files aed to construct lists of paths
        to files that are included as attachments
        '''
        subject = "Nextility: Your Monthly Bill for %s" % (merge_fields["street"])
        attachment_paths = [os.path.join(bill_path, file_name) for file_name in
                bill_files]
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
            'reebill', 'ui', self.template_html)) as template_file:
            template_html = template_file.read()
            send_email(self._mail_from, recipients, subject, self._originator, self._password,
                    self._smtp_host,
                    self._smtp_port, template_html, merge_fields,
                    bcc_addrs=self._bcc_list,
                    attachment_paths=attachment_paths)
