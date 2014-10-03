#!/usr/bin/env python
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mimetypes
import os
from jinja2 import Template
from billing.util.email_util import send_email

TEMPLATE_FILE_NAME = 'issue_email_template.html'

class Mailer(object):
    '''
    Class for sending out emails
    '''

    def __init__(self, mail_from, originator, password, template_html,
                server, bcc_list=None):
        '''
        :param mail_from: email address fdrom which emails are sent out
        :param originator: more descriptive email address for use as sender
        :param password: smtp password to connect to smtp_host
        :param template_html: html template used for formatting emails
        :param server: smtplib.SMTP object used for sending email
        :param bcc_list: list of addresses to which email is bcc'ed
        '''
        self._mail_from = mail_from
        self._originator = originator
        self._password = password
        self.server = server
        self._bcc_list = bcc_list
        self.template_html = template_html


    def mail(self, recipients, merge_fields, bill_path, bill_files, boundary=None):
        ''' Wrapper to send_mail method in email_utils that Send email to
        'recipients', using an HTML template 'template_html'
        populated with values from the dictionary 'merge_fields'.
        'bill_paths' and bill_files are used to construct lists of paths
        to files that are included as attachments
        '''
        subject = "Nextility: Your Monthly Bill for %s" % (merge_fields["street"])
        attachment_paths = [os.path.join(bill_path, file_name) for file_name in
                bill_files]
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
            'reebill', 'ui', self.template_html)) as template_file:
            template_html = template_file.read()
            '''send_email(self._mail_from, recipients, subject, self._originator, self._password,
                    self._smtp_host,
                    self._smtp_port, template_html, merge_fields,
                    bcc_addrs=self._bcc_list,
                    attachment_paths=attachment_paths)'''
        if boundary:
            container = MIMEMultipart(boundary=boundary)
        else:
            container = MIMEMultipart()
        container['Subject'] = subject
        container['From'] = self._mail_from
        container['To'] = u', '.join(recipients)
        html = Template(template_html).render(merge_fields)

        for path in attachment_paths:
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None or encoding is not None:
                # No guess could be made, or the file is encoded (compressed), so
                # use a generic bag-of-bits type.
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            if maintype == 'text':
                fp = open(path)
                # Note: we should handle calculating the charset
                attachment = MIMEText(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'image':
                fp = open(path, 'rb')
                attachment = MIMEImage(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'audio':
                fp = open(path, 'rb')
                attachment = MIMEAudio(fp.read(), _subtype=subtype)
                fp.close()
            else:
                fp = open(path, 'rb')
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(fp.read())
                fp.close()
                # Encode the payload using Base64
                encoders.encode_base64(attachment)
            # Set the filename parameter
            attachment.add_header('Content-Disposition', 'attachment',
                    filename=os.path.split(path)[1])
            container.attach(attachment)

        # Record the MIME types of both parts - text/plain and text/html.
        #part1 = MIMEText(text, 'plain')
        # grr... outlook seems to display the plain message first. wtf.
        part2 = MIMEText(html, 'html')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        #container.attach(part1)
        # grr... outlook seems to display the plain message first. wtf.
        container.attach(part2)

        self.server.ehlo()
        self.server.starttls()
        self.server.ehlo()
        self.server.login(self._originator, self._password)
        self.server.sendmail(self._originator, recipients, container.as_string())

        if self._bcc_list:
            bcc_list = [bcc_addr.strip() for bcc_addr in self._bcc_list.split(",")]
            container['Bcc'] = self._bcc_list
            self.server.sendmail(self._originator, bcc_list, container.as_string())

        self.server.close()
