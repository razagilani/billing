from StringIO import StringIO
from datetime import date
import os
from os.path import join, dirname, realpath
from sqlalchemy.orm.exc import NoResultFound
from billing.core.model import UtilBill
from test import testing_utils
from test.setup_teardown import TestCaseWithSetup


class UtilbillProcessingTest(TestCaseWithSetup, testing_utils.TestCase):
    '''Integration tests for features of the ReeBill application that deal
    with utility bills (to become "NexBill") including database.
    '''
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
        self.process.create_new_account('88888', 'New Account', 'thermal',
                                        0.6, 0.2, billing_address,
                                        service_address, '100000')

        # Disabled this test for now since it bypasses the process object
        # customer = self.state_db.get_customer(session, '88888')
        # self.assertEquals('88888', customer.account)
        # self.assertEquals(0.6, customer.get_discount_rate())
        # self.assertEquals(0.2, customer.get_late_charge_rate())
        # template_customer = self.state_db.get_customer(session, '99999')
        # self.assertNotEqual(template_customer.utilbill_template_id,
        # customer.utilbill_template_id)

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
        self.assertDictContainsSubset({'state': 'Final',
                                       'service': 'Gas',
                                       'utility': 'Test Utility Company Template',
                                       'rate_class': 'Test Rate Class Template',
                                       'period_start': date(2013, 1, 1),
                                       'period_end': date(2013, 2, 1),
                                       'total_charges': 0.0,
                                       'computed_total': 0,
                                       'processed': 0,
                                       'account': '88888',
                                       'reebills': [],
                                       }, utilbill_data)

        self.process.add_charge(utilbill_data['id'])
        self.process.update_charge({'quantity_formula': 'REG_TOTAL.quantity',
                                    'rate': 1, 'rsi_binding': 'A',
                                    'description':'a'},
                                   utilbill_id=utilbill_data['id'],
                                   rsi_binding='New RSI #1')

        ubdata = self.process.get_all_utilbills_json('88888', 0, 30)[0][0]
        self.assertDictContainsSubset({
                                          'account': '88888',
                                          'computed_total': 0,
                                          'period_end': date(2013, 2, 1),
                                          'period_start': date(2013, 1, 1),
                                          'processed': 0,
                                          'rate_class': 'Test Rate Class Template',
                                          'service': 'Gas',
                                          'state': 'Final',
                                          'total_charges': 0.0,
                                          'utility': 'Test Utility Company Template',
                                          }, ubdata)

        # nothing should exist for account 99999
        # (this checks for bug #70032354 in which query for
        # get_reebill_metadata_json includes bills from all accounts)
        self.assertEqual(([], 0), self.process.get_all_utilbills_json(
            '99999', 0, 30))

        # it should not be possible to create an account that already
        # exists
        self.assertRaises(ValueError, self.process.create_new_account,
            '88888', 'New Account', 'pv', 0.6, 0.2,
            billing_address, service_address, '99999')

        # try creating another account when the template account has no
        # utility bills yet
        self.process.create_new_account('77777', 'New Account', 'thermal',
                0.6, 0.2, billing_address, service_address, '88888')
        self.process.create_new_account('66666', 'New Account', 'thermal',
                0.6, 0.2, billing_address, service_address, '77777')

        # Try creating a reebill for a new account that has no utility bills
        # uploaded yet
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
        assert utilbill.target_total == 100
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
        self.assertEqual(date(2013, 1, 2), utilbill.period_start)

        # check that file really exists at the expected path
        # (get_utilbill_file_path also checks for existence)
        bill_file_path = self.billupload.get_utilbill_file_path(utilbill)

        # change end date
        self.process.update_utilbill_metadata(utilbill.id,
                                              period_end=date(2013, 2, 2))
        self.assertEqual(date(2013, 2, 2), utilbill.period_end)

        # change service
        self.process.update_utilbill_metadata(utilbill.id,
                                              service='electricity')
        self.assertEqual('electricity', utilbill.service)

        # change "total" aka "total_charges"
        self.process.update_utilbill_metadata(utilbill.id,
                                              target_total=200)
        self.assertEqual(200, utilbill.target_total)
        # NOTE "total" is not in utility bill Mongo documents, only MySQL

        # change utility name
        self.process.update_utilbill_metadata(utilbill.id,
                                              utility='BGE')
        self.assertEqual('BGE', utilbill.utility)

        # change rate class
        self.process.update_utilbill_metadata(utilbill.id,
                                              rate_class='something else')
        self.assertEqual('something else', utilbill.rate_class)

        # change processed state
        self.assertEqual(False, utilbill.processed)
        self.process.update_utilbill_metadata(utilbill.id, processed=True)
        self.assertEqual(True, utilbill.processed)

        # even when the utility bill is attached to an issued reebill, only
        # the editable document gets changed
        reebill = self.process.roll_reebill('99999',
                                            start_date=date(2013, 1, 1))
        self.process.issue('99999', 1)
        self.process.update_utilbill_metadata(utilbill.id, service='water')

    def test_upload_utility_bill(self):
        '''Tests saving of utility bills in database (which also belongs partly
        to StateDB); does not test saving of utility bill files (which belongs
        to BillUpload).'''
        account = '99999'

        # validation of dates
        bad_dates = [
            (date(2000,1,1), date(2000,1,1,)),
            (date(2000,1,1), date(2001,1,2,)),
            ]
        for start, end in bad_dates:
            with self.assertRaises(ValueError):
                self.process.upload_utility_bill(
                    account, 'electric', start, end, StringIO(), 'january.pdf',
                    utility='pepco', rate_class='Residential-R')

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

        self.assertDictContainsSubset({
                                          'state': 'Final',
                                          'service': 'Electric',
                                          'utility': 'pepco',
                                          'rate_class': 'Residential-R',
                                          'period_start': date(2012, 1, 1),
                                          'period_end': date(2012, 2, 1),
                                          'total_charges': 0,
                                          'computed_total': 0,
                                          'processed': 0,
                                          'account': '99999',
                                          'reebills': []
                                      }, utilbills_data[0])

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
        dictionaries = [{
                            'state': 'Final',
                            'service': 'Electric',
                            'utility': 'pepco',
                            'rate_class': 'Residential-R',
                            'period_start': date(2012, 2, 1),
                            'period_end': date(2012, 3, 1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }, {
                            'state': 'Final',
                            'service': 'Electric',
                            'utility': 'pepco',
                            'rate_class': 'Residential-R',
                            'period_start': date(2012, 1, 1),
                            'period_end': date(2012, 2, 1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }]
        for x, y in zip(dictionaries, utilbills_data):
            self.assertDictContainsSubset(x, y)

        # 3rd bill "estimated", without a file
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 3, 1), date(2012, 4, 1),
                                         None, None,
                                         state=UtilBill.Estimated,
                                         utility='washgas',
                                         rate_class='DC Non Residential Non Heat')
        utilbills_data, _ = self.process.get_all_utilbills_json(account, 0,
                                                                30)
        dictionaries = [{
                            'state': 'Estimated',
                            'service': 'Gas',
                            'utility': 'washgas',
                            'rate_class': 'DC Non Residential Non Heat',
                            'period_start': date(2012, 3, 1),
                            'period_end': date(2012, 4,
                                               1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }, {
                            'state': 'Final',
                            'service': 'Electric',
                            'utility': 'pepco',
                            'rate_class': 'Residential-R',
                            'period_start': date(2012, 2, 1),
                            'period_end': date(2012, 3, 1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }, {
                            'state': 'Final',
                            'service': 'Electric',
                            'utility': 'pepco',
                            'rate_class': 'Residential-R',
                            'period_start': date(2012, 1, 1),
                            'period_end': date(2012, 2, 1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }]
        for x, y in zip(dictionaries, utilbills_data):
            self.assertDictContainsSubset(x, y)

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
        self.assertDictContainsSubset({
                                          'state': 'Final',
                                          'service': 'Electric',
                                          'utility': 'pepco',
                                          'rate_class': 'Residential-R',
                                          'period_start': date(2012, 4, 1),
                                          'period_end': date(2012, 5, 1),
                                          'total_charges': 0,
                                          'computed_total': 0,
                                          'processed': 0,
                                          'account': '99999',
                                          'reebills': [],
                                          }, last_utilbill)

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

    def test_get_service_address(self):
        account = '99999'
        self.process.upload_utility_bill(account, 'gas',
                                         date(2012, 1, 1), date(2012, 2, 1),
                                         StringIO("A PDF"), 'january.pdf')
        address = self.process.get_service_address(account)
        self.assertEqual('12345', address['postal_code'])
        self.assertEqual('Test City', address['city'])
        self.assertEqual('XX', address['state'])
        self.assertEqual('Test Customer 1 Service', address['addressee'])
        self.assertEqual('123 Test Street', address['street'])

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

        self.process.create_new_account(acc_a, 'Customer A', 'thermal',
                                        .12, .34, billing_address,
                                        service_address, '100001')
        self.process.create_new_account(acc_b, 'Customer B', 'thermal',
                                        .12, .34, billing_address,
                                        service_address, '100001')
        self.process.create_new_account(acc_c, 'Customer C', 'thermal',
                                        .12, .34, billing_address,
                                        service_address, '100001')

        # new customers also need to be in nexus for 'update_renewable_readings' to
        # work (using mock skyliner)
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
                                         date(2000, 1, 1), date(2000, 2, 1), StringIO('January 2000 A'),
                                         'january-a.pdf', total=0, state=UtilBill.Complete)
        self.process.upload_utility_bill(acc_b, 'gas',
                                         date(2000, 1, 1), date(2000, 2, 1), StringIO('January 2000 B'),
                                         'january-b.pdf', total=0, state=UtilBill.Complete)
        self.process.upload_utility_bill(acc_c, 'gas',
                                         date(2000, 1, 1), date(2000, 2, 1), StringIO('January 2000 C'),
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
        self.process.add_charge(id_a)
        self.process.add_charge(id_a)
        self.process.update_charge({
                                       'rsi_binding': 'SYSTEM_CHARGE',
                                       'description': 'System Charge',
                                       'quantity_formula': '1',
                                       'rate': 11.2,
                                       'shared': True,
                                       'group': 'A',
                                       }, utilbill_id=id_a, rsi_binding='New RSI #1')
        self.process.update_charge({
                                       'rsi_binding': 'NOT_SHARED',
                                       'description': 'System Charge',
                                       'quantity_formula': '1',
                                       'rate': 3,
                                       'shared': False,
                                       'group': 'B',
                                       }, utilbill_id=id_a, rsi_binding='New RSI #2')
        for i in (id_b, id_c):
            self.process.add_charge(i)
            self.process.add_charge(i)
            self.process.update_charge({
                                           'rsi_binding': 'DISTRIBUTION_CHARGE',
                                           'description': 'Distribution charge for all therms',
                                           'quantity_formula': '750.10197727',
                                           'rate': 220.16,
                                           'shared': True,
                                           'group': 'C',
                                           }, utilbill_id=i, rsi_binding='New RSI #1')
            self.process.update_charge({
                                           'rsi_binding': 'PGC',
                                           'description': 'Purchased Gas Charge',
                                           'quantity_formula': '750.10197727',
                                           'rate': 0.7563,
                                           'shared': True,
                                           'group': 'D',
                                           }, utilbill_id=i, rsi_binding='New RSI #2')

        # create utility bill and reebill #2 for A
        self.process.upload_utility_bill(acc_a,
                                         'gas', date(2000, 2, 1), date(2000, 3, 1),
                                         StringIO('February 2000 A'), 'february-a.pdf', total=0,
                                         state=UtilBill.Complete)
        id_a_2 = [obj for obj in self.process.get_all_utilbills_json(
            acc_a, 0, 30)][0][0]['id']

        # initially there will be no RSIs in A's 2nd utility bill, because
        # there are no "processed" utility bills yet.
        self.assertEqual([], self.process.get_utilbill_charges_json(id_a_2))

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
                             self.process.get_utilbill_charges_json(id_a_2)))

        # now, modify A-2's UPRS so it differs from both A-1 and B/C-1. if
        # a new bill is rolled, the UPRS it gets depends on whether it's
        # closer to B/C-1 or to A-2.
        self.process.delete_charge(utilbill_id=id_a_2, rsi_binding='DISTRIBUTION_CHARGE')
        self.process.delete_charge(utilbill_id=id_a_2, rsi_binding='PGC')
        self.process.delete_charge(utilbill_id=id_a_2, rsi_binding='NOT_SHARED')
        self.session.flush()
        self.process.add_charge(id_a_2)
        self.process.update_charge({
                                       'rsi_binding': 'RIGHT_OF_WAY',
                                       'description': 'DC Rights-of-Way Fee',
                                       'quantity_formula': '750.10197727',
                                       'rate': 0.03059,
                                       'shared': True
                                   }, utilbill_id=id_a_2, rsi_binding='New RSI #1')

        # create B-2 with period 2-5 to 3-5, closer to A-2 than B-1 and C-1.
        # the latter are more numerous, but A-1 should outweigh them
        # because weight decreases quickly with distance.
        self.process.upload_utility_bill(acc_b, 'gas',
                                         date(2000, 2, 5), date(2000, 3, 5), StringIO('February 2000 B'),
                                         'february-b.pdf', total=0, state=UtilBill.Complete)
        self.assertEqual(set(['RIGHT_OF_WAY']), set(r['rsi_binding'] for r in
                                                    self.process.get_utilbill_charges_json(id_a_2)))

    def test_rs_prediction_processed(self):
        '''Tests that rate structure prediction includes all and only utility
        bills that are "processed". '''
        # TODO
        pass

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
        self.assertDictContainsSubset({
                                          'account': '99999',
                                          'computed_total': 0,
                                          'period_end': date(2013, 7, 8),
                                          'period_start': date(2013, 5, 6),
                                          'processed': 0,
                                          'rate_class': 'some rate structure',
                                          'reebills': [],
                                          'service': 'Gas',
                                          'state': 'Final',
                                          'total_charges': 0.0,
                                          'utility': 'washgas',
                                          }, utilbill_data)

        # doc = self.process.get_utilbill_doc(session, utilbill_data['id'])
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

        self.process.add_charge(utilbill_data['id'])
        self.process.update_charge({
                                       'rsi_binding': 'A',
                                       'description':'UPRS only',
                                       'quantity_formula': '2',
                                       'rate': 3,
                                       'group': 'All Charges',
                                       'quantity_units':'kWh'
                                   },
                                   utilbill_id=utilbill_data['id'],
                                   rsi_binding='New RSI #1')

        self.process.add_charge(utilbill_data['id'])
        self.process.update_charge({
                                       'rsi_binding': 'B',
                                       'description':'not shared',
                                       'quantity_formula': '6',
                                       'rate': 7,
                                       'quantity_units':'therms',
                                       'group': 'All Charges',
                                       'shared': False
                                   }, utilbill_id=utilbill_data['id'], rsi_binding='New RSI #1')

        # compute_utility_bill should update the document to match
        self.process.compute_utility_bill(utilbill_data['id'])
        charges = self.process.get_utilbill_charges_json(utilbill_data['id'])

        # check charges
        # NOTE if the commented-out lines are added below the test will
        # fail, because the charges are missing those keys.
        for x, y in zip([
                            {
                                'rsi_binding': 'A',
                                'quantity': 2,
                                'quantity_units': 'kWh',
                                'rate': 3,
                                'total': 6,
                                'description': 'UPRS only',
                                'group': 'All Charges',
                                'error': None,
                                }, {
                                'rsi_binding': 'B',
                                'quantity': 6,
                                'quantity_units': 'therms',
                                'rate': 7,
                                'total': 42,
                                'description': 'not shared',
                                'group': 'All Charges',
                                'error': None,
                                },
                            ], charges):
            self.assertDictContainsSubset(x, y)

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

        example_charge_fields = [
            dict(rate=23.14,
                 rsi_binding='PUC',
                 description='Peak Usage Charge',
                 quantity_formula='1'),
            dict(rate=0.03059,
                 rsi_binding='RIGHT_OF_WAY',
                 roundrule='ROUND_HALF_EVEN',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=0.01399,
                 rsi_binding='SETF',
                 roundrule='ROUND_UP',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rsi_binding='SYSTEM_CHARGE',
                 rate=11.2,
                 quantity_formula='1'),
            dict(rsi_binding='DELIVERY_TAX',
                 rate=0.07777,
                 quantity_units='therms',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=.2935,
                 rsi_binding='DISTRIBUTION_CHARGE',
                 roundrule='ROUND_UP',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=.7653,
                 rsi_binding='PGC',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=0.006,
                 rsi_binding='EATF',
                 quantity_formula='REG_TOTAL.quantity'),
            dict(rate=0.06,
                 rsi_binding='SALES_TAX',
                 quantity_formula=(
                     'SYSTEM_CHARGE.total + DISTRIBUTION_CHARGE.total + '
                     'PGC.total + RIGHT_OF_WAY.total + PUC.total + '
                     'SETF.total + EATF.total + DELIVERY_TAX.total'))
        ]

        # there are no charges in this utility bill yet because there are no
        # other utility bills in the db, so add charges. (this is the same way
        # the user would manually add charges when processing the
        # first bill for a given rate structure.)
        for fields in example_charge_fields:
            self.process.add_charge(utilbill_id)
            self.process.update_charge(fields, utilbill_id=utilbill_id,
                                       rsi_binding="New RSI #1")

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
        self.assertDictContainsSubset({
                                          'actual_total': 0,
                                          'balance_due': 0.0,
                                          'balance_forward': 0,
                                          'corrections': '(never issued)',
                                          'hypothetical_total': 0,
                                          'issue_date': None,
                                          'issued': 0,
                                          'version': 0,
                                          'payment_received': 0.0,
                                          'period_end': date(2012, 2, 1),
                                          'period_start': date(2012, 1, 1),
                                          'prior_balance': 0,
                                          'processed': 0,
                                          'ree_charge': 0.0,
                                          'ree_quantity': 22.602462036826545,
                                          'ree_value': 0,
                                          'sequence': 1,
                                          'services': [],
                                          'total_adjustment': 0,
                                          'total_error': 0.0
                                      }, reebills_data[0])
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