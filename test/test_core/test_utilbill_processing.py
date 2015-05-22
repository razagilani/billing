from StringIO import StringIO
from datetime import date
from os.path import join, dirname, realpath

import requests
from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound
from core import init_model

from reebill.views import column_dict
from test import init_test_config, create_tables, clear_db
from exc import DuplicateFileError, UnEditableBillError, BillingError
from core.model import UtilBill, UtilityAccount, Utility, Address, Supplier, \
    RateClass, Register, Charge
from core.model import Session
from test import testing_utils
from test.setup_teardown import create_utilbill_processor, \
    TestCaseWithSetup, create_reebill_objects, FakeS3Manager, create_nexus_util


def setUpModule():
    init_test_config()
    create_tables()
    init_model()
    FakeS3Manager.start()

def tearDownModule():
    FakeS3Manager.stop()

class UtilbillProcessingTest(testing_utils.TestCase):
    """Integration tests for features of the ReeBill application that deal
    with utility bills including database.
    """
    @classmethod
    def setUpClass(cls):
        # these objects don't change during the tests, so they should be
        # created only once.
        cls.utilbill_processor = create_utilbill_processor()
        cls.billupload = cls.utilbill_processor.bill_file_handler
        cls.reebill_processor, cls.views = create_reebill_objects()
        cls.nexus_util = create_nexus_util()

    def setUp(self):
        clear_db()
        TestCaseWithSetup.insert_data()

    def tearDown(self):
        clear_db()

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
        init_test_config()
        init_model()
        self.reebill_processor.create_new_account(
            '88888', 'New Account', 'thermal', 0.6, 0.2, billing_address,
            service_address, '100000', '12345', 'test')

        # Disabled this test for now since it bypasses the process object
        # customer = self.state_db.get_customer(session, '88888')
        # self.assertEquals('88888', customer.account)
        # self.assertEquals(0.6, customer.get_discount_rate())
        # self.assertEquals(0.2, customer.get_late_charge_rate())
        # template_customer = self.state_db.get_customer(session, '99999')
        # self.assertNotEqual(template_customer.utilbill_template_id,
        # customer.utilbill_template_id)

        self.assertEqual(([], 0), self.views.get_all_utilbills_json('88888',
                                                                    0, 30))

        # Upload a utility bill and check it persists and fetches
        self.utilbill_processor.upload_utility_bill('88888', StringIO('January 2013'),
                                         date(2013, 1, 1), date(2013, 2, 1),
                                         'gas')
        utilbills_data = self.views.get_all_utilbills_json('88888',
                                                             0, 30)[0]

        self.assertEqual(1, len(utilbills_data))
        utilbill_data = utilbills_data[0]
        self.assertDictContainsSubset({'state': 'Final',
                                       'service': 'Gas',
                                       'utility':
                                            column_dict(self.views.get_utility('Test Utility Company Template')),
                                       'rate_class': self.views.
                                            get_rate_class('Test Rate Class Template').
                                            name,
                                       'period_start': date(2013, 1, 1),
                                       'period_end': date(2013, 2, 1),
                                       'total_charges': 0.0,
                                       'computed_total': 0,
                                       'processed': 0,
                                       'account': '88888',
                                       'reebills': [],
                                       }, utilbill_data)

        self.utilbill_processor.add_charge(utilbill_data['id'])
        self.utilbill_processor.update_charge(
            {'quantity_formula': Charge.get_simple_formula(Register.TOTAL),
             'rate': 1, 'rsi_binding': 'A', 'description': 'a'},
            utilbill_id=utilbill_data['id'], rsi_binding='New Charge 1')

        ubdata = self.views.get_all_utilbills_json('88888', 0, 30)[0][0]
        self.assertDictContainsSubset({
                                          'account': '88888',
                                          'computed_total': 0,
                                          'period_end': date(2013, 2, 1),
                                          'period_start': date(2013, 1, 1),
                                          'processed': 0,
                                          'rate_class': self.views.
                                            get_rate_class('Test Rate Class Template').
                                            name,
                                          'service': 'Gas',
                                          'state': 'Final',
                                          'total_charges': 0.0,
                                          'utility':
                                            column_dict(self.views.get_utility('Test Utility Company Template')),
                                          }, ubdata)

        # nothing should exist for account 99999
        # (this checks for bug #70032354 in which query for
        # get_reebill_metadata_json includes bills from all accounts)
        self.assertEqual(([], 0), self.views.get_all_utilbills_json(
            '99999', 0, 30))

        # it should not be possible to create an account that already
        # exists
        self.assertRaises(ValueError, self.reebill_processor.create_new_account,
            '88888', 'New Account', 'pv', 0.6, 0.2,
            billing_address, service_address, '99999', '12345', 'test')

        # try creating another account when the template account has no
        # utility bills yet
        self.reebill_processor.create_new_account(
            '77777', 'New Account','thermal', 0.6, 0.2, billing_address,
            service_address, '88888', '12345', 'test')
        self.reebill_processor.create_new_account(
            '66666', 'New Account', 'thermal', 0.6, 0.2, billing_address,
            service_address, '77777', '12345', 'test')

        # Try creating a reebill for a new account that has no utility bills
        # uploaded yet
        self.assertRaises(NoResultFound, self.reebill_processor.roll_reebill,
                          '777777', start_date=date(2013, 2, 1))


    def test_update_utilbill_metadata(self):
        utilbill = self.utilbill_processor.upload_utility_bill(
            '99999', StringIO('January 2013'), date(2013, 1, 1),
            date(2013, 2, 1), 'Gas', total=100)

        # NOTE: UtilBill.date_modified gets updated when SQLAlchemy updates
        # the object in the database, so it can't be tested in a unit test
        # that only changes data in memory. it would be good to test the
        # date_modified feature apart from the unrelated stuff in this test,
        # but this works.
        date_modified = utilbill.date_modified

        doc = self.views.get_all_utilbills_json('99999', 0, 30)[0][0]
        assert utilbill.period_start == doc['period_start'] == date(2013, 1,
                                                                    1)
        assert utilbill.period_end == doc['period_end'] == date(2013, 2, 1)
        assert utilbill.get_service().lower() == doc['service'].lower() == 'gas'
        assert utilbill.utility.name == doc['utility']['name'] == \
               'Test Utility Company Template'
        assert utilbill.target_total == 100
        assert utilbill.rate_class.name == doc['rate_class'] == \
               'Test Rate Class Template'

        # invalid date ranges
        self.assertRaises(ValueError,
                          self.utilbill_processor.update_utilbill_metadata,
                          utilbill.id, period_start=date(2014, 1, 1))
        self.assertRaises(ValueError,
                          self.utilbill_processor.update_utilbill_metadata,
                          utilbill.id, period_end=date(2012, 1, 1))
        self.assertRaises(ValueError,
                          self.utilbill_processor.update_utilbill_metadata,
                          utilbill.id, period_end=date(2014, 2, 1))

        #since the updates to utilbill fialed, date_modified should be the old one
        self.assertEqual(utilbill.date_modified, date_modified)

        # change start date
        # TODO: this fails to actually move the file because
        # get_utilbill_file_path, called by move_utilbill, is using the
        # UtilBill object, whose date attributes have not been updated
        # yet. it should start passing when the file's old path and the
        # new it's path are the same.
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                              period_start=date(2013, 1, 2))
        # the date_modified should have been updated
        self.assertNotEqual(utilbill.date_modified, date_modified)
        # utibill.date_modified must be greater than old value of
        # date_modified
        self.assertGreater(utilbill.date_modified, date_modified)

        self.assertEqual(date(2013, 1, 2), utilbill.period_start)

        # check that file really exists at the expected path
        # (get_utilbill_file_path also checks for existence)
        key_name = self.billupload.get_key_name_for_utilbill(utilbill)
        key_obj = self.billupload._get_amazon_bucket().get_key(key_name)
        self.assertEqual('January 2013', key_obj.get_contents_as_string())

        # change end date
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                              period_end=date(2013, 2, 2))
        self.assertEqual(date(2013, 2, 2), utilbill.period_end)

        # change service
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                              service='electric')
        self.assertEqual('electric', utilbill.get_service())

        # change supply_choice_id
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                              supply_choice_id='some choice id')
        self.assertEqual('some choice id', utilbill.supply_choice_id)

        # change "total" aka "total_charges"
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                              target_total=200)
        self.assertEqual(200, utilbill.target_total)
        # NOTE "total" is not in utility bill Mongo documents, only MySQL

        # change supplier
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                              supplier='some supplier')
        self.assertEqual('some supplier', utilbill.supplier.name)

        # change processed state
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                                         processed=False)
        self.assertEqual(False, utilbill.processed)
        self.utilbill_processor.update_utilbill_metadata(utilbill.id,
                                                         processed=True)
        self.assertEqual(True, utilbill.processed)

    def test_update_account_number(self):
        s = Session()
        utility = Utility(name='utility', address=Address())
        supplier = Supplier(name='supplier', address=Address())
        utility_account = UtilityAccount('someone', '1000001',
                utility, supplier,
                RateClass(name='rate class', utility=utility, service='gas'),
                Address(), Address())
        s.add(utility_account)
        s.commit()
        self.utilbill_processor.update_utility_account_number(utility_account.id, 12345)
        self.assertEqual(utility_account.account_number, 12345)


    def test_upload_utility_bill(self):
        '''Tests saving of utility bills in database (which also belongs partly
        to ReeBillDAO); does not test saving of utility bill files (which belongs
        to BillFileHandler).'''
        account = '99999'

        s = Session()
        utility_account = s.query(UtilityAccount).filter_by(account=account).one()

        # validation of dates
        bad_dates = [
            (date(2000,1,1), date(2000,1,1,)),
            (date(2000,1,1), date(2001,1,2,)),
            ]
        for start, end in bad_dates:
            with self.assertRaises(ValueError):
                self.utilbill_processor.upload_utility_bill(account, StringIO(), start,
                                                 end, 'electric',
                    utility=utility_account.fb_utility.name, supplier=utility_account.fb_supplier.name,
                    rate_class='Residential-R')

        # one utility bill
        # service, utility, rate_class are different from the template
        # account
        utilbill_path = join(dirname(realpath(__file__)), 'data',
                             'utility_bill.pdf')

        with open(utilbill_path) as file1:
            # store args for this utilbill to be re-used below
            args = [account, file1, date(2012, 1, 1), date(2012, 2, 1),
                    'electric']
            kwargs = dict(utility='pepco', rate_class='Residential-R',
                          supplier='supplier')

            self.utilbill_processor.upload_utility_bill(*args, **kwargs)

            # exception should be raised if the same file is re-uploaded
            # (regardless of other parameters)
            file1.seek(0)
            with self.assertRaises(DuplicateFileError):
                self.utilbill_processor.upload_utility_bill(*args, **kwargs)
            file1.seek(0)
            with self.assertRaises(DuplicateFileError):
                self.utilbill_processor.upload_utility_bill(
                    '100000', file1, date(2015, 1, 2),
                    date(2015, 1, 31), 'Gas', total=100)

            # save file contents to compare later
            file1.seek(0)
            file_content = file1.read()

        utilbills_data, count = self.views.get_all_utilbills_json(account,
                                                                    0, 30)
        self.assertEqual(1, count)
        self.assertDictContainsSubset({
            'state': 'Final',
            'service': 'Gas',
            'utility': column_dict(self.views.get_utility('pepco')),
            'supplier': self.views.get_supplier('supplier').name,
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
        charges = self.views.get_utilbill_charges_json(
            utilbills_data[0]['id'])
        self.assertEqual([], charges)

        # check that the file is accessible
        url = utilbills_data[0]['pdf_url']
        response = requests.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(file_content, response.content)

        # second bill: default utility and rate class are chosen
        # when those arguments are not given, and non-standard file
        # extension is used
        file2 = StringIO('Another bill file')
        self.utilbill_processor.upload_utility_bill(account, file2, date(2012, 2, 1),
                                         date(2012, 3, 1), 'electric',
                                         utility='pepco',
                                         supplier='supplier')
        utilbills_data, _ = self.views.get_all_utilbills_json(account, 0, 30)
        dictionaries = [{
                            'state': 'Final',
                            'service': 'Gas',
                            'utility':
                                column_dict(self.views.get_utility('pepco')),
                            'supplier': self.views.
                                get_supplier('supplier').name,
                            'period_start': date(2012, 2, 1),
                            'period_end': date(2012, 3, 1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }, {
                            'state': 'Final',
                            'service': 'Gas',
                            'utility': column_dict(self.views.
                                get_utility('pepco')),
                            'supplier': self.views.
                                get_supplier('supplier').name,
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
        self.utilbill_processor.upload_utility_bill(account, None, date(2012, 3, 1),
                                         date(2012, 4, 1), 'gas',
                                         utility='washgas',
                                         rate_class='DC Non Residential Non Heat',
                                         state=UtilBill.Estimated,
                                         supplier='supplier')
        utilbills_data, _ = self.views.get_all_utilbills_json(account, 0,
                                                                30)
        dictionaries = [{
                            'state': 'Estimated',
                            'service': 'Gas',
                            'utility': column_dict(self.views.
                                get_utility('washgas')),
                            'supplier': self.views.
                                get_supplier('supplier').name,
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
                            'service': 'Gas',
                            'utility': column_dict(self.views.
                                get_utility('pepco')),
                            'supplier': self.views.
                                get_supplier('supplier').name,
                            'period_start': date(2012, 2, 1),
                            'period_end': date(2012, 3, 1),
                            'total_charges': 0,
                            'computed_total': 0,
                            'processed': 0,
                            'account': '99999',
                            'reebills': [],
                            }, {
                            'state': 'Final',
                            'service': 'Gas',
                            'utility': column_dict(self.views.
                                get_utility('pepco')),
                            'supplier': self.views.
                                get_supplier('supplier').name,
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

        # 4th bill: utility and rate_class will be taken from the last bill,
        # regardless of service.
        last_bill_id = utilbills_data[0]['id']
        file4 = StringIO('Yet another file')
        self.utilbill_processor.upload_utility_bill(account, file4, date(2012, 4, 1),
                                         date(2012, 5, 1), 'electric')

        utilbills_data, count = self.views.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(4, count)
        last_utilbill = utilbills_data[0]
        self.assertDictContainsSubset(
            {
                'state': 'Final',
                'service': 'Gas',
                'utility': column_dict(self.views.get_utility('washgas')),
                'supplier': self.views.get_supplier('supplier').name,
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
            u = Session().query(UtilBill).filter_by(id=id).one()
            if state == 'Final':
                key_name = self.billupload.get_key_name_for_utilbill(u)
                key_obj = self.billupload._get_amazon_bucket().get_key(key_name)
                key_obj.get_contents_as_string()

        # delete utility bills
        ids = [obj['id'] for obj in utilbills_data]

        self.utilbill_processor.delete_utility_bill_by_id(ids[3])
        _, count = self.views.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(3, count)

        self.utilbill_processor.delete_utility_bill_by_id(ids[2])
        _, count = self.views.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(2, count)

        self.utilbill_processor.delete_utility_bill_by_id(ids[1])
        _, count = self.views.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(1, count)

        self.utilbill_processor.delete_utility_bill_by_id(ids[0])
        _, count = self.views.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(0, count)

    def test_upload_uility_bill_without_reg_total(self):
        '''Check that a total register is added to new bills
        even though some old bills don't have it.
        '''
        account = '99999'
        s = Session()

        files = [StringIO(c) for c in 'abc']

        # upload a first utility bill to serve as the "predecessor" for the
        # next one. this will have only a demand register called so
        # the total register is missing
        self.utilbill_processor.upload_utility_bill(
            account, files.pop(), date(2012, 1, 1), date(2012, 2, 1), 'electric',
            utility='pepco', rate_class='Residential-R', supplier='supplier')
        u = s.query(UtilBill).join(UtilityAccount).filter(UtilityAccount.account == account).one()
        while len(u.registers) > 0:
            del u.registers[0]
        u.registers = [Register(Register.DEMAND, 'MMBTU')]
        self.assertEqual({Register.DEMAND},
                         {r.register_binding for r in u.registers})

        for service, energy_unit in [('gas', 'therms'), ('electric', 'kWh')]:
            # the next utility bill will still have the total register (in addition to demand),
            # and its unit will be 'energy_unit'
            self.utilbill_processor.upload_utility_bill(
                account, files.pop(), date(2012, 2, 1), date(2012, 3, 1), service,
                utility='pepco', rate_class='Residential-R', supplier='supplier')
            u = s.query(UtilBill).join(UtilityAccount).filter(
                UtilityAccount.account == account).order_by(
                desc(UtilBill.period_start)).first()
            self.assertEqual({Register.TOTAL, Register.DEMAND},
                             {r.register_binding for r in u.registers})
            other = next(
                r for r in u.registers if r.register_binding == Register.DEMAND)
            self.assertEqual('MMBTU', other.unit)
            # NOTE: total register unit is determined by service, not unit in
            # previous bill
            s.delete(u)
            s.flush()

    def test_create_utility_bill_for_existing_file(self):
        account = '99999'

        # file is assumed to already exist in S3, so put it there
        file = StringIO('example')
        file_hash = self.utilbill_processor.bill_file_handler._compute_hexdigest(file)
        s = Session()
        customer = s.query(UtilityAccount).filter_by(account=account).one()
        self.utilbill_processor.bill_file_handler.upload_file(file)

        utility = s.query(Utility).first()
        utility_account = s.query(UtilityAccount).first()
        self.utilbill_processor.create_utility_bill_with_existing_file(
            utility_account, utility, file_hash)

        data, count = self.views.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(1, count)
        self.assertDictContainsSubset({
            'state': 'Final',
            'service': 'Gas',
            'utility': column_dict(customer.fb_utility),
            'supplier': customer.fb_supplier.name,
            'rate_class': customer.fb_rate_class.name,
            'period_start': None,
            'period_end': None,
            'total_charges': 0,
            'computed_total': 0,
            'processed': 0,
            'account': '99999',
            'reebills': []
        }, data[0])

        # exception should be raised if the same file is re-uploaded
        # (regardless of other parameters)
        with self.assertRaises(DuplicateFileError):
            self.utilbill_processor.create_utility_bill_with_existing_file(
                utility_account, utility, file_hash)
        other_account = Session().query(UtilityAccount).filter(
            UtilityAccount.id != utility_account.id).first()
        with self.assertRaises(DuplicateFileError):
            self.utilbill_processor.create_utility_bill_with_existing_file(
                other_account, utility, file_hash)

        # here's another bill for the same account. this time more than the
        # minimal set of arguments is given.
        file = StringIO('example 2')
        file_hash = self.utilbill_processor.bill_file_handler._compute_hexdigest(file)
        s = Session()
        customer = s.query(UtilityAccount).filter_by(account=account).one()
        self.utilbill_processor.bill_file_handler.upload_file(file)
        the_address = Address(addressee='Nextility Inc.',
                              street='1606 20th St.',
                              city='Washington', state='DC',
                              postal_code='20009')
        utilbill \
            = self.utilbill_processor.create_utility_bill_with_existing_file(
            utility_account, utility, file_hash,
            # TODO: add due date
            #due_date=datetime(2000,1,1),
            target_total=100, service_address=the_address)
        # the only one of these arguments that is visible in the UI is "total"
        data, count = self.views.get_all_utilbills_json(account, 0, 30)
        self.assertEqual(2, count)
        self.assertDictContainsSubset({
                                          'state': 'Final',
                                          'service': 'Gas',
                                          'utility': column_dict(customer.fb_utility),
                                          'supplier': customer.fb_supplier.name,
                                          'rate_class': customer.fb_rate_class.name,
                                          'period_start': None,
                                          'period_end': None,
                                          'total_charges': 100,
                                          'computed_total': 0,
                                          'processed': 0,
                                          'account': '99999',
                                          'reebills': []
                                      }, data[1])
        self.assertEqual(100, utilbill.target_total)
        self.assertEqual(the_address, utilbill.service_address)

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

        self.reebill_processor.create_new_account(
            acc_a, 'Customer A', 'thermal', .12, .34, billing_address,
            service_address, '100001', '12345', 'test')
        self.reebill_processor.create_new_account(
            acc_b, 'Customer B', 'thermal', .12, .34, billing_address,
            service_address, '100001', '12345', 'test')
        self.reebill_processor.create_new_account(
            acc_c, 'Customer C', 'thermal', .12, .34, billing_address,
            service_address, '100001', '12345', 'test')

        # new customers also need to be in nexus for
        # 'update_renewable_readings' to
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
        self.utilbill_processor.upload_utility_bill(acc_a, StringIO('January 2000 A'),
                                         date(2000, 1, 1), date(2000, 2, 1),
                                         'gas', total=0,
                                         state=UtilBill.Complete)
        self.utilbill_processor.upload_utility_bill(acc_b, StringIO('January 2000 B'),
                                         date(2000, 1, 1), date(2000, 2, 1),
                                         'gas', total=0,
                                         state=UtilBill.Complete)
        self.utilbill_processor.upload_utility_bill(acc_c, StringIO('January 2000 C'),
                                         date(2000, 1, 1), date(2000, 2, 1),
                                         'gas', total=0,
                                         state=UtilBill.Complete)

        id_a = next(obj['id'] for obj in
                    self.views.get_all_utilbills_json(
            acc_a, 0, 30)[0])
        id_b = next(obj['id'] for obj in
                    self.views.get_all_utilbills_json(
            acc_b, 0, 30)[0])
        id_c = next(obj['id'] for obj in
                    self.views.get_all_utilbills_json(
            acc_c, 0, 30)[0])

        # UPRSs of all 3 bills will be empty.
        # insert some RSIs into them. A gets only one
        # RSI, SYSTEM_CHARGE, while B and C get two others,
        # DISTRIBUTION_CHARGE and PGC.
        self.utilbill_processor.add_charge(id_a)
        self.utilbill_processor.add_charge(id_a)
        self.utilbill_processor.update_charge({
                                       'rsi_binding': 'SYSTEM_CHARGE',
                                       'description': 'System Charge',
                                       'quantity_formula': '1',
                                       'rate': 11.2,
                                       'shared': True,
                                       }, utilbill_id=id_a, rsi_binding='New Charge 1')
        self.utilbill_processor.update_charge({
                                       'rsi_binding': 'NOT_SHARED',
                                       'description': 'System Charge',
                                       'quantity_formula': '1',
                                       'rate': 3,
                                       'shared': False,
                                       }, utilbill_id=id_a, rsi_binding='New Charge 2')
        for i in (id_b, id_c):
            self.utilbill_processor.add_charge(i)
            self.utilbill_processor.add_charge(i)
            self.utilbill_processor.update_charge({
                                           'rsi_binding': 'DISTRIBUTION_CHARGE',
                                           'description': 'Distribution charge for all therms',
                                           'quantity_formula': '750.10197727',
                                           'rate': 220.16,
                                           'shared': True,
                                           }, utilbill_id=i, rsi_binding='New Charge 1')
            self.utilbill_processor.update_charge({
                                           'rsi_binding': 'PGC',
                                           'description': 'Purchased Gas Charge',
                                           'quantity_formula': '750.10197727',
                                           'rate': 0.7563,
                                           'shared': True,
                                           }, utilbill_id=i, rsi_binding='New Charge 2')

        # create utility bill and reebill #2 for A
        self.utilbill_processor.upload_utility_bill(acc_a, StringIO('February 2000 A'),
                                         date(2000, 2, 1), date(2000, 3, 1),
                                         'gas', total=0,
                                         state=UtilBill.Complete)
        id_a_2 = [obj for obj in self.views.get_all_utilbills_json(
            acc_a, 0, 30)][0][0]['id']

        # initially there will be no RSIs in A's 2nd utility bill, because
        # there are no "processed" utility bills yet.
        self.assertEqual([], self.views.get_utilbill_charges_json(id_a_2))

        # when the other bills have been marked as "processed", they should
        # affect the new one.
        self.utilbill_processor.update_utilbill_metadata(id_a, processed=True)
        self.utilbill_processor.update_utilbill_metadata(id_b, processed=True)
        self.utilbill_processor.update_utilbill_metadata(id_c, processed=True)
        self.utilbill_processor.regenerate_charges(id_a_2)
        # the UPRS of A's 2nd bill should now match B and C, i.e. it
        # should contain DISTRIBUTION and PGC and exclude SYSTEM_CHARGE,
        # because together the other two have greater weight than A's
        # reebill #1. it should also contain the NOT_SHARED RSI because
        # un-shared RSIs always get copied from each bill to its successor.
        self.assertEqual(set(['DISTRIBUTION_CHARGE', 'PGC', 'NOT_SHARED']),
                         set(r['rsi_binding'] for r in
                             self.views.get_utilbill_charges_json(id_a_2)))

        # now, modify A-2's UPRS so it differs from both A-1 and B/C-1. if
        # a new bill is rolled, the UPRS it gets depends on whether it's
        # closer to B/C-1 or to A-2.
        s = Session()
        utilbill_a_2 = s.query(UtilBill).filter_by(id=id_a_2).one()
        dc_id = utilbill_a_2.get_charge_by_rsi_binding('DISTRIBUTION_CHARGE').id
        pgc_id = utilbill_a_2.get_charge_by_rsi_binding('PGC').id
        not_shared_id = utilbill_a_2.get_charge_by_rsi_binding('NOT_SHARED').id
        self.utilbill_processor.delete_charge(dc_id)
        self.utilbill_processor.delete_charge(pgc_id)
        self.utilbill_processor.delete_charge(not_shared_id)
        Session().flush()
        self.utilbill_processor.add_charge(id_a_2)
        self.utilbill_processor.update_charge(
            {
                'rsi_binding': 'RIGHT_OF_WAY',
                'description': 'DC Rights-of-Way Fee',
                'quantity_formula': '750.10197727',
                'rate': 0.03059,
                'shared': True
            }, utilbill_id=id_a_2, rsi_binding='New Charge 1')

        # create B-2 with period 2-5 to 3-5, closer to A-2 than B-1 and C-1.
        # the latter are more numerous, but A-1 should outweigh them
        # because weight decreases quickly with distance.
        self.utilbill_processor.upload_utility_bill(
            acc_b, StringIO('February 2000 B'), start=date(2000, 2, 5),
            end=date(2000, 3, 5), service='gas')
        self.assertEqual(set(['RIGHT_OF_WAY']),
                         set(r['rsi_binding'] for r in
                             self.views.get_utilbill_charges_json(id_a_2)))

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
        self.utilbill_processor.upload_utility_bill('99999',
            StringIO('A Water Bill'), date(2013, 5, 6), date(2013, 7, 8), 'gas',
            utility='washgas', rate_class='Test Rate Class Template')
        utilbill_data = self.views.get_all_utilbills_json(
            '99999', 0, 30)[0][0]
        self.assertDictContainsSubset({'account': '99999', 'computed_total': 0,
                                       'period_end': date(2013, 7, 8),
                                       'period_start': date(2013, 5, 6),
                                       'processed': 0,
                                       'rate_class': self.views.get_rate_class(
                                           'Test Rate Class Template').name,
                                       'reebills': [], 'service': 'Gas',
                                       'state': 'Final', 'total_charges': 0.0,
                                       'utility': column_dict(
                                           self.views.get_utility(
                                               'washgas')), }, utilbill_data)

        self.utilbill_processor.update_utilbill_metadata(utilbill_data['id'],
                                                         processed=True)
        # no other attributes of a utilbill can be changed if
        # update_utilbill_metadata is called with processed = True
        s = Session()
        utilbill = s.query(UtilBill).filter_by(id=utilbill_data['id']).one()
        self.assertEqual('Test Supplier', utilbill.supplier.name)
        self.assertRaises(UnEditableBillError,
                          self.utilbill_processor.add_charge,
                          utilbill_data['id'])
        self.utilbill_processor.update_utilbill_metadata(utilbill_data['id'],
                                                         processed=False)

        self.utilbill_processor.add_charge(utilbill_data['id'])
        self.utilbill_processor.update_charge({
                                       'rsi_binding': 'A',
                                       'description':'UPRS only',
                                       'quantity_formula': '2',
                                       'rate': 3,
                                       'unit':'kWh'
                                   },
                                   utilbill_id=utilbill_data['id'],
                                   rsi_binding='New Charge 1')

        self.utilbill_processor.add_charge(utilbill_data['id'])
        self.utilbill_processor.update_charge({
                                       'rsi_binding': 'B',
                                       'description':'not shared',
                                       'quantity_formula': '6',
                                       'rate': 7,
                                       'unit':'therms',
                                       'shared': False},
            utilbill_id=utilbill_data['id'], rsi_binding='New Charge 1')

        # compute_utility_bill should update the document to match
        self.utilbill_processor.compute_utility_bill(utilbill_data['id'])
        charges = self.views.get_utilbill_charges_json(utilbill_data['id'])

        # check charges
        # NOTE if the commented-out lines are added below the test will
        # fail, because the charges are missing those keys.
        for x, y in zip([
                            {
                                'rsi_binding': 'A',
                                'quantity': 2,
                                'unit': 'kWh',
                                'rate': 3,
                                'total': 6,
                                'description': 'UPRS only',
                                'error': None,
                                }, {
                                'rsi_binding': 'B',
                                'quantity': 6,
                                'unit': 'therms',
                                'rate': 7,
                                'total': 42,
                                'description': 'not shared',
                                'error': None,
                                },
                            ], charges):
            self.assertDictContainsSubset(x, y)
        self.utilbill_processor.update_utilbill_metadata(
            utilbill_data['id'], supplier='some supplier')
        self.utilbill_processor.update_utilbill_metadata(utilbill_data['id'],
                                                         processed=True)
        self.assertRaises(UnEditableBillError,
                          self.utilbill_processor.update_charge,
                          {'rsi_binding': 'C', 'description': 'not shared',
                           'quantity_formula': '6', 'rate': 7, 'unit': 'therms',
                           'shared': False}, utilbill_id=utilbill_data['id'],
                          rsi_binding='B')

    def test_compute_realistic_charges(self):
        '''Tests computing utility bill charges and reebill charge for a
        reebill based on the utility bill, using a set of charge from an actual
        bill.
        '''
        account = '99999'
        # create utility bill and reebill
        self.utilbill_processor.upload_utility_bill(
            account, StringIO('January 2012'), date(2012, 1, 1),
            date(2012, 2, 1), 'gas')
        utilbill_id = self.views.get_all_utilbills_json(
            account, 0, 30)[0][0]['id']

        formula = Charge.get_simple_formula(Register.TOTAL)
        example_charge_fields = [
            dict(rate=23.14,
                 rsi_binding='PUC',
                 description='Peak Usage Charge',
                 quantity_formula='1'),
            dict(rate=0.03059,
                 rsi_binding='RIGHT_OF_WAY',
                 roundrule='ROUND_HALF_EVEN',
                 quantity_formula=formula),
            dict(rate=0.01399,
                 rsi_binding='SETF',
                 roundrule='ROUND_UP',
                 quantity_formula=formula),
            dict(rsi_binding='SYSTEM_CHARGE',
                 rate=11.2,
                 quantity_formula='1'),
            dict(rsi_binding='DELIVERY_TAX',
                 rate=0.07777,
                 unit='therms',
                 quantity_formula=formula),
            dict(rate=.2935,
                 rsi_binding='DISTRIBUTION_CHARGE',
                 roundrule='ROUND_UP',
                 quantity_formula=formula),
            dict(rate=.7653,
                 rsi_binding='PGC',
                 quantity_formula=formula),
            dict(rate=0.006,
                 rsi_binding='EATF',
                 quantity_formula=formula),
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
            self.utilbill_processor.add_charge(utilbill_id)
            self.utilbill_processor.update_charge(fields,
                                                  utilbill_id=utilbill_id,
                                                  rsi_binding="New Charge 1")

        # ##############################################################
        # check that each actual (utility) charge was computed correctly:
        quantity = self.views.get_registers_json(
            utilbill_id)[0]['quantity']
        actual_charges = self.views.get_utilbill_charges_json(utilbill_id)

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
        self.assertEqual(
            round(0.06 * sum(map(get_total, non_tax_rsi_bindings)), 2),
            get_total('SALES_TAX'))

    def test_delete_utility_bill_with_reebill(self):
        account = '99999'
        start, end = date(2012, 1, 1), date(2012, 2, 1)
        # create utility bill in MySQL, Mongo, and filesystem (and make
        # sure it exists all 3 places)
        u = self.utilbill_processor.upload_utility_bill(
            account, StringIO( "test1"), start, end, 'gas')
        utilbills_data, count = self.views.get_all_utilbills_json(
            account, 0, 30)
        self.assertEqual(1, count)

        u.set_processed(True)

        # when utilbill is attached to reebill, deletion should fail
        self.reebill_processor.roll_reebill(account, start_date=start)
        reebills_data = self.views.get_reebill_metadata_json(account)
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
                                          'ree_quantity': 22.602462036826555,
                                          'ree_value': 0,
                                          'sequence': 1,
                                          'services': [],
                                          'total_adjustment': 0,
                                          'total_error': 0.0
                                      }, reebills_data[0])
        self.assertRaises(BillingError,
                          self.utilbill_processor.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])

        # deletion should fail if any version of a reebill has an
        # association with the utility bill. so issue the reebill, add
        # another utility bill, and create a new version of the reebill
        # attached to that utility bill instead.
        self.reebill_processor.issue(account, 1)
        self.reebill_processor.new_version(account, 1)
        u = self.utilbill_processor.upload_utility_bill(
            account, StringIO("test2"), date(2012, 2, 1), date(2012, 3, 1),
            'gas')
        self.utilbill_processor.update_utilbill_metadata(u.id, processed=True)
        # TODO this may not accurately reflect the way reebills get
        # attached to different utility bills; see
        # https://www.pivotaltracker.com/story/show/51935657
        self.assertRaises(BillingError,
                          self.utilbill_processor.delete_utility_bill_by_id,
                          utilbills_data[0]['id'])
