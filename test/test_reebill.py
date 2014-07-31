import unittest
from datetime import date
import pprint

from bson import ObjectId

from billing.processing.state import ReeBill, Customer, UtilBill, Address
from billing.test.setup_teardown import TestCaseWithSetup
from billing.processing.rate_structure2 import RateStructure, \
        RateStructureItem
from billing.processing.session_contextmanager import DBSession

pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillTest(TestCaseWithSetup):

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
                    group='All Charges',
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

            customer = Customer('someone', '11111', 0.5, 0.1, '',
                                'example@example.com')
            utilbill = UtilBill(customer, UtilBill.Complete, 'gas', 'washgas',
                    'DC Non Residential Non Heat', period_start=date(2000,1,1),
                    period_end=date(2000,2,1), doc_id=str(utilbill_doc['_id']),
                    uprs_id=str(uprs.id), billing_address=Address(),
                    service_address=Address())
            session.add(utilbill)
            utilbill.refresh_charges(uprs.rates)
            reebill = ReeBill(customer, 1, discount_rate=0.5, late_charge_rate=0.1,
                    utilbills=[utilbill])
            session.add(reebill)
            session.flush()
            reebill.update_readings_from_document(utilbill_doc)
            self.assertTrue(all(r.renewable_quantity == 0 for r in
                    reebill.readings))

            self.reebill_dao.save_utilbill(utilbill_doc)
            self.process.compute_utility_bill(utilbill.id)
            self.process.compute_reebill(reebill.customer.account,
                    reebill.sequence, version=reebill.version)

            # check that there are the same group names and rsi_bindings in
            # reebill charges as utility bill charges
            self.assertEqual(
                set((c.rsi_binding, c.description)
                        for c in utilbill.charges),
                set((c.rsi_binding, c.description) for c in reebill.charges)
            )

            self.assertEqual(200, reebill.get_total_hypothetical_charges())

            # check reebill charges. since there is no renewable energy,
            # hypothetical charges should be identical to actual charges:
            self.assertEqual(1, len(reebill.charges))
            c = reebill.charges[0]
            self.assertEqual('A', c.rsi_binding)
            self.assertEqual('a', c.description)
            self.assertEqual(100, c.a_quantity)
            self.assertEqual(100, c.h_quantity)
            self.assertEqual(2, c.a_rate)
            self.assertEqual(2, c.h_rate)
            self.assertEqual(200, c.a_total)
            self.assertEqual(200, c.h_total)
            self.assertEqual('All Charges', c.group)

            self.assertEqual(200, reebill.get_total_hypothetical_charges())

