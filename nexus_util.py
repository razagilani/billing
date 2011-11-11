#!/usr/bin/python
import urllib, urllib2
import json
from optparse import OptionParser
#from scripts.nexus import nexus

class NexusUtil(object):

    def __init__(self, host = "nexus"):
        super(NexusUtil,self).__init__()
        self.host = host

    def olap_id(self, bill_account):
        """ For a billing account number, return an olap_id """
        url = "http://%s/nexus_query/lookup?system=billing&systemid=%s&forsystem=olap" % (
            self.host,
            bill_account
        )
        f = urllib2.urlopen(url)
        return f.read()

    def billing_id(self, olap_id):
        '''For an olap id, return a billing account number.'''
        url = "http://%s/nexus_query/lookup?system=olap&systemid=%s&forsystem=billing" % (
            self.host,
            olap_id
        )
        f = urllib2.urlopen(url)
        return f.read()

    def all(self, system, system_id):

        url = "http://%s/nexus_query/lookup_all?system=%s&systemid=%s" % (
            self.host,
            system,
            system_id
        )
        f = urllib2.urlopen(url)
        record = json.load(f)

        if record["total_rows"] > 0:
            return record["rows"][0]
        else:
            return {}

    def fast_all(self, system, system_id):
        '''Same as all(), but looks up the data directly from nexus instead of
        via the HTTP interface.'''
        # TODO: design a solution better than having to depend on another 
        # application.  NexusQuery is a class in another application.
        # see 19355107
        return self.all(system, system_id)

        #
        #result = nexus.NexusQuery().mongo_find({system:system_id})

        # 'result' is normally a list of dictionaries, containing various
        # customer id types and their values for a given customer. it may be
        # empty if the nexus database does not have an id of type 'system' for
        # the customer being looked up (e.g. if 'system' is "billing", and the
        # customer has an "olap" name or "casualname", but not a billing name).
        # fast_all() is only used to display customer names, so returning an
        # empty dict in that situation is OK.
        #if result == []:
        #    return {}
        
        #return result[0]

    def all_ids_for_accounts(self, system, id_objects, key=lambda x:x):
        '''Returns a list of all customer names for all the customers specified
        in the list 'id_objects': an id_object can be just a customer id (as a
        string), or it can be any object from which the function 'key' can
        extract a customer id. ('key' is the identity function by default.)
        Intended to simplify and speed up bill_tool_bridge functions by not
        requiring them to call NexusUtil.all() for each customer
        individually.'''
        result = [self.fast_all(system, key(id_object)) for id_object in id_objects]
        return result

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
        



