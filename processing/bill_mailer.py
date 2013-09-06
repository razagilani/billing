#!/usr/bin/env python
import datetime as dt
import os
import time, argparse, jinja2
import pdb
from billing.util.email_util import send_email

TEMPLATE_FILE_NAME = 'issue_email_template.html'

def mail(recipients, merge_fields, bill_path, bill_files): 
    from_user = config["from"]
    originator = config["originator"]
    password = config["password"]

    subject = "Skyline Innovations: Your Monthly Bill for %s" % (merge_fields["street"])

    attachment_paths = [os.path.join(bill_path, file_name) for file_name in
            bill_files]
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
        'reebill', 'ui', TEMPLATE_FILE_NAME)) as template_file:
        template_html = template_file.read()
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
