import unittest
from StringIO import StringIO
from datetime import date, datetime, timedelta
import pprint

import os
from sqlalchemy.orm.exc import NoResultFound
from os.path import realpath, join, dirname
from datetime import date, datetime, timedelta
import pprint
import os

#from billing.processing.rate_structure2 import RateStructureItem
from billing.processing.process import IssuedBillError
from billing.processing.state import ReeBill, Customer, UtilBill, Reading, Address, Customer, Charge
from os.path import realpath, join, dirname

from sqlalchemy.orm.exc import NoResultFound
from processing.state import ReeBillCharge

from skyliner.sky_handlers import cross_range
#from billing.processing.rate_structure2 import RateStructureItem
from billing.processing.process import IssuedBillError
from billing.processing.state import ReeBill, Customer, UtilBill
from billing.test.setup_teardown import TestCaseWithSetup
from billing.test import example_data
from billing.processing.mongo import NoSuchBillException
from billing.processing.exceptions import BillStateError, NoRSIError, RSIError,\
    FormulaSyntaxError
from billing.test import utils


pp = pprint.PrettyPrinter(indent=1).pprint
pformat = pprint.PrettyPrinter(indent=1).pformat

# TODO: move this into TestProcess.setUp and use it in every test
class MockReeGetter(object):
    def __init__(self, quantity):
        self.quantity = quantity

    def update_renewable_readings(self, olap_id, reebill,
                                  use_olap=True, verbose=False):
        for reading in reebill.readings:
            reading.renewable_quantity = self.quantity


