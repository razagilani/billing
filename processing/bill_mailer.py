#!/usr/bin/env python
import datetime as dt
import os
import time, argparse, jinja2
import pdb

def bind_template(template_values):
        
    template_plaintext = jinja2.Template("""\
Please find attached your bills for the dates ending {{ bill_dates }}.

The attached file, {{ last_bill }} reflects the current balance and is the only bill that should be paid.

Total Due {{balance_due}}

Best Regards,
Skyline Billing Department
Skyline Innovations

--
SKYLINE INNOVATIONS
Guaranteed Savings Through Green Energy
1606 20th St NW, Second Floor, Washington DC 20009
Phone: (202) 719-5297  Fax: (888) 907-5996
http://www.skylineinnovations.com
""")

    template_html = jinja2.Template("""\

<p>Please find attached your bills for the dates ending {{ bill_dates }}.</p>

<p>The attached file, {{ last_bill }} reflects the current balance and is the only bill that should be paid.

<p>Total Due {{balance_due}}</p>

<p>Best Regards,<br/>
Skyline Billing Department<br/>
Skyline Innovations</p>
<br/>--
<div style="text-align:center">
    <b>SKYLINE INNOVATIONS</b>
</div>
<div style="text-align:center">
    <font color="#33CC00" size="1"><b>Guaranteed Savings Through Green Energy</b></font>
</div>
<div style="text-align:center">
    <font size="1">1606 20th St NW, Second Floor, Washington DC 20009</font>
</div>
<div style="text-align:center">
    <font size="1">Phone: (202) 719-5297  Fax: (888) 907-5996</font>
</div>
<div style="text-align:center">
    <font size="1">
        <a href="http://www.skylineinnovations.com" target="_blank">
            <b>http://www.skylineinnovations.com</b>
        </a>
    </font>
</div>
""")

    return (template_plaintext.render(template_values), template_html.render(template_values))

def mail(recipients, merge_fields, bill_path, bill_files): 
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import mimetypes
    from email import encoders
    from email.message import Message
    from email.mime.audio import MIMEAudio
    from email.mime.base import MIMEBase
    from email.mime.image import MIMEImage

    from_user = config["from"]
    originator = config["originator"]
    password = config["password"]

    # outer container, attachments declare their type
    container = MIMEMultipart()
    container['Subject'] = "Skyline Innovations: Your Monthly Bill for %s" % (merge_fields["sa_street1"])
    container['From'] = from_user
    container['To'] = u', '.join(recipients)

    text, html = bind_template(merge_fields)

    for bill_file in bill_files:
        path = os.path.join(bill_path, bill_file)

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
        attachment.add_header('Content-Disposition', 'attachment', filename=bill_file)
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


    server = smtplib.SMTP(config["smtp_host"], int(config["smtp_port"]))
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(originator, password)
    server.sendmail(originator, recipients, container.as_string())

    if "bcc_list" in config:
        bcc_addrs = config["bcc_list"]
        if bcc_addrs:
            bcc_list = [bcc_addr.strip() for bcc_addr in bcc_addrs.split(",")]
            container['Bcc'] = bcc_addrs
            server.sendmail(originator, bcc_list, container.as_string())

    server.close()

def parse_args(): 
    parser = argparse.ArgumentParser(
        description="Test interface for mailing bills." )

    parser.add_argument("-r", "--recipients", dest="recipients", nargs='+',
                        default="randrews@skylineinnovations.com", 
                        help="Comma separated list of recipients.  Default: %(default)r")

    parser.add_argument("-p", "--path", dest="bill_path", nargs='+',
                        default="/tmp", 
                        help="Path to a bill file.  Default: %(default)r")

    parser.add_argument("-b", "--bill", dest="bill_file", nargs='+',
                        default="1.pdf", 
                        help="Filename of bill pdf.  Default: %(default)r")

    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args() 

    import ConfigParser
    config = ConfigParser.RawConfigParser()
    config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bill_mailer.cfg')
    config.read(config_file_path)

    fields = { "balance_due": "140.00" } 
    mail(args.recipients, fields, args.bill_path, args.bill_file)
