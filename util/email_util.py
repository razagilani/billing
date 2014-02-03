import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mimetypes
from email import encoders
from email.message import Message
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from jinja2 import Template

def send_email(from_user, recipients, subject, originator, password, smtp_host,
        smtp_port, template_html, template_values, attachment_paths=[],
        bcc_addrs=None):
    '''Send email from 'from_user' to 'recipients', titled 'subject', using an
    HTML template 'template_html' populated with values from the dictionary
    'template_values'.
    'originator': email address from which the email is sent
    'attachment_paths': optional list of paths to files to include as
    attachments
    'bcc_addrs': optional comma-separated string of email addresses to BCC.
    '''
    # outer container, attachments declare their type
    container = MIMEMultipart()
    container['Subject'] = subject
    container['From'] = from_user
    container['To'] = u', '.join(recipients)

    html = Template(template_html).render(template_values)

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

    server = smtplib.SMTP(smtp_host, smtp_port)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(originator, password)
    server.sendmail(originator, recipients, container.as_string())

    if bcc_addrs:
        bcc_list = [bcc_addr.strip() for bcc_addr in bcc_addrs.split(",")]
        container['Bcc'] = bcc_addrs
        server.sendmail(originator, bcc_list, container.as_string())

    server.close()

