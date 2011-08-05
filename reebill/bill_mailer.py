#!/usr/bin/python
import datetime as dt

import time, argparse, jinja2

def bind_email():
        
    template_values = {
        "customer_email":"randrews@skylineinnovations.com",
        "customer_service":"My Location",
        "total_due":"100.00"
        }

    template_plaintext = jinja2.Template("""\
Total Due {{ total_due}}
""")

    template_html = jinja2.Template("""\
<p>Total Due {{ total_due}}</p>
""")

    return (template_plaintext.render(template_values), template_html.render(template_values))

def mail(message, recipients): 
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import mimetypes
    from email import encoders
    from email.message import Message
    from email.mime.audio import MIMEAudio
    from email.mime.base import MIMEBase
    from email.mime.image import MIMEImage

    originator = 'jwatson@skylineinnovations.com'
    password = 'gkjtiNnpv85HhWjKue8w'

    # Create message container - the correct MIME type is multipart/alternative.
    container = MIMEMultipart('alternative')
    container['Subject'] = "Skyline Innovations: Your Monthly Bill for %s" % "[service locations]"
    container['From'] = originator
    container['To'] = recipients

    (text, html) = bind_email()

    path = "/tmp/1.pdf"
    ctype, encoding = mimetypes.guess_type(path)
    print ctype, encoding
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
    attachment.add_header('Content-Disposition', 'attachment', filename="1.pdf")
    container.attach(attachment)

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    container.attach(part1)
    container.attach(part2)

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(originator, password)
    server.sendmail(originator, recipients, container.as_string())
    server.close()

def parse_args(): 
    parser = argparse.ArgumentParser(
        description="Test interface for mailing bills." )

    parser.add_argument("-r", "--recipients", dest="recipients", nargs='+',
                        default=["randrews@skylineinnovations.com"], 
                        help="List of recipients.  Default: %(default)r")

    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args() 

    message = bind_email()
    print message

    mail(message, args.recipients)
