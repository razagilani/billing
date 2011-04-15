#!/usr/bin/python

import urllib, urllib2
import json

from optparse import OptionParser

class NexusUtil(object):

    def __init__(self, host = "nexus"):
        super(NexusUtil,self).__init__()
        self.host = host

    def olap_id(self, bill_account):
        """ For a billing account number, return an olap_id """

        url = "http://%s/nexus_rest/lookup?system=billing&systemid=%s&forsystem=olap" % (
            self.host,
            bill_account
        )

        f = urllib2.urlopen(url)

        return f.read()

    def all(self, system, system_id):
        """ For a billing account number, return an olap_id """
        #http://nexus/nexus_rest/lookup_all?system=billing&systemid=10001

        url = "http://%s/nexus_rest/lookup_all?system=%s&systemid=%s" % (
            self.host,
            system,
            system_id
        )
        f = urllib2.urlopen(url)

        record = json.load(f)
        return record["rows"][0]

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("--host", dest="host", help="Host where Nexus ReSTful service may be found.")

    parser.add_option("--billaccount", dest="billaccount", help="Account number for Billing System")
    parser.add_option("--system", dest="system", help="Name of the system to be queried")
    parser.add_option("--systemid", dest="systemid", help="Identifier of the system to be queried")

    (options, args) = parser.parse_args()

    if (options.billaccount):
        print NexusUtil(options.host).olap_id(options.billaccount)
        exit()

    if (options.system and options.systemid):
        print NexusUtil(options.host).all(options.system, options.systemid)
        exit()
        



