#!/usr/bin/env python
import datetime as dt
import os
import time, argparse, jinja2
import pdb
from billing.util.email_util import send_email

template_plaintext = """\
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
"""

template_html = """\

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
"""

def mail(recipients, merge_fields, bill_path, bill_files): 
    from_user = config["from"]
    originator = config["originator"]
    password = config["password"]

    subject = "Skyline Innovations: Your Monthly Bill for %s" % (merge_fields["street"])

    attachment_paths = [os.path.join(bill_path, file_name) for file_name in
            bill_files]
    send_email(from_user, recipients, subject, originator, password, config['smtp_host'],
            config['smtp_port'], template_html, merge_fields,
            bcc_addrs=config.get("bcc_list"),
            attachment_paths=attachment_paths)


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
