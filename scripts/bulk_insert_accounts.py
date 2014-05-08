

"""
A quick-and-dirty script to bulk insert some new accounts into reebill.
"""
#from sys import path; path.append('..') #The anti-pattern(!) http://legacy.python.org/dev/peps/pep-3122/
from datetime import date
from billing.reebill.wsgi import BillToolBridge
from billing.processing.state import UtilBill
from json import loads
from os.path import join

INPUT_FILE = "accounts.json"
PDFDIR = "/Users/mnaber/Dropbox/skyline-etl/Acquisitor/sanford"
TEMPLATE_ACCOUNT = "" #the rebill template account number
INITIAL_ID = 120000
BILLING_ADDRESS = {'addressee': '',
                   'street': '123 billingstreet',
                   'city': 'billingcity',
                   'state': 'XX',
                   'postal_code': '44444'}
UTILITY = ""
RATE_CLASS = ""


bridge = BillToolBridge()
session = bridge.state_db.session()

for i, d in enumerate(loads(open(INPUT_FILE, 'r').read())):
    account = i + INITIAL_ID

    street, rem = d['service_address'].split('\n')
    city, rem = rem.split(',')
    state, pc = rem.split('.')
    
    
    address = {'addressee': '',
               'street': street.strip(),
               'city': city.strip(),
               'state': state.strip(),
               'postal_code': pc.strip()}

    bridge.process.create_new_account(session,
                                      account,   #account
                                      "%s %s" % (d['service_address'], d['account_number']), #name
                                      0, #discount rate
                                      0, #late charge rate
                                      BILLING_ADDRESS, #billing_address
                                      address, #service address
                                      TEMPLATE_ACCOUNT)

    file_name = "%s-%s.pdf" % (d['account_number'], d['due_date'])
    pdf_file = open(join(PDFDIR, file_name), 'r')

    total = float("".join([c for c in d['balance'] if c.isdigit()]))

    bridge.process.upload_utility_bill(session, 
                                       account, 
                                       'gas',             #service
                                       date(1900, 1, 1),  #begin_date
                                       date(1900, 1, 31), #end_date
                                       pdf_file, 
                                       file_name,
                                       total=total,
                                       state=UtilBill.Complete,
                                       utility=UTILITY,
                                       rate_class=RATE_CLASS)
    
session.commit()