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
    # TODO make this a real unit test (it should not inherit from
    # TestCaseWithSetup and should not use the database)

    def test_utilbill_periods(self):
        acc = '99999'
        with DBSession(self.state_db) as session:
            self.process.upload_utility_bill(session, acc, 'gas',
                    date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                    'january.pdf', utility='washgas',
                    rate_class='DC Non Residential Non Heat')
            self.process.roll_reebill(session, acc, start_date=date(2013,1,1))
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
            b._utilbills[0]['start'] = date(2100,1,1)
            b._utilbills[0]['start'] = date(2100,2,1)
            check()
            self.reebill_dao.save_reebill(b)
            self.reebill_dao.save_utilbill(b._utilbills[0])
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
        # self.assertEquals(0, reebill.ree_charge)
        # self.assertEquals(0, reebill.ree_value)
        # self.assertEquals(0.5, reebill.discount_rate)
        # self.assertEquals(0.1, reebill.late_charge_rate)
        # self.assertEquals(0, reebill.late_charge)
        self.assertEquals(1, len(reebill._utilbills))
        # TODO test utility bill document contents
        # self.assertEquals(0, reebill.payment_received)
        # self.assertEquals(None, reebill.due_date)
        # self.assertEquals(0, reebill.total_adjustment)
        # self.assertEquals(0, reebill.ree_savings)
        # self.assertEquals(0, reebill.balance_due)
        # self.assertEquals(0, reebill.prior_balance)
        # self.assertEquals(0, reebill.balance_forward)

    def test_compute_charges(self):
        with DBSession(self.state_db) as session:
            # TODO make this a real unit test when possible (when utility bill
            # charges are no longer in Mongo so Process.compute_reebill doesn't
            # need to load and save utility bill documents and
            # Process._compute_reebill_charges becomes state.ReeBill
            # .compute_charges)
            uprs = RateStructure(rates=[
                RateStructureItem(
                    rsi_binding='A',
                    description='a',
                    quantity='REG_TOTAL.quantity',
                    rate='2',
                )
            ])
            uprs.save()
            utilbill_doc = {
                '_id': ObjectId(),
                'account': '12345', 'service': 'gas', 'utility': 'washgas',
                'start': date(2000,1,1), 'end': date(2000,2,1),
                'rate_class': "won't be loaded from the db anyway",
                'charges': [
                    {'rsi_binding': 'A', 'quantity': 0, 'group': 'All Charges'},
                ],
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
            mongo.compute_all_charges(utilbill_doc, uprs)
            self.assertEqual([
                {
                    'rsi_binding': 'A',
                    'description': 'a',
                    'quantity': 100,
                    'rate': 2,
                    'total': 200,
                    'group': 'All Charges',
                }
            ], utilbill_doc['charges'])

            customer = Customer('someone', '11111', 0.5, 0.1, '',
                                'example@example.com')
            utilbill = UtilBill(customer, UtilBill.Complete, 'gas', 'washgas',
                    'DC Non Residential Non Heat', period_start=date(2000,1,1),
                    period_end=date(2000,2,1), doc_id=str(utilbill_doc['_id']),
                    uprs_id=str(uprs.id))
            reebill = ReeBill(customer, 1, discount_rate=0.5, late_charge_rate=0.1,
                    utilbills=[utilbill])
            session.add(reebill)
            reebill.update_readings_from_document(session, utilbill_doc)
            reebill_doc = MongoReebill.get_reebill_doc_for_utilbills('11111', 1,
                    0, 0.5, 0.1, [utilbill_doc])
            utilbill_subdoc = reebill_doc.reebill_dict['utilbills'][0]
            assert all(register['quantity'] == 0 for register in
                    utilbill_subdoc['shadow_registers'])

            self.reebill_dao.save_utilbill(utilbill_doc)
            self.reebill_dao.save_reebill(reebill_doc)
            self.reebill_dao.save_utilbill(reebill_doc._utilbills[0])

            #reebill_doc.compute_charges(uprs)
            #self.process._compute_reebill_charges(session, reebill, uprs)
            self.process.compute_utility_bill(session, utilbill.id)
            self.process.compute_reebill(session, reebill.customer.account,
                    reebill.sequence, version=reebill.version)

            # check that there are the same group names and rsi_bindings and only,
            # by creating two dictionaries mapping group names to sets of
            # rsi_bindings and comparing them
            self.assertEqual(subdict(utilbill_doc['charges'],
                    ['rsi_binding, description']),
                    subdict(utilbill_subdoc['hypothetical_charges'],
                    ['rsi_binding, description']))

            self.assertEqual(200, reebill.get_total_hypothetical_charges())

            # check reebill charges. since there is no renewable energy,
            # hypothetical charges should be identical to actual charges:
            self.assertEqual([{
                'rsi_binding': 'A',
                'description': 'a',
                'quantity': 100,
                'rate': 2,
                'total': 200,
                'group': 'All Charges',
            }], utilbill_subdoc['hypothetical_charges'])

            self.assertEqual(subdict(utilbill_doc['charges'],
                    ['rsi_binding, description', 'quantity', 'rate', 'total']),
                    subdict(utilbill_subdoc['hypothetical_charges'],
                    ['rsi_binding, description', 'quantity', 'rate', 'total']))

            self.assertEqual(200, reebill.get_total_hypothetical_charges())

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