class ProcessTest(TestCaseWithSetup, utils.TestCase):

    def setup_dummy_utilbill_calc_charges(self, acc, begin_date, end_date):
        """Upload a dummy-utilbill, add an RSI, and calculate charges
        """
        utilbill = self.process.upload_utility_bill(acc,
                                                    'gas', begin_date, end_date,
                                                    StringIO('a utility bill'),
                                                    'filename.pdf')
        self.process.add_rsi(utilbill.id)
        self.process.update_rsi(utilbill.id, 'New RSI #1', {
            'rsi_binding': 'A',
            'quantity': 'REG_TOTAL.quantity',
            'rate': '1'
        })
        self.process.refresh_charges(utilbill.id)  #creates charges
        self.process.compute_utility_bill(utilbill.id)  #updates charge values


    def test_create_new_account(self):
        billing_address = {
            'addressee': 'Andrew Mellon',
            'street': '1785 Massachusetts Ave. NW',
            'city': 'Washington',
            'state': 'DC',
            'postal_code': '20036',
        }
        service_address = {
            'addressee': 'Skyline Innovations',
            'street': '1606 20th St. NW',
            'city': 'Washington',
            'state': 'DC',
            'postal_code': '20009',
        }
        # Create new account "88888" based on template account "99999",
        # which was created in setUp
        self.process.create_new_account('88888', 'New Account',
                                            0.6, 0.2, billing_address,
                                            service_address, '100000')

            # Disabled this test for now since it bypasses the process object
            # customer = self.state_db.get_customer(session, '88888')
            # self.assertEquals('88888', customer.account)
            # self.assertEquals(0.6, customer.get_discount_rate())
            # self.assertEquals(0.2, customer.get_late_charge_rate())
            # template_customer = self.state_db.get_customer(session, '99999')
            # self.assertNotEqual(template_customer.utilbill_template_id,
            #                     customer.utilbill_template_id)

        # No Reebills or Utility Bills should exist
        self.assertEqual([], self.process.get_reebill_metadata_json(
                '88888'))
        self.assertEqual(([], 0), self.process.get_all_utilbills_json(
                '88888', 0, 30))

        # Upload a utility bill and check it persists and fetches
        self.process.upload_utility_bill('88888', 'gas',
                                         date(2013, 1, 1), date(2013, 2, 1),
                                         StringIO('January 2013'),
                                         'january.pdf')
        utilbills_data = self.process.get_all_utilbills_json('88888',
                                                             0, 30)[0]

        self.assertEqual(1, len(utilbills_data))
        utilbill_data = utilbills_data[0]
        self.assertDocumentsEqualExceptKeys({'state': 'Final',
                                             'service': 'Gas',
                                             'utility': 'washgas',
                                             'rate_class': 'DC Non Residential Non Heat',
                                             'period_start': date(2013, 1,
                                                                  1),
                                             'period_end': date(2013, 2,
                                                                1),
                                             'total_charges': 0.0,
                                             'computed_total': 0,
                                             # 'date_received': datetime.utcnow().date(),
                                             'processed': 0,
                                             'account': '88888',
                                             'editable': True,
                                                 'name': '88888 - Example 2/1786 Massachusetts Ave. - Test Utility Company Template: Test Rate Class Template',
                                             'reebills': [],
                                            }, utilbill_data, 'id', 'charges', 'reebills')


        self.process.add_rsi(utilbill_data['id'])
        self.process.update_rsi(utilbill_data['id'],
                'New RSI #1', {'quantity': 'REG_TOTAL.quantity',
                'rate': '1', 'rsi_binding': 'A', 'description':'a'})
        self.process.refresh_charges(utilbill_data['id'])

        self.process.ree_getter = MockReeGetter(10)
        self.process.roll_reebill('88888', start_date=date(2013, 1, 1))

        ubdata = self.process.get_all_utilbills_json('88888', 0, 30)[0][0]
        self.assertDocumentsEqualExceptKeys({
            'account': '88888',
            'computed_total': 0,
            'editable': True,
            'id': 6469L,
            'name': ('88888 - Example 2/1786 Massachusetts Ave. - '
                     'washgas: DC Non Residential Non Heat'),
            'period_end': date(2013, 2, 1),
            'period_start': date(2013, 1, 1),
            'processed': 0,
            'rate_class': 'DC Non Residential Non Heat',
            'reebills': [{'issue_date': None, 'sequence': 1,
                    'version': 0L}],
            'service': 'Gas',
            'state': 'Final',
            'total_charges': 0.0,
            'utility': 'washgas',
        }, ubdata, 'id', 'charges')

        reebill_data = self.process.get_reebill_metadata_json('88888')
        self.assertEqual([{
            'id': 1,
            'sequence': 1,
            'max_version': 0,
            'issued': False,
            'issue_date': None,
            'actual_total': 0.,
            'hypothetical_total': 10,
            'payment_received': 0.,
            'period_start': date(2013, 1, 1),
            'period_end': date(2013, 2, 1),
            'prior_balance': 0.,
            'processed': False,
            'ree_charges': 4.,
            'ree_value': 10.,
            'services': [],
            'total_adjustment': 0.,
            'total_error': 0.,
            'ree_quantity': 10.,
            'balance_due': 4.,
            'balance_forward': 0.,
            'corrections': '(never issued)',
        }], reebill_data)

        reebill_charges = self.process.get_hypothetical_matched_charges(
                '88888', 1)
        self.assertEqual([{
            'actual_quantity': 0,
            'actual_rate': 1,
            'actual_total': 0,
            'description': 'a',
            'quantity': 10,
            'quantity_units': '',
            'rate': 1,
            'rsi_binding': 'A',
            'total': 10,
        }], reebill_charges)

        # TODO: fields not checked above that should be checked some other
        # way:
        # email recipient
        # utilbills
        # ree_charge
        # ree_savings
        # late_charges
        # ree_value
        # late_charge_rate
        # discount_rate
        # payment_received
        # total_adjustment
        # billing_address
        # service_address

        # nothing should exist for account 99999
        # (this checks for bug #70032354 in which query for
        # get_reebill_metadata_json includes bills from all accounts)
        self.assertEqual(([], 0), self.process.get_all_utilbills_json(
                '99999', 0, 30))
        self.assertEqual([], self.process.get_reebill_metadata_json(
                '99999'))

        # it should not be possible to create an account that already
        # exists
        self.assertRaises(ValueError, self.process.create_new_account,
                '88888', 'New Account', 0.6, 0.2,
                billing_address, service_address, '99999')

        # try creating another account when the template account has no
        # utility bills yet
        self.process.create_new_account('77777', 'New Account',
                0.6, 0.2, billing_address, service_address, '88888')
        self.process.create_new_account('66666', 'New Account',
                0.6, 0.2, billing_address, service_address, '88888')

        # Try rolling a reebill for a new account that has no utility bills uploaded yet
        self.assertRaises(NoResultFound, self.process.roll_reebill,
                '777777', start_date=date(2013, 2, 1))

    def test_update_utilbill_metadata(self):
        utilbill = self.process.upload_utility_bill('99999',
                                                    'Gas', date(2013, 1, 1),
                                                    date(2013, 2, 1),
                                                    StringIO(
                                                        'January 2013'),
                                                    'january.pdf',
                                                    total=100)

        doc = self.process.get_all_utilbills_json('99999', 0, 30)[0][0]
        assert utilbill.period_start == doc['period_start'] == date(2013, 1,
                                                                    1)
        assert utilbill.period_end == doc['period_end'] == date(2013, 2, 1)
        assert utilbill.service == doc['service'] == 'Gas'
        assert utilbill.utility == doc['utility'] == 'Test Utility Company Template'
        assert utilbill.total_charges == 100
        assert utilbill.rate_class == doc['rate_class'] == 'Test Rate Class Template'

        # invalid date ranges
        self.assertRaises(ValueError,
                          self.process.update_utilbill_metadata,
                          utilbill.id, period_start=date(2014, 1, 1))
        self.assertRaises(ValueError,
                          self.process.update_utilbill_metadata,
                          utilbill.id, period_end=date(2012, 1, 1))
        self.assertRaises(ValueError,
                          self.process.update_utilbill_metadata,
                          utilbill.id, period_end=date(2014, 2, 1))

        # change start date
        # TODO: this fails to actually move the file because
        # get_utilbill_file_path, called by move_utilbill, is using the
        # UtilBill object, whose date attributes have not been updated
        # yet. it should start passing when the file's old path and the
        # new it's path are the same.
        self.process.update_utilbill_metadata(utilbill.id,
                                              period_start=date(2013, 1, 2))
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual(date(2013, 1, 2), utilbill.period_start)
        self.assertEqual(date(2013, 1, 2), doc['start'])
        for meter in doc['meters']:
            self.assertEqual(date(2013, 1, 2), meter['prior_read_date'])
        # check that file really exists at the expected path
        # (get_utilbill_file_path also checks for existence)
        bill_file_path = self.billupload.get_utilbill_file_path(utilbill)

        # change end date
        self.process.update_utilbill_metadata(utilbill.id,
                                              period_end=date(2013, 2, 2))
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual(date(2013, 2, 2), utilbill.period_end)
        self.assertEqual(date(2013, 2, 2), doc['end'])
        for meter in doc['meters']:
            self.assertEqual(date(2013, 2, 2), meter['present_read_date'])

        # change service
        self.process.update_utilbill_metadata(utilbill.id,
                                              service='electricity')
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual('electricity', utilbill.service)
        self.assertEqual('electricity', doc['service'])

        # change "total" aka "total_charges"
        self.process.update_utilbill_metadata(utilbill.id,
                                              total_charges=200)
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual(200, utilbill.total_charges)
        # NOTE "total" is not in utility bill Mongo documents, only MySQL

        # change utility name
        self.process.update_utilbill_metadata(utilbill.id,
                                              utility='BGE')
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual('BGE', utilbill.utility)
        self.assertEqual('BGE', doc['utility'])

        # change rate class
        self.process.update_utilbill_metadata(utilbill.id,
                                              rate_class='something else')
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual('something else', utilbill.rate_class)
        self.assertEqual('something else', doc['rate_class'])

        # change processed state
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual(False, utilbill.processed)
        self.process.update_utilbill_metadata(utilbill.id, processed=True)
        doc = self.process.get_utilbill_doc(utilbill.id)
        self.assertEqual(True, utilbill.processed)

        # even when the utility bill is attached to an issued reebill, only
        # the editable document gets changed
        reebill = self.process.roll_reebill('99999',
                                            start_date=date(2013, 1, 1))
        self.process.issue('99999', 1)
        self.process.update_utilbill_metadata(utilbill.id, service='water')
        editable_doc = self.process.get_utilbill_doc(utilbill.id)
        frozen_doc = self.process.get_utilbill_doc(utilbill.id,
                                                   reebill_sequence=reebill.sequence,
                                                   reebill_version=reebill.version)
        assert 'sequence' not in editable_doc and 'version' not in editable_doc
        assert frozen_doc['sequence'] == 1 and frozen_doc['version'] == 0
        self.assertNotEqual(editable_doc, frozen_doc)
        self.assertEqual('electricity', frozen_doc['service'])
        self.assertEqual('water', utilbill.service)
        self.assertEqual('water', editable_doc['service'])


    def test_get_late_charge(self):
        '''Tests computation of late charges.
        '''
        # TODO: when possible, convert this into a unit test that checks the
        # get_late_charge method, whatever class it may belong to by then
        # (ReeBill?). See 69883814.
        acc = '99999'
        # create utility bill with a charge in it
        u = self.process.upload_utility_bill(acc, 'gas',
                date(2000, 1, 1), date(2000, 2, 1),
                StringIO('January 2000'), 'january.pdf')
        self.process.add_rsi(u.id)
        self.process.update_rsi(u.id, 'New RSI #1', {
            'rsi_binding': 'THE_CHARGE',
            'quantity': 'REG_TOTAL.quantity',
            'quantity_units': 'therms',
            'rate': '1',
            'group': 'All Charges',
        })
        self.process.refresh_charges(u.id)
        self.process.update_utilbill_metadata(u.id, processed=True)

        # create first reebill
        bill1 = self.process.roll_reebill(acc, start_date=date(2000, 1, 1))
        self.process.update_sequential_account_info(acc, 1,
                discount_rate=.5, late_charge_rate=.34)
        self.process.ree_getter=MockReeGetter(100)
        self.process.bind_renewable_energy(acc, 1)
        self.process.compute_reebill(acc, 1)
        self.assertEqual(0, self.process.get_late_charge(bill1,
                date(1999, 12, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                date(2000, 1, 1)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                date(2000, 1, 2)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                date(2000, 2, 1)))
        self.assertEqual(0, self.process.get_late_charge(bill1,
                date(2000, 2, 2)))

        # issue first reebill, so a later bill can have a late charge
        # based on the customer's failure to pay bill1 by its due date,
        # i.e. 30 days after the issue date.
        self.process.issue(acc, bill1.sequence,
                issue_date=date(2000, 4, 1))
        self.assertEqual(date(2000, 5, 1), bill1.due_date)
        self.assertEqual(50, bill1.balance_due)

        # create 2nd utility bill and reebill
        u2 = self.process.upload_utility_bill(acc, 'gas',
                date(2000, 2, 1), date(2000, 3, 1),
                StringIO('February 2000'), 'february.pdf')
        self.process.update_utilbill_metadata(u2.id, processed=True)
        bill2 = self.process.roll_reebill(acc)
        self.process.update_sequential_account_info(acc, 2,
                discount_rate=.5, late_charge_rate=.34)
        self.process.ree_getter = MockReeGetter(200)
        self.process.bind_renewable_energy(acc, 2)
        self.process.compute_reebill(acc, 2)
        assert bill2.discount_rate == 0.5
        assert bill2.ree_charge == 100

        # bill2's late charge should be 0 before bill1's due date; on/after
        # the due date, it's balance * late charge rate, i.e.
        # 50 * .34 = 17
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(1999, 12, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2000, 1, 2)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2000, 3, 31)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2000, 4, 1)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2000, 4, 2)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2000, 4, 30)))
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2000, 5, 1)))
        self.assertEqual(17, self.process.get_late_charge(bill2,
                date(2000, 5, 2)))
        self.assertEqual(17, self.process.get_late_charge(bill2,
                date(2013, 1, 1)))

        # in order to get late charge of a 3rd bill, bill2 must be computed
        self.process.compute_reebill(acc, 2)

        # create a 3rd bill without issuing bill2. bill3 should have None
        # as its late charge for all dates
        self.process.upload_utility_bill(acc, 'gas',
                date(2000, 3, 1), date(2000, 4, 1), StringIO('March 2000'),
                'march.pdf')
        bill3 = self.process.roll_reebill(acc)
        self.assertEqual(None, self.process.get_late_charge(bill3,
                date(1999, 12, 31)))
        self.assertEqual(None, self.process.get_late_charge(bill3,
                date(2013, 1, 1)))

        # late charge should be based on the version with the least total
        # of the bill from which it derives. on 2013-01-15, make a version
        # 1 of bill 1 with a lower total, and then on 2013-03-15, a version
        # 2 with a higher total, and check that the late charge comes from
        # version 1.
        self.process.new_version(acc, 1)
        bill1_1 = self.state_db.get_reebill(acc, 1, version=1)
        self.process.ree_getter = MockReeGetter(100)
        self.process.bind_renewable_energy(acc, 1)
        bill1_1.discount_rate = 0.75
        self.process.compute_reebill(acc, 1, version=1)
        self.assertEqual(25, bill1_1.ree_charge)
        self.assertEqual(25, bill1_1.balance_due)
        self.process.issue(acc, 1, issue_date=date(2013, 3, 15))
        late_charge_source_amount = bill1_1.balance_due

        self.process.new_version(acc, 1)
        self.process.bind_renewable_energy(acc, 2)
        self.process.update_sequential_account_info(acc, 1,
                discount_rate=.25)
        bill1_2 = self.state_db.get_reebill(acc, 1, version=2)
        self.process.compute_reebill(acc, 1, version=2)
        self.assertEqual(75, bill1_2.ree_charge)
        self.assertEqual(75, bill1_2.balance_due)
        self.process.issue(acc, 1)

        # note that the issue date on which the late charge in bill2 is
        # based is the issue date of version 0--it doesn't matter when the
        # corrections were issued.
        late_charge = self.process.get_late_charge(bill2, date(2013, 4, 18))
        self.assertEqual(late_charge_source_amount * bill2.late_charge_rate,
                         late_charge)

        # add a payment between 2000-01-01 (when bill1 version 0 was
        # issued) and 2013-01-01 (the present), to make sure that payment
        # is deducted from the balance on which the late charge is based
        self.state_db.create_payment(acc, date(2000, 6, 5),
                                     'a $10 payment in june', 10)
        self.assertEqual((late_charge_source_amount - 10) *
                bill2.late_charge_rate,
                self.process.get_late_charge(bill2, date(2013, 1, 1)))

        #Pay off the bill, make sure the late charge is 0
        self.process.create_payment(acc, date(2000, 6, 6),
                'a $40 payment in june', 40)
        self.assertEqual(0, self.process.get_late_charge(bill2,
                                                         date(2013, 1, 1)))

        #Overpay the bill, make sure the late charge is still 0
        self.process.create_payment(acc, date(2000, 6, 7),
                'a $40 payment in june', 40)
        self.assertEqual(0, self.process.get_late_charge(bill2,
                date(2013, 1, 1)))


    def test_compute_realistic_charges(self):
        '''Tests computing utility bill charges and reebill charge for a
        reebill based on the utility bill, using a set of charge from an actual
        bill.
        '''
        account = '99999'
        # create utility bill and reebill
        self.process.upload_utility_bill(account, 'gas', date(2012, 1, 1),
                date(2012, 2, 1), StringIO('January 2012'), 'january.pdf')
        utilbill_id = self.process.get_all_utilbills_json(
                account, 0, 30)[0][0]['id']

        # the UPRS for this utility bill will be empty, because there are
        # no other utility bills in the db, and the bill will have no
        # charges; all the charges in the template bill get removed because
        # the rate structure has no RSIs in it. so, add RSIs and charges
        # corresponding to them from example_data. (this is the same way
        # the user would manually add RSIs and charges when processing the
        # first bill for a given rate structure.)
        for fields in example_data.charge_fields:
            self.process.add_rsi(utilbill_id)
            self.process.update_rsi(utilbill_id, "New RSI #1", fields)
        self.process.refresh_charges(utilbill_id)

        # ##############################################################
        # check that each actual (utility) charge was computed correctly:
        quantity = self.process.get_registers_json(
                utilbill_id)[0]['quantity']
        actual_charges = self.process.get_utilbill_charges_json(utilbill_id)
        def get_total(rsi_binding):
            charge = next(c for c in actual_charges
                    if c['rsi_binding'] == rsi_binding)
            return charge['total']
        self.assertEqual(11.2, get_total('SYSTEM_CHARGE'))
        self.assertEqual(0.03059 * quantity, get_total('RIGHT_OF_WAY'))
        self.assertEqual(0.01399 * quantity, get_total('SETF'))
        self.assertEqual(0.006 * quantity, get_total('EATF'))
        self.assertEqual(0.07777 * quantity, get_total('DELIVERY_TAX'))
        self.assertEqual(23.14, get_total('PUC'))
        self.assertEqual(.2935 * quantity, get_total('DISTRIBUTION_CHARGE'))
        self.assertEqual(.7653 * quantity, get_total('PGC'))
        # sales tax depends on all of the above
        non_tax_rsi_bindings = [
            'SYSTEM_CHARGE',
            'DISTRIBUTION_CHARGE',
            'PGC',
            'RIGHT_OF_WAY',
            'PUC',
            'SETF',
            'EATF',
            'DELIVERY_TAX'
        ]
        self.assertEqual(0.06 * sum(map(get_total, non_tax_rsi_bindings)),
                get_total('SALES_TAX'))

        # ##############################################################
        # check that each hypothetical charge was computed correctly:
        self.process.roll_reebill(account, start_date=date(2012, 1, 1))
        self.process.compute_reebill(account, 1)
        reebill_charges = self.process.get_hypothetical_matched_charges(
                account, 1)
        def get_h_total(rsi_binding):
            charge = next(c for c in reebill_charges
                    if c['rsi_binding'] == rsi_binding)
            return charge['total']
        h_quantity = self.process.get_reebill_metadata_json(
                account)[0]['ree_quantity']
        self.assertEqual(11.2, get_h_total('SYSTEM_CHARGE'))
        self.assertEqual(0.03059 * h_quantity, get_h_total('RIGHT_OF_WAY'))
        self.assertEqual(0.01399 * h_quantity, get_h_total('SETF'))
        self.assertEqual(0.006 * h_quantity, get_h_total('EATF'))
        self.assertEqual(0.07777 * h_quantity, get_h_total('DELIVERY_TAX'))
        self.assertEqual(23.14, get_h_total('PUC'))
        self.assertEqual(.2935 * h_quantity,
                get_h_total('DISTRIBUTION_CHARGE'))
        self.assertEqual(.7653 * h_quantity, get_h_total('PGC'))
        self.assertEqual(0.06 * sum(map(get_h_total, non_tax_rsi_bindings)),
                get_h_total('SALES_TAX'))


    def test_upload_utility_bill(self):
        #Good
        '''Tests saving of utility bills in database (which also belongs partly
        to StateDB); does not test saving of utility bill files (which belongs
        to BillUpload).'''
        # TODO include test of saving of utility bill files here
        account = '99999'

        # one utility bill
        # service, utility, rate_class are different from the template
        # account
        utilbill_path = join(dirname(realpath(__file__)), 'data',
                             'utility_bill.pdf')
        with open(utilbill_path) as file1:
            self.process.upload_utility_bill(account, 'electric',
                                             date(2012, 1, 1),
                                             date(2012, 2, 1), file1,
                                             'january.pdf',
                                             utility='pepco',
                                             rate_class='Residential-R')
        utilbills_data, _ = self.process.get_all_utilbills_json(account, 0,
                                                                30)
        self.assertDocumentsEqualExceptKeys([{
                                                 'state': 'Final',
                                                 'service': 'Electric',
                                                 'utility': 'pepco',
                                                 'rate_class': 'Residential-R',
                                                 'period_start': date(2012,
                                                                      1, 1),
                                                 'period_end': date(2012, 2,
                                                                    1),
                                                 'total_charges': 0,
                                                 'computed_total': 0,
                                                 # 'date_received': datetime.utcnow().date(),
                                                 'processed': 0,
                                                 'account': '99999',
                                                 'editable': True,
                                                 'id': None,
                                                 'reebills': [],
                                             }], utilbills_data, 'id',
                                            'name')

        # TODO check "meters and registers" data here
        # TODO check "charges" data here

        # check charges
        charges = self.process.get_utilbill_charges_json(
                utilbills_data[0]['id'])
        self.assertEqual([], charges)

        # second bill: default utility and rate class are chosen
        # when those arguments are not given, and non-standard file
        # extension is used
        with open(utilbill_path) as file2:
            self.process.upload_utility_bill(account, 'electric',
                                             date(2012, 2, 1),
                                             date(2012, 3, 1), file2,
                                             'february.abc')
        utilbills_data, _ = self.process.get_all_utilbills_json(
                                                                account, 0,
                                                                30)
        self.assertDocumentsEqualExceptKeys([{
                                                 'state': 'Final',
                                                 'service': 'Electric',
                                                 'utility': 'pepco',
                                                 'rate_class': 'Residential-R',
                                                 'period_start': date(2012,
                                                                      2, 1),
                                                 'period_end': date(2012, 3,
                                                                    1),
                                                 'total_charges': 0,
                                                 'computed_total': 0,
                                                 # 'date_received': datetime.utcnow().date(),
                                                 'processed': 0,
                                                 'account': '99999',
                                                 'editable': True,
                                                 'id': None,
                                                 'reebills': [],
                                             }, {
                                                 'state': 'Final',
                                                 'service': 'Electric',
                                                 'utility': 'pepco',
                                                 'rate_class': 'Residential-R',
                                                 'period_start': date(2012,
                                                                      1, 1),
                                                 'period_end': date(2012, 2,
                                                                    1),
                                                 'total_charges': 0,
                                                 'computed_total': 0,
                                                 # 'date_received': datetime.utcnow().date(),
                                                 'processed': 0,
                                                 'account': '99999',
                                                 'editable': True,
                                                 'id': None,
                                                 'reebills': [],
                                             }], utilbills_data, 'id',
                                            'name')

        # 3rd bill "Skyline estimated", without a file
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 3, 1), date(2012, 4, 1),
                                         None, None,
                                         state=UtilBill.SkylineEstimated,
                                         utility='washgas',
                                         rate_class='DC Non Residential Non Heat')
        utilbills_data, _ = self.process.get_all_utilbills_json(account, 0,
                                                                30)
        self.assertDocumentsEqualExceptKeys([{
                                                 'state': 'Skyline Estimated',
                                                 'service': 'Gas',
                                                 'utility': 'washgas',
                                                 'rate_class': 'DC Non Residential Non Heat',
                                                 'period_start': date(2012,
                                                                      3, 1),
                                                 'period_end': date(2012, 4,
                                                                    1),
                                                 'total_charges': 0,
                                                 'computed_total': 0,
                                                 'processed': 0,
                                                 'account': '99999',
                                                 'editable': True,
                                                 'reebills': [],
                                             }, {
                                                 'state': 'Final',
                                                 'service': 'Electric',
                                                 'utility': 'pepco',
                                                 'rate_class': 'Residential-R',
                                                 'period_start': date(2012,
                                                                      2, 1),
                                                 'period_end': date(2012, 3,
                                                                    1),
                                                 'total_charges': 0,
                                                 'computed_total': 0,
                                                 # 'date_received': datetime.utcnow().date(),
                                                 'processed': 0,
                                                 'account': '99999',
                                                 'editable': True,
                                                 'id': None,
                                                 'reebills': [],
                                             }, {
                                                 'state': 'Final',
                                                 'service': 'Electric',
                                                 'utility': 'pepco',
                                                 'rate_class': 'Residential-R',
                                                 'period_start': date(2012,
                                                                      1, 1),
                                                 'period_end': date(2012, 2,
                                                                    1),
                                                 'total_charges': 0,
                                                 'computed_total': 0,
                                                 # 'date_received': datetime.utcnow().date(),
                                                 'processed': 0,
                                                 'account': '99999',
                                                 'editable': True,
                                                 'id': None,
                                                 'reebills': [],
                                             }], utilbills_data, 'id',
                                            'name')

        # 4th bill: utility and rate_class will be taken from the last bill
        # with the same service. the file has no extension.
        last_bill_id = utilbills_data[0]['id']
        with open(utilbill_path) as file4:
            self.process.upload_utility_bill(account, 'electric',
                                             date(2012, 4, 1),
                                             date(2012, 5, 1), file4,
                                             'august')

        utilbills_data, count = self.process.get_all_utilbills_json(
                account, 0, 30)
        # NOTE: upload_utility bill is creating additional "missing"
        # utility bills, so there may be > 4 bills in the database now,
        # but this feature should not be tested because it's not used and
        # will probably go away.
        self.assertEqual(4, count)
        last_utilbill = utilbills_data[0]
        self.assertDocumentsEqualExceptKeys({
                                                'state': 'Final',
                                                'service': 'Electric',
                                                'utility': 'pepco',
                                                'rate_class': 'Residential-R',
                                                'period_start': date(2012,
                                                                     4, 1),
                                                'period_end': date(2012, 5,
                                                                   1),
                                                'total_charges': 0,
                                                'computed_total': 0,
                                                'processed': 0,
                                                'account': '99999',
                                                'editable': True,
                                                'reebills': [],
                                            }, last_utilbill, 'id', 'name')

        # make sure files can be accessed for these bills (except the
        # estimated one)
        for obj in utilbills_data:
            id, state = obj['id'], obj['state']
            u = self.state_db.get_utilbill_by_id(id)
            if state == 'Final':
                self.process.billupload.get_utilbill_file_path(u)
            else:
                with self.assertRaises(IOError):
                    self.process.billupload.get_utilbill_file_path(u)

        # delete utility bills
        ids = [obj['id'] for obj in utilbills_data]

        _, new_path = self.process.delete_utility_bill_by_id(ids[3])
        _, count = self.process.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(3, count)
        self.assertTrue(os.access(new_path, os.F_OK))
        _, new_path = self.process.delete_utility_bill_by_id(ids[2])
        _, count = self.process.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(2, count)
        self.assertTrue(os.access(new_path, os.F_OK))
        _, new_path = self.process.delete_utility_bill_by_id(ids[1])
        _, count = self.process.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(1, count)
        _, new_path = self.process.delete_utility_bill_by_id(ids[0])
        _, count = self.process.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(0, count)

    def test_delete_utility_bill_with_reebill(self):
        account = '99999'
        start, end = date(2012, 1, 1), date(2012, 2, 1)
        # create utility bill in MySQL, Mongo, and filesystem (and make
        # sure it exists all 3 places)
        self.process.upload_utility_bill(account, 'gas', start, end,
                StringIO("test"), 'january.pdf')
        utilbills_data, count = self.process.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(1, count)

        # when utilbill is attached to reebill, deletion should fail
        self.process.roll_reebill(account, start_date=start)
        reebills_data = self.process.get_reebill_metadata_json(account)
        self.assertEqual([{
                              'actual_total': 0,
                              'balance_due': 0.0,
                              'balance_forward': 0,
                              'corrections': '(never issued)',
                              'hypothetical_total': 0,
                              'id': 1,
                              'issue_date': None,
                              'issued': False,
                              'max_version': 0,
                              'payment_received': 0.0,
                              'period_end': date(2012, 2, 1),
                              'period_start': date(2012, 1, 1),
                              'prior_balance': 0,
                              'processed': False,
                              'ree_charges': 0.0,
                              'ree_quantity': 22.602462036826545,
                              'ree_value': 0,
                              'sequence': 1,
                              'services': [],
                              'total_adjustment': 0,
                              'total_error': 0.0
                          }], reebills_data)
        self.assertRaises(ValueError,
                          self.process.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

        # deletion should fail if any version of a reebill has an
        # association with the utility bill. so issue the reebill, add
        # another utility bill, and create a new version of the reebill
        # attached to that utility bill instead.
        self.process.issue(account, 1)
        self.process.new_version(account, 1)
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO("test"),
                                         'january-electric.pdf')
        # TODO this may not accurately reflect the way reebills get
        # attached to different utility bills; see
        # https://www.pivotaltracker.com/story/show/51935657
        self.assertRaises(ValueError,
                          self.process.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])
    def test_get_service_address(self):
        account = '99999'
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO("A PDF"), 'january.pdf')
        address = self.process.get_service_address(account)
        self.assertEqual(address['postal_code'], '20010')
        self.assertEqual(address['city'], 'Washington')
        self.assertEqual(address['state'], 'DC')
        self.assertEqual(address['addressee'], 'Monroe Towers')
        self.assertEqual(address['street'], '3501 13TH ST NW #WH')

    def test_correction_issuing(self):
        """Test creating corrections on reebills, and issuing them to create
        adjustments on other reebills.
        """
        acc = '99999'
        p = self.process
        base_date = date(2012, 1, 1)

        for i in xrange(4):
            ub = p.upload_utility_bill(acc, 'gas',
                                       base_date + timedelta(days=30 * i),
                                       base_date + timedelta(
                                           days=30 * (i + 1)),
                                       StringIO('a utility bill'),
                                       'filename.pdf')

            p.add_rsi(ub.id)  #creates an RSI with binding 'New RSI #1'
            p.update_rsi(ub.id,  #update the just-created RSI
                         'New RSI #1',
                         {'rsi_binding': 'THE_CHARGE',
                          'quantity': 'REG_TOTAL.quantity',
                          'rate': '1',
                          'group': 'All Charges'})

            p.update_register(ub.id, 'M60324', 'M60324',
                              {'quantity': 100})

            p.refresh_charges(ub.id)  #creates charges
            p.compute_utility_bill(ub.id)  #updates charge values

        for seq, reg_tot, strd in [(1, 100, base_date), (2, 200, None),
                                   (3, 300, None)]:
            rb = p.roll_reebill(acc, start_date=strd)
            p.update_sequential_account_info(acc, seq, discount_rate=0.5)
            p.ree_getter = MockReeGetter(reg_tot)
            p.bind_renewable_energy(acc, seq)
            p.compute_reebill(acc, seq)
            p.issue(acc, seq)

            self.assertEqual(rb.ree_charge, reg_tot / 2.0,
                             "Reebill %s recharge should equal %s; not %s" \
                             % (seq, reg_tot / 2.0, rb.ree_charge))

        self.assertEquals([], p.get_unissued_corrections(acc),
                            "There should be no unissued corrections.")
        self.assertEquals(0, p.get_total_adjustment(acc),
                          "There should be no total adjustments.")

        p.roll_reebill(acc)  #Fourth Reebill

        # try to issue nonexistent corrections
        self.assertRaises(ValueError, p.issue_corrections, acc, 4)

        reebill_data = lambda seq: next(d for d in \
                                        p.get_reebill_metadata_json(acc)
                                        if d['sequence'] == seq)

        #Update the discount rate for reebill sequence 1
        p.new_version(acc, 1)
        p.update_sequential_account_info(acc, 1, discount_rate=0.75)
        p.ree_getter = MockReeGetter(100)
        p.bind_renewable_energy(acc, 1)
        p.compute_reebill(acc, 1, version=1)

        d = reebill_data(1)
        self.assertEqual(d['ree_charges'], 25.0,
                         "Charges for reebill seq 1 should be updated to 25")

        #Update the discount rate for reebill sequence 3
        p.new_version(acc, 3)
        p.update_sequential_account_info(acc, 3, discount_rate=0.25)
        p.ree_getter = MockReeGetter(300)
        p.bind_renewable_energy(acc, 3)
        p.compute_reebill(acc, 3)
        d = reebill_data(3)
        self.assertEqual(d['ree_charges'], 225.0,
                         "Charges for reebill seq 3 should be updated to 225")

        # there should be 2 adjustments: -25 for the first bill, and +75
        # for the 3rd
        self.assertEqual([(1, 1, -25), (3, 1, 75)],
                         p.get_unissued_corrections(acc))
        self.assertEqual(50, p.get_total_adjustment(acc))

        # try to apply corrections to an issued bill
        self.assertRaises(ValueError, p.issue_corrections, acc, 2)
        # try to apply corrections to a correction
        self.assertRaises(ValueError, p.issue_corrections, acc, 3)

        self.assertFalse(reebill_data(1)['issued'])
        self.assertFalse(reebill_data(3)['issued'])

        # get original balance of reebill 4 before applying corrections
        #four = self.state_db.get_reebill(session, acc, 4)
        p.compute_reebill(acc, 4)

        # apply corrections to un-issued reebill 4. reebill 4 should be
        # updated, and the corrections (1 & 3) should be issued
        p.issue_corrections(acc, 4)
        p.compute_reebill(acc, 4)
        # for some reason, adjustment is part of "balance forward"
        # https://www.pivotaltracker.com/story/show/32754231

        four = reebill_data(4)
        self.assertEqual(four['prior_balance'] - four['payment_received'] +
                         four['total_adjustment'], four['balance_forward'])
        self.assertEquals(four['balance_forward'] + four['ree_charges'],
                          four['balance_due'])

        self.assertTrue(reebill_data(1)['issued'])
        self.assertTrue(reebill_data(3)['issued'])

        self.assertEqual([], p.get_unissued_corrections(acc))


    def test_late_charge_correction(self):
        acc = '99999'
        # set customer late charge rate
        customer = self.state_db.get_customer(acc)
        customer.set_discountrate(.5)
        customer.set_late_charge_rate(.34)

        # first utility bill (ensure that an RSI and a charge exist,
        # and mark as "processed" so next utility bill will have them too
        u1 = self.process.upload_utility_bill(acc, 'gas',
                                              date(2012, 1, 1),
                                              date(2012, 2, 1),
                                              StringIO('January 2012'),
                                              'january.pdf')

        self.process.add_charge(u1.id, "")
        self.process.update_charge(u1.id, "", dict(rsi_binding='THE_CHARGE',
            quantity=100,
            quantity_units='therms', rate=1,
            total=100, group='All Charges'))

        raise NotImplementedError()
        """Not Implemented because test is not using process"""
        u1_uprs = self.rate_structure_dao.load_uprs_for_utilbill(u1)
        u1_uprs.rates = [RateStructureItem(
            rsi_binding='THE_CHARGE',
            quantity='REG_TOTAL.quantity',
            rate='1',
        )]
        u1_uprs.save()
        self.process.update_utilbill_metadata(u1.id,
                                              processed=True)

        # 2nd utility bill
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('February 2012'),
                                         'february.pdf')

        # 1st reebill, with a balance of 100, issued 40 days ago and unpaid
        # (so it's 10 days late)
        # TODO don't use current date in a test!
        one = self.process.roll_reebill(acc,
                                        start_date=date(2012, 1, 1))
        one_doc = self.reebill_dao.load_reebill(acc, 1)
        # TODO control amount of renewable energy given by mock_skyliner
        # so there's no need to replace that value with a known one here
        one.set_renewable_energy_reading('REG_TOTAL', 100 * 1e5)
        self.process.compute_reebill(acc, 1)
        assert one.ree_charge == 50
        assert one.balance_due == 50
        self.process.issue(acc, 1,
                           issue_date=datetime.utcnow().date() - timedelta(
                               40))

        # 2nd reebill, which will get a late charge from the 1st
        two = self.process.roll_reebill(acc)

        # "bind REE" in 2nd reebill
        # (it needs energy data only so its correction will have the same
        # energy in it as the original version; only the late charge will
        # differ)
        self.process.ree_getter.update_renewable_readings(
            self.nexus_util.olap_id(acc), two)

        # if given a late_charge_rate > 0, 2nd reebill should have a late
        # charge
        two.late_charge_rate = .5
        self.process.compute_reebill(acc, 2)
        self.assertEqual(25, two.late_charge)

        # issue 2nd reebill so a new version of it can be created
        self.process.issue(acc, 2)

        # add a payment of $30 30 days ago (10 days after 1st reebill was
        # issued). the late fee above is now wrong; it should be 50% of
        # the unpaid $20 instead of 50% of the entire $50.
        self.process.create_payment(acc, datetime.utcnow().date()
                - timedelta(30), 'backdated payment', 30)

        # now a new version of the 2nd reebill should have a different late
        # charge: $10 instead of $50.
        self.process.new_version(acc, 2)
        two_1 = self.state_db.get_reebill(acc, 2, version=1)
        assert two_1.late_charge_rate == .5
        self.process.compute_reebill(acc, 2, version=1)
        self.assertEqual(10, two_1.late_charge)

        # that difference should show up as an error
        corrections = self.process.get_unissued_corrections(acc)
        assert len(corrections) == 1
        # self.assertEquals((2, 1, 25 - 15), corrections[0])
        # for some reason there's a tiny floating-point error in the
        # correction amount so it must be compared with assertAlmostEqual
        # (which doesn't work on tuples)
        sequence, version, amount = corrections[0]
        self.assertEqual(2, sequence)
        self.assertEqual(1, version)
        self.assertAlmostEqual(-15, amount)

    # TODO rename
    def test_roll(self):
        '''Tests creation of reebills and dependency of each reebill on its
        predecessor.'''
        account = '99999'
        self.process.ree_getter = MockReeGetter(100)

        self.process.upload_utility_bill(account, 'gas',
                date(2013, 4, 4), date(2013, 5, 2), StringIO('April 2013'),
                'april.pdf')
        # add a register to the first utility bill so there are 2,
        # REG_TOTAL and OTHER
        id_1 = self.process.get_all_utilbills_json(
                account, 0, 30)[0][0]['id']
        self.process.new_register(id_1, {'meter_id': 'M60324',
                                         'register_id': 'R'})
        self.process.update_register(id_1,
                'M60324', 'R', {'binding': 'OTHER'})

        # 2nd utility bill should have the same registers as the first
        self.process.upload_utility_bill(account, 'gas',
                date(2013, 5, 2), date(2013, 6, 3), StringIO('May 2013'),
                'may.pdf')

        # create reebill based on first utility bill
        reebill1 = self.process.roll_reebill(account,
                                  start_date=date(2013, 4, 4))

        self.process.compute_reebill(account, 1)
        self.process.issue(account, 1)
        # delete register from the 2nd utility bill
        id_2 = self.process.get_all_utilbills_json(
                account, 0, 30)[0][0]['id']
        self.process.delete_register(id_2, 'M60324', 'R')

        # 2nd reebill should NOT have a reading corresponding to the
        # additional register, which was removed
        reebill2 = self.process.roll_reebill(account)
        utilbill_data, count = self.process.get_all_utilbills_json(
                account, 0, 30)
        self.assertEqual(2, count)
        self.assertEqual(reebill1.readings[0].measure, reebill2.readings[0].measure)
        self.assertEqual(reebill1.readings[0].aggregate_function,
                reebill2.readings[0].aggregate_function)
        self.assertEqual([{
            'sequence': 1,
            'version': 0,
            'issue_date': datetime.utcnow().date()
        }], utilbill_data[1]['reebills'])
        self.assertEqual([{
            'sequence': 2,
            'version': 0,
            'issue_date': None,
        }], utilbill_data[0]['reebills'])

        # the 1st reebill has a reading for both the "REG_TOTAL" register
        # and the "OTHER" register, for a total of 200 therms of renewable
        # energy. since the 2nd utility bill no longer has the "OTHER" register,
        # the 2nd reebill does not have a reading fot it, even though the 1st
        # reebill has it.
        reebill_2_data, reebill_1_data = self.process\
                .get_reebill_metadata_json(account)
        self.assertEqual(200, reebill_1_data['ree_quantity'])
        self.assertEqual(100, reebill_2_data['ree_quantity'])

        # addresses should be preserved from one reebill document to the
        # next
        billing_address = {
            u"postalcode" : u"20910",
            u"city" : u"Silver Spring",
            u"state" : u"MD",
            u"addressee" : u"Managing Member Monroe Towers",
            u"street" : u"3501 13TH ST NW LLC"
        }
        service_address = {
             u"postalcode" : u"20010",
             u"city" : u"Washington",
             u"state" : u"DC",
             u"addressee" : u"Monroe Towers",
             u"street" : u"3501 13TH ST NW #WH"
        }
        account_info = self.process.get_sequential_account_info(
                account, 1)
        self.assertEqual({
            'discount_rate': 0.12,
            'late_charge_rate': 0.34,
            'billing_address': billing_address,
            'service_address': service_address,
        }, account_info)

        # add two more utility bills: a Hypothetical one, then a Complete one
        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 6, 3), date(2013, 7, 1),
                                         None, 'no file',
                                         state=UtilBill.Hypothetical)
        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 7, 1),
                                         date(2013, 7, 30),
                                         StringIO('July 2013'),
                                         'july.pdf')
        utilbill_data, count = self.process.get_all_utilbills_json(
                account, 0, 30)
        self.assertEqual(4, count)
        self.assertEqual(['Final', 'Missing', 'Final', 'Final'],
                [u['state'] for u in utilbill_data])

        # The next utility bill isn't estimated or final, so
        # create_next_reebill should fail
        self.assertRaises(NoSuchBillException,
                self.process.roll_reebill, account)

        # replace Hypothetical bill with a UtilityEstimated one.
        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 6, 3), date(2013, 7, 1),
                                         StringIO('June 2013'),
                                         'june.pdf',
                                         state=UtilBill.UtilityEstimated)
        utilbill_data, count = self.process.get_all_utilbills_json(
                account, 0, 30)
        self.assertEqual(4, count)
        self.assertEqual(['Final', 'Utility Estimated', 'Final', 'Final'],
                         [u['state'] for u in utilbill_data])
        last_utilbill_id, formerly_hyp_utilbill_id = (u['id'] for u in
                utilbill_data[:2])

        self.process.roll_reebill(account)
        self.process.roll_reebill(account)
        self.process.compute_reebill(account, 2)

        self.process.issue(account, 2)

        # Shift later_utilbill a few days into the future so that there is
        # a time gap after the last attached utilbill
        self.process.update_utilbill_metadata(
                formerly_hyp_utilbill_id, period_start=date(2013,6,8))
        self.process.update_utilbill_metadata(last_utilbill_id,
                period_end=date(2013,7,6))

        # can't create another reebill because there are no more utility
        # bills
        with self.assertRaises(NoSuchBillException) as context:
            self.process.roll_reebill(account)


    def test_rs_prediction(self):
        '''Basic test of rate structure prediction when uploading utility
        bills.
        '''
        acc_a, acc_b, acc_c = 'aaaaa', 'bbbbb', 'ccccc'
        # create customers A, B, and C
        billing_address = {
           'addressee': 'Andrew Mellon',
           'street': '1785 Massachusetts Ave. NW',
           'city': 'Washington',
           'state': 'DC',
           'postal_code': '20036',
        }
        service_address = {
           'addressee': 'Skyline Innovations',
           'street': '1606 20th St. NW',
           'city': 'Washington',
           'state': 'DC',
           'postal_code': '20009',
        }

        self.process.create_new_account(acc_a, 'Customer A',
                .12, .34, billing_address, service_address, '100001')
        self.process.create_new_account(acc_b, 'Customer B',
               .12, .34, billing_address, service_address, '100001')
        self.process.create_new_account(acc_c, 'Customer C',
               .12, .34, billing_address, service_address, '100001')

        # new customers also need to be in nexus for 'update_renewable_readings' to
        # work (using mock Skyliner)
        self.nexus_util._customers.extend([
           {
               'billing': 'aaaaa',
               'olap': 'a-1',
               'casualname': 'Customer A',
               'primus': '1 A St.',
           },
           {
               'billing': 'bbbbb',
               'olap': 'b-1',
               'casualname': 'Customer B',
               'primus': '1 B St.',
           },
           {
               'billing': 'ccccc',
               'olap': 'c-1',
               'casualname': 'Customer C',
               'primus': '1 C St.',
           },
        ])

        # create utility bills and reebill #1 for all 3 accounts
        # (note that period dates are not exactly aligned)
        self.process.upload_utility_bill(acc_a, 'gas',
                date(2000,1,1), date(2000,2,1), StringIO('January 2000 A'),
                'january-a.pdf', total=0, state=UtilBill.Complete)
        self.process.upload_utility_bill(acc_b, 'gas',
                date(2000,1,1), date(2000,2,1), StringIO('January 2000 B'),
                'january-b.pdf', total=0, state=UtilBill.Complete)
        self.process.upload_utility_bill(acc_c, 'gas',
                date(2000,1,1), date(2000,2,1), StringIO('January 2000 C'),
                'january-c.pdf', total=0, state=UtilBill.Complete)

        id_a = next(obj['id'] for obj in self.process.get_all_utilbills_json(
               acc_a, 0, 30)[0])
        id_b = next(obj['id'] for obj in self.process.get_all_utilbills_json(
               acc_b, 0, 30)[0])
        id_c = next(obj['id'] for obj in self.process.get_all_utilbills_json(
               acc_c, 0, 30)[0])

        # UPRSs of all 3 bills will be empty.
        # insert some RSIs into them. A gets only one
        # RSI, SYSTEM_CHARGE, while B and C get two others,
        # DISTRIBUTION_CHARGE and PGC.
        self.process.add_rsi(id_a)
        self.process.add_rsi(id_a)
        self.process.update_rsi(id_a, 'New RSI #1', {
           'rsi_binding': 'SYSTEM_CHARGE',
            'description': 'System Charge',
            'quantity': '1',
            'rate': '11.2',
            'shared': True,
            'group': 'A',
        })
        self.process.update_rsi(id_a, 'New RSI #2', {
           'rsi_binding': 'NOT_SHARED',
           'description': 'System Charge',
           'quantity': '1',
           'rate': '3',
           'shared': False,
           'group': 'B',
        })
        for i in (id_b, id_c):
           self.process.add_rsi(i)
           self.process.add_rsi(i)
           self.process.update_rsi(i, 'New RSI #1', {
               'rsi_binding': 'DISTRIBUTION_CHARGE',
               'description': 'Distribution charge for all therms',
               'quantity': '750.10197727',
               'rate': '220.16',
               'shared': True,
               'group': 'C',
           })
           self.process.update_rsi(i, 'New RSI #2', {
               'rsi_binding': 'PGC',
               'description': 'Purchased Gas Charge',
               'quantity': '750.10197727',
               'rate': '0.7563',
               'shared': True,
               'group': 'D',
           })

        # create utility bill and reebill #2 for A
        self.process.upload_utility_bill(acc_a,
               'gas', date(2000,2,1), date(2000,3,1),
                StringIO('February 2000 A'), 'february-a.pdf', total=0,
                state=UtilBill.Complete)
        id_a_2 = [obj for obj in self.process.get_all_utilbills_json(
                acc_a, 0, 30)][0][0]['id']

        # initially there will be no RSIs in A's 2nd utility bill, because
        # there are no "processed" utility bills yet.
        self.assertEqual([], self.process.get_rsis_json(id_a_2))

        # when the other bills have been marked as "processed", they should
        # affect the new one.
        self.process.update_utilbill_metadata(id_a, processed=True)
        self.process.update_utilbill_metadata(id_b, processed=True)
        self.process.update_utilbill_metadata(id_c, processed=True)
        self.process.regenerate_uprs(id_a_2)
        # the UPRS of A's 2nd bill should now match B and C, i.e. it
        # should contain DISTRIBUTION and PGC and exclude SYSTEM_CHARGE,
        # because together the other two have greater weight than A's
        # reebill #1. it should also contain the NOT_SHARED RSI because
        # un-shared RSIs always get copied from each bill to its successor.
        self.assertEqual(set(['DISTRIBUTION_CHARGE', 'PGC', 'NOT_SHARED']),
                set(r['rsi_binding'] for r in
                    self.process.get_rsis_json(id_a_2)))

        # now, modify A-2's UPRS so it differs from both A-1 and B/C-1. if
        # a new bill is rolled, the UPRS it gets depends on whether it's
        # closer to B/C-1 or to A-2.
        self.process.delete_rsi(id_a_2, 'DISTRIBUTION_CHARGE')
        self.process.delete_rsi(id_a_2, 'PGC')
        self.process.delete_rsi(id_a_2, 'NOT_SHARED')
        self.process.add_rsi(id_a_2)
        self.process.update_rsi(id_a_2, 'New RSI #1', {
           'rsi_binding': 'RIGHT_OF_WAY',
           'description': 'DC Rights-of-Way Fee',
           'quantity': '750.10197727',
           'rate': '0.03059',
           'shared': True
        })

        # create B-2 with period 2-5 to 3-5, closer to A-2 than B-1 and C-1.
        # the latter are more numerous, but A-1 should outweigh them
        # because weight decreases quickly with distance.
        self.process.upload_utility_bill(acc_b, 'gas',
                date(2000,2,5), date(2000,3,5), StringIO('February 2000 B'),
               'february-b.pdf', total=0, state=UtilBill.Complete)
        self.assertEqual(set(['RIGHT_OF_WAY']), set(r['rsi_binding'] for r in
               self.process.get_rsis_json(id_a_2)))

    def test_rs_prediction_processed(self):
        '''Tests that rate structure prediction includes all and only utility
        bills that are "processed". '''
        # TODO
        pass

    def test_issue(self):
        '''Tests issuing of reebills.'''
        acc = '99999'
        # two utilbills, with reebills
        session = self.session
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO('january 2012'),
                                         'january.pdf')
        self.process.upload_utility_bill(acc, 'gas',
                                         date(2012, 2, 1), date(2012, 3, 1),
                                         StringIO('february 2012'),
                                         'february.pdf')
        one = self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        two = self.process.roll_reebill(acc)

        # neither reebill should be issued yet
        self.assertEquals(False, self.state_db.is_issued(acc, 1))
        self.assertEquals(None, one.issue_date)
        self.assertEquals(None, one.due_date)
        self.assertEqual(None, one.email_recipient)
        self.assertEquals(False, self.state_db.is_issued(acc, 2))
        self.assertEquals(None, two.issue_date)
        self.assertEquals(None, two.due_date)
        self.assertEqual(None, two.email_recipient)

        # two should not be issuable until one_doc is issued
        self.assertRaises(BillStateError, self.process.issue, acc, 2)

        # issue one
        self.process.issue(acc, 1)

        # re-load from mongo to see updated issue date, due date,
        # recipients
        self.assertEquals(True, one.issued)
        self.assertEquals(True, self.state_db.is_issued(acc, 1))
        self.assertEquals(datetime.utcnow().date(), one.issue_date)
        self.assertEquals(one.issue_date + timedelta(30), one.due_date)
        self.assertEquals('example@example.com', one.email_recipient)

        customer = self.state_db.get_customer(acc)
        customer.bill_email_recipient = 'test1@example.com, test2@exmaple.com'

        # issue two
        self.process.issue(acc, 2)

        # re-load from mongo to see updated issue date and due date
        self.assertEquals(True, self.state_db.is_issued(acc, 2))
        self.assertEquals(datetime.utcnow().date(), two.issue_date)
        self.assertEquals(two.issue_date + timedelta(30), two.due_date)
        self.assertEquals('test1@example.com, test2@exmaple.com',
                          two.email_recipient)

    def test_issue_2_at_once(self):
        '''Tests issuing one bill immediately after another, without
        recomputing it. In bug 64403990, a bill could be issued with a wrong
        "prior balance" because it was not recomputed before issuing to
        reflect a change to its predecessor.
        '''
        acc = '99999'
        # first reebill is needed so the others get computed correctly
        self.process.upload_utility_bill(acc, 'gas', date(2000, 1, 1),
                    date(2000, 2, 1), StringIO('january 2000'), 'january.pdf')
        self.process.roll_reebill(acc, start_date=date(2000, 1, 1))
        self.process.issue(acc, 1, date(2000, 2, 15))

        # two more utility bills and reebills
        self.process.upload_utility_bill(acc, 'gas', date(2000, 2, 1),
                date(2000, 3, 1), StringIO('february 2000'), 'february.pdf')
        self.process.upload_utility_bill(acc, 'gas', date(2000, 3, 1),
                date(2000, 4, 1), StringIO('february 2000'), 'february.pdf')
        two = self.process.roll_reebill(acc)
        three = self.process.roll_reebill(acc)

        # add a payment, shown on bill #2
        self.state_db.create_payment(acc, date(2000, 2, 16), 'a payment', 100)
        # TODO bill shows 0 because bill has no energy in it and
        # payment_received is 0
        self.process.compute_reebill(acc, 2)
        self.assertEqual(100, two.payment_received)
        self.assertEqual(-100, two.balance_due)

        # the payment does not appear on #3, since #3 has not be
        # recomputed
        self.assertEqual(0, three.payment_received)
        self.assertEqual(0, three.prior_balance)
        self.assertEqual(0, three.balance_forward)
        self.assertEqual(0, three.balance_due)

        # issue #2 and #3
        self.process.issue(acc, 2, date(2000, 5, 15))
        self.process.issue(acc, 3, date(2000, 5, 15))

        # #2 is still correct, and #3 should be too because it was
        # automatically recomputed before issuing
        self.assertEqual(100, two.payment_received)
        self.assertEqual(-100, two.balance_due)
        self.assertEqual(-100, three.prior_balance)
        self.assertEqual(0, three.payment_received)
        self.assertEqual(-100, three.balance_forward)
        self.assertEqual(-100, three.balance_due)


    def test_delete_reebill(self):
        account = '99999'
        # create 2 utility bills for Jan-Feb 2012
        self.process.upload_utility_bill(account, 'gas',
                date(2012, 1, 1), date(2012, 2, 1),
                StringIO('january 2012'), 'january.pdf')
        self.process.upload_utility_bill(account, 'gas',
                date(2012, 2, 1), date(2012, 3, 1),
                StringIO('february 2012'), 'february.pdf')
        utilbill = self.session.query(UtilBill).order_by(
                UtilBill.period_start).first()


        # create 2 reebills
        reebill = self.process.roll_reebill(account,
                                  start_date=date(2012, 1, 1))
        self.process.roll_reebill(account)

        # only the last reebill is deletable: deleting the 2nd one should
        # succeed, but deleting the 1st one should fail
        with self.assertRaises(IssuedBillError):
            self.process.delete_reebill(account, 1)
        self.process.delete_reebill(account, 2)
        with self.assertRaises(NoSuchBillException):
            self.reebill_dao.load_reebill(account, 2, version=0)
        self.assertEquals(1, self.session.query(ReeBill).count())
        self.assertEquals([1], self.state_db.listSequences(account))
        self.assertEquals([utilbill], reebill.utilbills)

        # issued reebill should not be deletable
        self.process.issue(account, 1)
        self.assertEqual(1, reebill.issued)
        self.assertEqual([utilbill], reebill.utilbills)
        self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)
        self.process.compute_reebill(account, 1, version=0)
        self.assertRaises(IssuedBillError, self.process.delete_reebill,
                          account, 1)

        # create a new verison and delete it, returning to just version 0
        self.process.new_version(account, 1)
        self.session.query(ReeBill).filter_by(version=1).one()
        self.assertEqual(1, self.state_db.max_version(account, 1))
        self.assertFalse(self.state_db.is_issued(account, 1))
        self.process.delete_reebill(account, 1)
        self.assertEqual(0, self.state_db.max_version(account, 1))
        self.assertTrue(self.state_db.is_issued(account, 1))

        # original version should still be attached to utility bill
        # TODO this will have to change. see
        # https://www.pivotaltracker.com/story/show/31629749
        self.assertEqual([utilbill], reebill.utilbills)
        self.assertEqual(reebill, utilbill._utilbill_reebills[0].reebill)

    def test_correction_adjustment(self):
        '''Tests that adjustment from a correction is applied to (only) the
        earliest unissued bill.'''
        # replace process.ree_getter with one that always sets the renewable
        # energy readings to a known value
        self.process.ree_getter = MockReeGetter(10)

        acc = '99999'

        # create 3 utility bills: Jan, Feb, Mar
        for i in range(3):
            self.setup_dummy_utilbill_calc_charges(acc, date(2012, i + 1, 1),
                    date(2012, i + 2, 1))

        # create 1st reebill and issue it
        self.process.roll_reebill(acc, start_date=date(2012, 1, 1))
        self.process.bind_renewable_energy(acc, 1)
        self.process.compute_reebill(acc, 1)
        self.process.issue(acc, 1)
        self.assertEqual([{
                              'id': 1,
                              'sequence': 1,
                              'max_version': 0,
                              'issued': True,
                              'issue_date': datetime.utcnow().date(),
                              'actual_total': 0.,
                              'hypothetical_total': 10,
                              'payment_received': 0.,
                              'period_start': date(2012, 1, 1),
                              'period_end': date(2012, 2, 1),
                              'prior_balance': 0.,
                              'processed': False,
                              'ree_charges': 8.8,
                              'ree_value': 10,
                              'services': [],
                              'total_adjustment': 0.,
                              'total_error': 0.,
                              'ree_quantity': 10,
                              'balance_due': 8.8,
                              'balance_forward': 0,
                              'corrections': '-',
                          }],
                         self.process.get_reebill_metadata_json('99999'))

        # create 2nd reebill, leaving it unissued
        self.process.ree_getter.quantity = 0
        self.process.roll_reebill(acc)
        # make a correction on reebill #1. this time 20 therms of renewable
        # energy instead of 10 were consumed.
        self.process.ree_getter.quantity = 20
        self.process.new_version(acc, 1)
        self.process.compute_reebill(acc, 2)

        self.assertEqual([{
                          'actual_total': 0,
                          'balance_due': 17.6,
                          'balance_forward': 17.6,
                          'corrections': '(never issued)',
                          'hypothetical_total': 0,
                          'id': 2,
                          'issue_date': None,
                          'issued': False,
                          'max_version': 0,
                          'payment_received': 0.0,
                          'period_end': date(2012, 3, 1),
                          'period_start': date(2012, 2, 1),
                          'prior_balance': 8.8,
                          'processed': False,
                          'ree_charges': 0.0,
                          'ree_quantity': 0,
                          'ree_value': 0,
                          'sequence': 2,
                          'services': [],
                          'total_adjustment': 8.8,
                          'total_error': 0.0
                      }, {
                          'actual_total': 0,
                          'balance_due': 17.6,
                          'balance_forward': 0,
                          'corrections': '#1 not issued',
                          'hypothetical_total': 20.0,
                          'id': 1,
                          'issue_date': None,
                          'issued': False,
                          'max_version': 1,
                          'payment_received': 0.0,
                          'period_end': date(2012, 2, 1),
                          'period_start': date(2012, 1, 1),
                          'prior_balance': 0,
                          'processed': False,
                          'ree_charges': 17.6,
                          'ree_quantity': 20,
                          'ree_value': 20,
                          'sequence': 1,
                          'services': [],
                          'total_adjustment': 0,
                          'total_error': 8.8,
                      }],
                     self.process.get_reebill_metadata_json('99999'))

    def test_create_first_reebill(self):
        '''Test creating the first utility bill and reebill for an account,
        making sure the reebill is correct with respect to the utility bill.
        '''
        # at first, there are no utility bills
        self.assertEqual(([], 0), self.process.get_all_utilbills_json(
                '99999', 0, 30))

        # upload a utility bill
        self.process.upload_utility_bill('99999', 'gas',
                date(2013,1,1), date(2013,2,1), StringIO('January 2013'),
                'january.pdf')

        utilbill_data = self.process.get_all_utilbills_json(
                '99999', 0, 30)[0][0]
        self.assertDocumentsEqualExceptKeys({
            'account': '99999',
            'computed_total': 0,
            'editable': True,
            'id': 6469L,
            'name': '99999 - Example 1/1785 Massachusetts Ave. - washgas: DC Non Residential Non Heat',
            'period_end': date(2013, 2, 1),
            'period_start': date(2013, 1, 1),
            'processed': 0,
            'rate_class': 'DC Non Residential Non Heat',
            'reebills': [],
            'service': 'Gas',
            'state': 'Final',
            'total_charges': 0.0,
            'utility': 'washgas',
            }, utilbill_data, 'id', 'charges')

        # create a reebill
        self.process.roll_reebill('99999', start_date=date(2013,1,1))

        utilbill_data = self.process.get_all_utilbills_json(
                '99999', 0, 30)[0][0]
        self.assertDocumentsEqualExceptKeys({
            'account': '99999',
            'computed_total': 0,
            'editable': True,
            'id': 6469L,
            'name': '99999 - Example 1/1785 Massachusetts Ave. - washgas: DC Non Residential Non Heat',
            'period_end': date(2013, 2, 1),
            'period_start': date(2013, 1, 1),
            'processed': 0,
            'rate_class': 'DC Non Residential Non Heat',
            'reebills': [{'issue_date': None, 'sequence': 1L,
                    'version': 0L}],
            'service': 'Gas', 'state': 'Final',
            'total_charges': 0.0,
            'utility': 'washgas',
        }, utilbill_data, 'id', 'charges')

        billing_address = {
            'addressee': 'Andrew Mellon',
            'street': '1785 Massachusetts Ave. NW',
            'city': 'Washington',
            'state': 'DC',
            'postal_code': '20036',
        }
        service_address = {
            'addressee': 'Skyline Innovations',
            'street': '1606 20th St. NW',
            'city': 'Washington',
            'state': 'DC',
            'postal_code': '20009',
        }
        self.process.create_new_account('55555', 'Another New Account',
                0.6, 0.2, billing_address, service_address, '99999')
        self.assertRaises(ValueError, self.process.roll_reebill,
                '55555', start_date=date(2013,2,1))

    def test_uncomputable_correction_bug(self):
        '''Regresssion test for
        https://www.pivotaltracker.com/story/show/53434901.'''
        account = '99999'
        # create reebill and utility bill
        self.process.upload_utility_bill(account, 'gas', date(2013, 1, 1),
                date(2013, 2, 1), StringIO('January 2013'), 'january.pdf')
        utilbill_id = self.process.get_all_utilbills_json(
                account, 0, 30)[0][0]['id']
        self.process.roll_reebill(account, start_date=date(2013, 1, 1))
        # bind, compute, issue
        self.process.bind_renewable_energy(account, 1)
        self.process.compute_reebill(account, 1)
        self.process.issue(account, 1)

        # create new version
        self.process.new_version(account, 1)
        self.assertEquals(1, self.state_db.max_version(account, 1))

        # initially, reebill version 1 can be computed without an error
        self.process.compute_reebill(account, 1, version=1)

        # put it in an un-computable state by adding a charge without an
        # RSI. it should now raise an RSIError
        self.process.add_charge(utilbill_id, '')
        #Todo: Do we want to raise a FormulaSyntaxError or a NoRSIError Here?
        self.assertRaises(FormulaSyntaxError, self.process.compute_reebill,
                          account, 1, version=1)

        # delete the new version
        self.process.delete_reebill(account, 1)
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertEquals(0, reebill_data[0]['max_version'])
        self.assertEquals(0, reebill_data[0]['max_version'])

        # try to create a new version again: it should succeed, even though
        # there was a KeyError due to a missing RSI when computing the bill
        self.process.new_version(account, 1)
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertEquals(1, reebill_data[0]['max_version'])


    def test_compute_utility_bill(self):
        '''Tests creation of a utility bill and updating the Mongo document
        after the MySQL row has changed.'''
        # create reebill and utility bill
        # NOTE Process._generate_docs_for_new_utility_bill requires utility
        # and rate_class arguments to match those of the template
        self.process.upload_utility_bill('99999', 'gas', date(2013, 5, 6),
                date(2013, 7, 8), StringIO('A Water Bill'), 'waterbill.pdf',
                utility='washgas', rate_class='some rate structure')
        utilbill_data = self.process.get_all_utilbills_json(
                '99999', 0, 30)[0][0]
        self.assertDocumentsEqualExceptKeys({
                                                'account': '99999',
                                                'computed_total': 0,
                                                'editable': True,
                                                'id': 6469L,
                                                'name': '99999 - Example 1/1785 Massachusetts Ave. - washgas: some rate structure',
                                                'period_end': date(2013, 7,
                                                                   8),
                                                'period_start': date(2013,
                                                                     5, 6),
                                                'processed': 0,
                                                'rate_class': 'some rate structure',
                                                'reebills': [],
                                                'service': 'Gas',
                                                'state': 'Final',
                                                'total_charges': 0.0,
                                                'utility': 'washgas',
                                            }, utilbill_data, 'id',
                                            'charges')
        #doc = self.process.get_utilbill_doc(session, utilbill_data['id'])
        #doc = self.process.get_utilbill_doc(session, utilbill_data['id'])

        # TODO enable these assertions when upload_utility_bill stops
        # ignoring them; currently they are set to match the template's
        # values regardless of the arguments to upload_utility_bill, and
        # Process._generate_docs_for_new_utility_bill requires them to
        # match the template.
        #self.assertEquals('water', doc['service'])
        #self.assertEquals('pepco', doc['utility'])
        #self.assertEquals('pepco', doc['rate_class'])

        # modify the MySQL utility bill
        self.process.update_utilbill_metadata(utilbill_data['id'],
                                              period_start=date(2013, 6, 6),
                                              period_end=date(2013, 8, 8),
                                              service='electricity',
                                              utility='BGE',
                                              rate_class='General Service - Schedule C')

        # add some RSIs to the UPRS, and charges to match

        self.process.add_rsi(utilbill_data['id'])
        self.process.update_rsi(utilbill_data['id'],'New RSI #1', {
            'rsi_binding': 'A',
            'description':'UPRS only',
            'quantity': '2',
            'rate': '3',
            'group': 'All Charges',
            'quantity_units':'kWh'
        })

        self.process.add_rsi(utilbill_data['id'])
        self.process.update_rsi(utilbill_data['id'],'New RSI #1', {
            'rsi_binding': 'B',
            'description':'not shared',
            'quantity': '6',
            'rate': '7',
            'quantity_units':'therms',
            'group': 'All Charges',
            'shared': False
        })

        # compute_utility_bill should update the document to match
        self.process.compute_utility_bill(utilbill_data['id'])
        self.process.refresh_charges(utilbill_data['id'])
        charges = self.process.get_utilbill_charges_json(utilbill_data['id'])

        # check charges
        # NOTE if the commented-out lines are added below the test will
        # fail, because the charges are missing those keys.
        self.assertEqual([
                             {
                                 'rsi_binding': 'A',
                                 'quantity': 2,
                                 'id': 'A',
                                 'quantity_units': 'kWh',
                                 'rate': 3,
                                 'total': 6,
                                 'description': 'UPRS only',
                                 'group': 'All Charges',
                             }, {
                                 'rsi_binding': 'B',
                                 'id': 'B',
                                 'quantity': 6,
                                 'quantity_units': 'therms',
                                 'rate': 7,
                                 'total': 42,
                                 'description': 'not shared',
                                 'group': 'All Charges',
                             },
                         ], charges)

    def test_compute_reebill(self):
        '''Basic test of reebill processing with an emphasis on making sure
        the accounting numbers in reebills are correct.
        '''
        account = '99999'
        energy_quantity = 100.0
        payment_amount = 100.0
        self.process.ree_getter = MockReeGetter(energy_quantity)

        # create 2 utility bills with 1 charge in them
        #from processing.state import Session
        #s = Session()

        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 1, 1), date(2013, 2, 1),
                                         StringIO('January 2013'),
                                         'january.pdf')
        self.process.upload_utility_bill(account, 'gas',
                                         date(2013, 2, 1), date(2013, 3, 1),
                                         StringIO('February 2013'),
                                         'february.pdf')
        utilbills_data, _ = self.process.get_all_utilbills_json(account, 0, 30)
        id_1, id_2 = (obj['id'] for obj in utilbills_data)
        self.process.add_rsi(id_1)
        self.process.update_rsi(id_1, 'New RSI #1',
                                {'rsi_binding': 'THE_CHARGE',
                                 'quantity': 'REG_TOTAL.quantity',
                                 'rate': '1', })
        self.process.refresh_charges(id_1)
        self.process.update_utilbill_metadata(id_1, processed=True)
        self.process.regenerate_uprs(id_2)
        self.process.refresh_charges(id_2)
        self.process.update_utilbill_metadata(id_2, processed=True)

        # create, process, and issue reebill

        rbc = self.session.query(ReeBillCharge).all()
        self.process.roll_reebill(account, start_date=date(2013, 1, 1))
        rbc = self.session.query(ReeBillCharge).all()
        self.process.update_sequential_account_info(account, 1,
                discount_rate=0.5)

        # get renewable energy and compute the reebill. make sure this is
        # idempotent because in the past there was a bug where it was not.
        for i in range(2):
            self.process.bind_renewable_energy(account, 1)
            self.process.compute_reebill(account, 1)
            reebill_data = self.process.get_reebill_metadata_json(account)
            self.assertDocumentsEqualExceptKeys([{
                 'sequence': 1,
                 'max_version': 0,
                 'issued': False,
                 'issue_date': None,
                 'actual_total': 0.,
                 'hypothetical_total': energy_quantity,
                 'payment_received': 0.,
                 'period_start': date(2013,1,1),
                 'period_end': date(2013,2,1),
                 'prior_balance': 0.,
                 'processed': False,
                 'ree_charges': energy_quantity * .5,
                 'ree_value': energy_quantity,
                 'services': [],
                 'total_adjustment': 0.,
                 'total_error': 0.,
                 'ree_quantity': energy_quantity,
                 'balance_due': energy_quantity * .5,
                 'balance_forward': 0.,
                 'corrections': '(never issued)',
             }], reebill_data, 'id')

        self.process.issue(account, 1, issue_date=date(2013, 2, 15))
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertDocumentsEqualExceptKeys([{
             'id': 1,
             'sequence': 1,
             'max_version': 0,
             'issued': True,
             'issue_date': date(2013,2,15),
             'actual_total': 0.,
             'hypothetical_total': energy_quantity,
             'payment_received': 0.,
             'period_start': date(2013,1,1),
             'period_end': date(2013,2,1),
             'prior_balance': 0.,
             'processed': False,
             'ree_charges': energy_quantity * .5,
             'ree_value': energy_quantity,
             'services': [],
             'total_adjustment': 0.,
             'total_error': 0.,
             'ree_quantity': energy_quantity,
             'balance_due': energy_quantity * .5,
             'balance_forward': 0.0,
             'corrections': '-',
         }], reebill_data)

        # add a payment so payment_received is not 0
        self.process.create_payment(account, date(2013,2,17),
                'a payment for the first reebill', payment_amount)

        # 2nd reebill
        self.process.roll_reebill(account)
        self.process.update_sequential_account_info(account, 2,
                                                    discount_rate=0.2)
        self.process.compute_reebill(account, 2)
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertDocumentsEqualExceptKeys([{
            'sequence': 2,
            'max_version': 0L,
            'issued': False,
            'issue_date': None,
            'actual_total': 0,
            'hypothetical_total': energy_quantity,
            'payment_received': payment_amount,
            'period_start': date(2013,2,1),
            'period_end': date(2013,3,1),
            'prior_balance': energy_quantity * .5,
            'processed': False,
            'ree_charges': energy_quantity * .8,
            'ree_value': energy_quantity,
            'services': [],
            'total_adjustment': 0,
            'total_error': 0.0,
            'ree_quantity': energy_quantity,
            'balance_due': energy_quantity * .5 +
                        energy_quantity * .8 - payment_amount,
            'balance_forward': energy_quantity * .5 -
                            payment_amount,
            'corrections': '(never issued)',
        },{
            'sequence': 1L,
            'max_version': 0L,
            'issued': True,
            'issue_date': date(2013,2,15),
            'actual_total': 0,
            'hypothetical_total': energy_quantity,
            'payment_received': 0.0,
            'period_start': date(2013,1,1),
            'period_end': date(2013,2,1),
            'prior_balance': 0,
            'processed': False,
            'ree_charges': energy_quantity * .5,
            'ree_value': energy_quantity,
            'services': [],
            'total_adjustment': 0,
            'total_error': 0.0,
            'ree_quantity': energy_quantity,
            'balance_due': energy_quantity * .5,
            'balance_forward': 0.0,
            'corrections': '-',
        }], reebill_data, 'id')
        # make a correction on reebill #1: payment does not get applied to
        # #1, and does get applied to #2
        # NOTE because #1-1 is unissued, its utility bill document should
        # be "current", not frozen
        self.process.new_version(account, 1)
        self.process.compute_reebill(account, 1)
        self.process.compute_reebill(account, 2)
        reebill_data = self.process.get_reebill_metadata_json(account)
        self.assertDocumentsEqualExceptKeys([{
            'sequence': 2,
            'max_version': 0,
            'issued': False,
            'issue_date': None,
            'actual_total': 0,
            'hypothetical_total': energy_quantity,
            'payment_received': payment_amount,
            'period_start': date(2013,2,1),
            'period_end': date(2013,3,1),
            'prior_balance': energy_quantity * .5,
            'processed': False,
            'ree_charges': energy_quantity * .8,
            'ree_value': energy_quantity,
            'services': [],
            'total_adjustment': 0,
            'total_error': 0,
            'ree_quantity': energy_quantity,
            'balance_due': energy_quantity * .5 +
                        energy_quantity * .8 - payment_amount,
            'balance_forward': energy_quantity * .5 -
                            payment_amount,
            'corrections': '(never issued)',
        },{
            'sequence': 1,
            'max_version': 1,
            'issued': False,
            'issue_date': None,
            'actual_total': 0,
            'hypothetical_total': energy_quantity,
            'payment_received': 0,
            'period_start': date(2013,1,1),
            'period_end': date(2013,2,1),
            'prior_balance': 0,
            'processed': False,
            'ree_charges': energy_quantity * .5,
            'ree_value': energy_quantity,
            'services': [],
            'total_adjustment': 0,
            'total_error': 0,
            'ree_quantity': energy_quantity,
            'balance_due': energy_quantity * .5,
            'balance_forward': 0,
            'corrections': '#1 not issued',
        }], reebill_data, 'id')

    def test_tou_metering(self):
        # TODO: possibly move to test_fetch_bill_data
        account = '99999'

        def get_mock_energy_consumption(install, start, end, measure,
                    ignore_misisng=True, verbose=False):
            assert start, end == (date(2000,1,1), date(2000,2,1))
            result = []
            for hourly_period in cross_range(start, end):
                # for a holiday (Jan 1), weekday (Fri Jan 14), or weekend
                # (Sat Jan 15), return number of BTU equal to the hour of
                # the day. no energy is consumed on other days.
                if hourly_period.day in (1, 14, 15):
                    result.append(hourly_period.hour)
                else:
                    result.append(0)
            assert len(result) == 31 * 24 # hours in January
            return result

        self.process.ree_getter.get_billable_energy_timeseries = \
                get_mock_energy_consumption

        self.process.upload_utility_bill(account, 'gas', date(2000, 1, 1),
                date(2000, 2, 1), StringIO('January'), 'january.pdf')

        # modify registers of this utility bill so they are TOU
        u = self.session.query(UtilBill).join(Customer).\
                filter_by(account='99999').one()
        doc = self.reebill_dao.load_doc_for_utilbill(u)
        doc['meters'][0]['registers'] = [{
            'register_binding': 'REG_TOTAL',
            'description': 'normal register',
            'identifier': 'test1',
            'quantity': 0,
            # use BTU to avoid unit conversion
            'quantity_units': 'btu',
            # this appears to be unused (though "type" values include
            # "total", "tou", "demand", and "")
            'type': 'total',
        },{
            'register_binding': 'TOU',
            'description': 'time-of-use register',
            'identifier': 'test2',
            'quantity': 0,
            'quantity_units': 'btu',
            # NOTE these hour ranges are inclusive at both ends
            'active_periods_weekday': [[9, 9]],
            'active_periods_weekend': [[11, 11]],
            'active_periods_holiday': [[13, 13]],
            'type': 'tou',
        }]
        self.reebill_dao.save_utilbill(doc)

        self.process.roll_reebill(account, start_date=date(2000,1,1))

        # the total energy consumed over the 3 non-0 days is
        # 3 * (0 + 2 + ... + 23) = 23 * 24 / 2 = 276.
        # when only the hours 9, 11, and 13 are included, the total is just
        # 9 + 11 + 13 = 33.
        total_renewable_btu = 23 * 24 / 2. * 3
        tou_renewable_btu = 9 + 11 + 13

        # check reading of the reebill corresponding to the utility register
        total_reading, tou_reading = self.session.query(ReeBill).one().readings
        self.assertEqual('btu', total_reading.unit)
        self.assertEqual(total_renewable_btu, total_reading.renewable_quantity)
        self.assertEqual('btu', tou_reading.unit)
        self.assertEqual(tou_renewable_btu, tou_reading.renewable_quantity)

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()