#!/usr/bin/env python
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mimetypes
import os
import smtplib
from util.email_util import send_email

#TEMPLATE_FILE_PATH = os.path.join(
#    os.path.dirname(os.path.realpath(__file__)),
#    '..', 'reebill', 'reebill_templates', 'issue_email_template.html')

class Mailer(object):
    '''
    Class for sending out emails
    '''

    def __init__(self, mail_from, originator, password,
                server, host, port, bcc_list=None):
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
        self.host = host
        self.port = port
        self._bcc_list = bcc_list

    def mail(self, recipients, subject, html_body, attachment_contents, display_file_path,
            boundary=None):

        if boundary:
            container = MIMEMultipart(boundary=boundary)
        else:
            container = MIMEMultipart()
        container['Subject'] = subject
        container['From'] = self._mail_from
        container['To'] = recipients

        ctype, encoding = mimetypes.guess_type(display_file_path)
        if ctype is None or encoding is not None:
            # No guess could be made, or the file is encoded (compressed), so
            # use a generic bag-of-bits type.
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        if maintype in ('text', 'image', 'audio'):
            # Note: we should handle calculating the charset
            attachment = MIMEText(attachment_contents, _subtype=subtype)
        else:
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(attachment_contents)
            # Encode the payload using Base64
            encoders.encode_base64(attachment)
        # Set the filename parameter
        attachment.add_header('Content-Disposition', 'attachment',
                filename=display_file_path)
        container.attach(attachment)

        # Record the MIME types of both parts - text/plain and text/html.
        #part1 = MIMEText(text, 'plain')
        # grr... outlook seems to display the plain message first. wtf.
        part2 = MIMEText(html_body, 'html')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        #container.attach(part1)
        # grr... outlook seems to display the plain message first. wtf.
        container.attach(part2)
        self.server.connect(self.host, self.port)

        self.server.ehlo()
        self.server.starttls()
        self.server.ehlo()
        self.server.login(self._originator, self._password)
        self.server.sendmail(self._originator, recipients,
                             container.as_string())

        if self._bcc_list:
            bcc_list = [bcc_addr.strip() for bcc_addr in
                        self._bcc_list.split(",")]
            container['Bcc'] = self._bcc_list
            self.server.sendmail(self._originator, bcc_list,
                                 container.as_string())
        self.server.close()
