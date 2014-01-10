import unittest
import pymongo
import sqlalchemy
import copy
from StringIO import StringIO
from datetime import date, datetime, timedelta
from bson import ObjectId
from billing.util import dateutils
from billing.processing import mongo
from billing.processing.state import StateDB
from billing.processing.state import ReeBill, Customer, UtilBill
import MySQLdb
from billing.test import example_data
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.rate_structure2 import RateStructure, \
        RateStructureItem
from billing.processing.mongo import MongoReebill, NoSuchBillException, IssuedBillError
from billing.processing.session_contextmanager import DBSession
from billing.util.dictutils import subdict

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillTest(TestCaseWithSetup):
    '''Tests for MongoReebill methods.'''
    
    def test_utilbill_periods(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf', utility='washgas',
                    rate_class='DC Non Residential Non Heat')
            self.process.create_first_reebill(session,
                    session.query(UtilBill).one())
            b = self.reebill_dao.load_reebill(acc, 1)

            # function to check that the utility bill matches the reebill's
            # reference to it
            def check():
                # reebill should be loadable
                reebill = self.reebill_dao.load_reebill(acc, 1, version=0)
                # there should be two utilbill documents: the account's
                # template and new one
                all_utilbills = self.reebill_dao.load_utilbills()
                self.assertEquals(2, len(all_utilbills))
                # all its _id fields dates should match the reebill's reference
                # to it
                self.assertEquals(reebill._utilbills[0]['_id'],
                        reebill.reebill_dict['utilbills'][0]['id'])
                
            # this must work because nothing has been changed yet
            check()

            # change utilbill period
            b._get_utilbill_for_service(b.services[0])['start'] = date(2100,
                    1,1)
            b._get_utilbill_for_service(b.services[0])['end'] = date(2100,
                2,1)
            check()
            self.reebill_dao.save_reebill(b)
            check()

            # NOTE account, utility name, service can't be changed, but if they
            # become changeable, do the same test for them

    def test_get_reebill_doc_for_utilbills(self):
        utilbill_template = example_data.get_utilbill_dict('99999',
                utility='washgas', service='gas', start=date(2013,1,1),
                end=date(2013,2,1))
        reebill = MongoReebill.get_reebill_doc_for_utilbills('99999', 1, 0,
                0.5, 0.1, [utilbill_template])
        self.assertEquals('99999', reebill.account)
        self.assertEquals(1, reebill.sequence)
        self.assertEquals(0, reebill.version)
        self.assertEquals(0, reebill.ree_charges)
        self.assertEquals(0, reebill.ree_value)
        self.assertEquals(0.5, reebill.discount_rate)
        self.assertEquals(0.1, reebill.late_charge_rate)
        self.assertEquals(0, reebill.late_charges)
        self.assertEquals(1, len(reebill._utilbills))
        # TODO test utility bill document contents
        self.assertEquals(0, reebill.payment_received)
        self.assertEquals(None, reebill.due_date)
        self.assertEquals(0, reebill.total_adjustment)
        self.assertEquals(0, reebill.ree_savings)
        self.assertEquals(0, reebill.ree_savings)
        self.assertEquals(0, reebill.balance_due)
        self.assertEquals(0, reebill.prior_balance)
        self.assertEquals(0, reebill.balance_forward)

        self.assertEquals({
            "city" : u"Silver Spring",
            "state" : u"MD",
            "addressee" : u"Managing Member Monroe Towers",
            "postal_code" : u"20910",
            "street" : u"3501 13TH ST NW LLC"
        }, reebill.billing_address)
        self.assertEquals({
            "addressee" : u"Monroe Towers",
            "state" : u"DC",
            "city" : u"Washington",
            "street" : u"3501 13TH ST NW #WH",
            "postal_code" : u"20010"
        }, reebill.service_address)

    def test_compute_charges(self):
        uprs = RateStructure(type='UPRS', rates=[
            RateStructureItem(
                rsi_binding='A',
                quantity='REG_TOTAL.quantity',
                rate='2',
            )
        ])
        cprs = RateStructure(type='CPRS', rates=[])
        utilbill_doc = {
            '_id': ObjectId(),
            'account': '12345', 'service': 'gas', 'utility': 'washgas',
            'start': date(2000,1,1), 'end': date(2000,2,1),
            'rate_class': "won't be loaded from the db anyway",
            'chargegroups': {'All Charges': [
                {'rsi_binding': 'A', 'quantity': 0},
            ]},
            'meters': [{
                'present_read_date': date(2000,2,1),
                'prior_read_date': date(2000,1,1),
                'identifier': 'ABCDEF',
                'registers': [{
                    'identifier': 'GHIJKL',
                    'register_binding': 'REG_TOTAL',
                    'quantity': 100,
                    'quantity_units': 'therms',
                }]
            }],
            "billing_address" : {
                "city" : "Columbia",
                "state" : "MD",
                "addressee" : "Equity Mgmt",
                "street" : "8975 Guilford Rd Ste 100",
                "postal_code" : "21046"
            },
            'service_address': {
                "city" : "Columbia",
                "state" : "MD",
                "addressee" : "Equity Mgmt",
                "street" : "8975 Guilford Rd Ste 100",
                "postal_code" : "21046"
            },
        }
        mongo.compute_all_charges(utilbill_doc, uprs, cprs)
        self.assertEqual({'All Charges': [
            {
                'rsi_binding': 'A',
                'quantity': 100,
                'rate': 2,
                'total': 200,
            }
        ]}, utilbill_doc['chargegroups'])

        reebill_doc = MongoReebill.get_reebill_doc_for_utilbills('99999', 1,
                0, 0.5, 0.1, [utilbill_doc])
        utilbill_subdoc = reebill_doc.reebill_dict['utilbills'][0]
        assert all(register['quantity'] == 0 for register in
                utilbill_subdoc['shadow_registers'])

        reebill_doc.compute_charges(uprs, cprs)

        # check that there are the same group names and rsi_bindings and only,
        # by creating two dictionaries mapping group names to sets of
        # rsi_bindings and comparing them
        utilbill_charge_info = {group_name: [subdict(c, ['rsi_binding',
                'description']) for c in charges] for group_name, charges
                in utilbill_doc['chargegroups'].iteritems()}
        reebill_charge_info = {group_name: [subdict(c, ['rsi_binding',
                'description']) for c in charges] for group_name, charges
                in utilbill_subdoc['hypothetical_chargegroups'].iteritems()}
        self.assertEqual(utilbill_charge_info, reebill_charge_info)

        # check reebill charges. since there is no renewable energy,
        # hypothetical charges should be identical to actual charges:
        self.assertEqual({'All Charges': [
            {
                'rsi_binding': 'A',
                'quantity': 100,
                'rate': 2,
                'total': 200,
            }
        ]}, utilbill_subdoc['hypothetical_chargegroups'])

        utilbill_charge_info = {group_name: [subdict(c, ['rsi_binding',
            'description', 'quantity', 'rate', 'total']) for c in charges]
            for  group_name,  charges in
            utilbill_doc['chargegroups'].iteritems()}
        reebill_charge_info = {group_name: [subdict(c, ['rsi_binding',
            'description', 'quantity', 'rate', 'total']) for c in charges]
            for group_name, charges in
            utilbill_subdoc['hypothetical_chargegroups'].iteritems()}
        self.assertEqual(utilbill_charge_info, reebill_charge_info)

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
