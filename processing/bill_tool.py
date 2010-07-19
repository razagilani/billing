#!/usr/bin/python
"""
File: bill_tool.py
Description: Various utility procedures to process bills
Usage: See command line synopsis
"""

#
# runtime support
#
import sys
import os  
from optparse import OptionParser

from urlparse import urlparse

# for xml processing
import amara
from amara import bindery

#
# Globals
#
user=None
password=None

class BillTool():
    """ Class with a variety of utility procedures for processing bills """
    
    def __init__(self):
        pass

    def roll_bill(self, prevbill, nextbill, amountPaid):
        # Bind to XML bill
        dom = bindery.parse(prevbill)
         
        # roll the bill

        xml = dom.xml_encode()

        # determine URI scheme
        parts = urlparse(nextbill)

        # nice then to factor out and put into a common lib
        if (parts.scheme == 'http'): 
            # http scheme URL, PUT to eXistDB

            con = httplib.HTTP(parts.netloc)
            con.putrequest('PUT', '%s' % nextbill)
            con.putheader('Content-Type', 'text/xml')

            if (user and password):
                auth = 'Basic ' + string.strip(base64.encodestring(user + ':' + password))
                con.putheader('Authorization', auth )

            clen = len(xml) 
            con.putheader('Content-Length', `clen`)
            con.endheaders() 
            con.send(xml)
        else:
            # if not http specifier, assume just a plain filename was passed in.
            billFile = open(nextbill, "w")
            billFile.write(xml)
            billFile.close()

def main(options):
    """
    """
    pass

if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-p", "--prevbill", dest="prevbill", help="Previous bill to be rolled", metavar="FILE")
    parser.add_option("-n", "--nextbill", dest="nextbill", help="Next bill to be targeted", metavar="FILE")
    parser.add_option("-u", "--user", dest="user", default='prod', help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password", help="Bill database user account name.")

    (options, args) = parser.parse_args()

    if (options.prevbill == None):
        print "Previous bill must be specified."
        exit()

    if (options.nextbill == None):
        print "Next bill must be specified"
        exit()

    username=options.user
    password=options.password
