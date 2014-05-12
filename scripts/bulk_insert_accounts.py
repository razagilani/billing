

"""
A quick-and-dirty script to bulk create some customers and upload utility bills
for them.
"""

#from sys import path; path.append('..') #The anti-pattern(!) http://legacy.python.org/dev/peps/pep-3122/
from datetime import date, datetime
from billing.reebill.wsgi import BillToolBridge
from billing.processing.state import UtilBill
from json import loads
from os.path import join
from pdfminer.pdfparser import PDFParser
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from StringIO import StringIO
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfdocument import PDFDocument
import re
import argparse




parser = argparse.ArgumentParser()
parser.add_argument('accounts_json_file', help='The accounts.json data file')
parser.add_argument('pdf_directory', help='The data directory containing the bill pdf files')

parsed = parser.parse_args()

INPUT_FILE = parsed.accounts_json_file
PDFDIR = parsed.pdf_directory

TEMPLATE_ACCOUNT = "10009" #the rebill template account number

BILLING_ADDRESS = {'addressee': 'SANFORD CAPITAL, LLC',
                   'street': '6931 ARLINGTON RD STE 560',
                   'city': 'Bethesda',
                   'state': 'MD',
                   'postal_code': '20814'}

UTILITY = "pepco"


bridge = BillToolBridge()
s = bridge.state_db.session()

def parse_pdf_text(filename):
    
    txt = ""
    
    pdf_file = open(join(PDFDIR, file_name), 'r')
    print pdf_file
    parser = PDFParser(pdf_file)
    document = PDFDocument(parser)
    
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    
    
    device = TextConverter(rsrcmgr, retstr)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    
    for page in PDFPage.create_pages(document):
        interpreter.process_page(page)
        data =  retstr.getvalue()
        txt += data

    return txt


rate_classes = ["Residential-R", "Residential-AE", "Non-Residential-GS ND"]

initial_id = int(bridge.state_db.get_next_account_number(s))

for i, d in enumerate(loads(open(INPUT_FILE, 'r').read())):
    if i < 10: continue
    account = str(i + initial_id)
    print account
    street, rem = d['service_address'].split('\n')
    city, rem = rem.split(',')
    state, pc = rem.split('.')
        
    address = {'addressee': '',
               'street': street.strip(),
               'city': city.strip(),
               'state': state.strip(),
               'postal_code': pc.strip()}

    #returns a customer object; adds customer to the session
    customer = bridge.process.create_new_account(s,
                                      account,   #account is a string here
                                      "%s %s" % (address['street'], d['account_number']), #name
                                      0, #discount rate
                                      0, #late charge rate
                                      BILLING_ADDRESS, #billing_address
                                      address, #service address
                                      TEMPLATE_ACCOUNT)
    print "created customer account %s" % account
    s.flush()

    file_name = "%s-%s.pdf" % (d['account_number'], d['due_date'])



    """Get Rate Class"""
    pdf_txt = parse_pdf_text(file_name)
    rate_class = None
    try:
        rate_class = re.search("\d+(\D+)The present reading", pdf_txt[:pdf_txt.index("is an actual reading")]).group(1).strip()
    except:
        for c in rate_classes:
            idx = pdf_txt.find(c)
            if idx != -1:
                rate_class = c
    
    if not rate_class:
        print "NO RATE CLASS FOUND"
        print pdf_txt
        
        
    
    """Get Begin End Date"""
    begin_date = end_date = None
    try:
        m = re.search("Services for (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d+), (\d+) to (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d+), (\d+)",
                          pdf_txt)
        
        strpd = lambda x, y, z: datetime.strptime("%s %s %s" % (x, y, z), "%b %d %Y").date()
        begin_date = strpd(m.group(1), m.group(2), m.group(3))
        end_date = strpd(m.group(4), m.group(5), m.group(6))
    except AttributeError:
        pass
    
    if not begin_date:
        m = re.search("(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d+), (\d+) to (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d+), (\d+)Service Period",
                          pdf_txt)
        
        strpd = lambda x, y, z: datetime.strptime("%s %s %s" % (x, y, z), "%b %d %Y").date()
        begin_date = strpd(m.group(1), m.group(2), m.group(3))
        end_date = strpd(m.group(4), m.group(5), m.group(6))

    print " parsed begin_date %s end_date %s rate class: %s" % (begin_date, end_date, rate_class)
    
    if begin_date == end_date: 
        print "\nBEGIN DATE SAME AS END DATE!"
        print "DEBUG BEGIN"
        print pdf_txt
        print "\n\n"
        continue 

        
    
            
        
    pdf_file = open(join(PDFDIR, file_name), 'r')
    total = float("".join([c for c in d['balance'] if c.isdigit()]))
    bridge.process.upload_utility_bill(s, 
                                       account, 
                                       'gas',             #service
                                       begin_date,  #begin_date
                                       end_date, #end_date
                                       pdf_file, 
                                       file_name,
                                       total=total,
                                       state=UtilBill.Complete,
                                       utility=UTILITY,
                                       rate_class=rate_class + '_DC_DC_SOS')
    
    print " uploaded utility bill for account %s" % account

s.commit()
print "Transaction Committed."