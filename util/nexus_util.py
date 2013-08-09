#!/usr/bin/env python
import urllib, urllib2
import json
from optparse import OptionParser
import dictutils
#from scripts.nexus import nexus

class NexusUtil(object):

    def __init__(self, host):
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

    def olap_id_from_primus_id(self, address):
        url = "http://%s/nexus_query/lookup?system=primus&systemid=%s&forsystem=olap" % (
            self.host,
            urllib.quote(address)
        )
        f = urllib2.urlopen(url)
        return f.read()

    def primus_id_from_olap_id(self, olapid):
        url = "http://%s/nexus_query/lookup?system=olap&systemid=%s&forsystem=primus" % (
            self.host,
            urllib.quote(olapid)
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
            urllib.quote(system_id)
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

    def all_names_for_accounts(self, accounts, key=lambda x:x):
        '''Given a list of customer accounts (ids in the billing system),
        returns a dictionary mapping each billing account to a dictionary of
        names for each customer in all systems. For example,
        all_names_for_accounts(['1002', '10003']) returns:
        {
            '10002': {
                'billing': '10002',
                'olap': 'penvillage-1},
                casualname: 'Penick Village',
                ...
            },
            '10003': {
                'billing': '10003',
                'olap': 'agni-3501',
                'casualname': 'Monroe Towers',
                ...
            }
        }
        Instead of specifying a list of billing account strings in 'accounts',
        you can specify any object from which the function 'key' can extract a
        billing account string. ('key' is the identity function by default.)
        This is intended to simplify and speed up bill_tool_bridge functions by
        not requiring them to call NexusUtil.all() for each customer
        individually.'''
        return dict([
            (account, self.fast_all('billing', key(account)))
                for account in accounts
        ])

    
    def get_non_billing_customers(self):
        '''Returns a dictionary of 'codename', 'casualname', 'olap' and
        'primus' names for customers that have no billing name or whose billing
        name is an empty string. (If any of those names is missing, it is
        replaced by an empty string.)'''
        url = 'http://%s/nexus_query/all' % self.host
        f = urllib2.urlopen(url)
        response_text = f.read()
        response_data = json.loads(response_text)
        non_billing_rows = [row for row in response_data['rows'] if 'billing'
                not in row or row['billing'] == '']
        result = []
        for row in non_billing_rows:
            result.append(dict([
                (key, row.get(key, ''))
                for key in ['codename', 'casualname', 'olap', 'primus']
            ]))
        return result

class MockNexusUtil(object):
    def __init__(self, customers):
        self._customers = customers

    def _get(self, from_type, name, to_type):
        try:
            customer = next(c for c in self._customers if c[from_type] == name)
        except StopIteration:
            # NOTE real NexusUtil doesn't report errors this way, or at all
            raise ValueError("Couldn't find %s id for %s id '%s'" % (to_type,
                from_type, name))
        return customer[to_type]

    def olap_id(self, bill_account):
        return self._get('billing', bill_account, 'olap')

    def olap_id_from_primus_id(self, address):
        return self._get('primus', bill_account, 'olap')

    def primus_id_from_olap_id(self, olapid):
        return self._get('olap', bill_account, 'primus')

    def billing_id(self, olap_id):
        return self._get('olap', bill_account, 'billing')

    def all(self, system, system_id):
        customer = next(c for c in self._customers if c[system] == name)
        return customer

    def fast_all(self, system, system_id):
        return self.all(system, system_id)

    def all_names_for_accounts(self, accounts, key=lambda x:x):
        return dict([
            (account, self.fast_all('billing', key(account)))
                for account in accounts
        ])

    def get_non_billing_customers(self):
        # TODO maybe put in some fake customer names
        return {}

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
