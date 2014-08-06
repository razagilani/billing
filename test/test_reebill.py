import unittest
from datetime import date

from bson import ObjectId
from mock import Mock

from billing.processing.state import ReeBill, Customer, UtilBill, Address, \
    Charge
from billing.processing.rate_structure2 import RateStructure, \
        RateStructureItem
from processing.mongo import ReebillDAO


class ReebillTest(unittest.TestCase):

    def setUp(self):
        self.mock_rbd = Mock(autospec=ReebillDAO)

    def test_compute_charges(self):
        customer = Customer('someone', '11111', 0.5, 0.1, '',
            'example@example.com')

        uprs = RateStructure(rates=[RateStructureItem(
            rsi_binding='A',
            description='a',
            quantity='REG_TOTAL.quantity',
            rate='2',
            group='All Charges',
        )])

        # only fields that are actually used are included in this document
        utilbill_doc = {
            'meters': [{
                'registers': [{
                    'register_binding': 'REG_TOTAL',
                    'quantity': 100,
                    'quantity_units': 'therms',
                }]
            }],
        }

        utilbill = UtilBill(customer, UtilBill.Complete, 'gas', 'washgas',
                'DC Non Residential Non Heat', period_start=date(2000,1,1),
                period_end=date(2000,2,1), uprs_id=str(uprs.id),
                billing_address=Address(), service_address=Address())
        utilbill.charges = [Charge(utilbill, 'a', 'All Charges', 0, 'therms',
                0,'A', 0)]

        reebill = ReeBill(customer, 1, discount_rate=0.5, late_charge_rate=0.1,
                utilbills=[utilbill])

        reebill.update_readings_from_document(utilbill_doc)
        self.assertEqual(1, len(reebill.readings))
        reading = reebill.readings[0]
        self.assertEqual(100, reading.conventional_quantity)
        self.assertEqual(0, reading.renewable_quantity)

        self.mock_rbd.load_doc_for_utilbill.return_value = utilbill_doc
        reebill.compute_charges(uprs, self.mock_rbd)

        # check that there are the same group names and rsi_bindings in
        # reebill charges as utility bill charges
        self.assertEqual(
            set((c.rsi_binding, c.description) for c in utilbill.charges),
            set((c.rsi_binding, c.description) for c in reebill.charges)
        )

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

