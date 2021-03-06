from mock import MagicMock, Mock
from sqlalchemy.inspection import inspect

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from sqlalchemy.exc import IntegrityError
from test import init_test_config
init_test_config()

from core import init_model
from core.bill_file_handler import BillFileHandler

from core.model.model import RegisterTemplate, SupplyGroup, ELECTRIC
from core.pricing import PricingModel, FuzzyPricingModel
from test import init_test_config, create_tables, clear_db

from datetime import date
from unittest import TestCase

from core.exceptions import RSIError, UnEditableBillError, NotProcessable, BillingError, \
    MissingFileError
from core.model import Session, Address, Register, Utility, Supplier, RateClass, UtilityAccount
from core.model.utilbill import UtilBill, Charge
from util.pdf import PDFUtil


class UtilBillTest(TestCase):
    """Unit tests for UtilBill.
    """
    def test_validate_utilbill_period(self):
        # valid periods
        UtilBill.validate_utilbill_period(None, None)
        UtilBill.validate_utilbill_period(date(1000,1,1), None)
        UtilBill.validate_utilbill_period(None, date(1000,1,1))
        UtilBill.validate_utilbill_period(date(2000,1,1), date(2000,1,2))
        UtilBill.validate_utilbill_period(date(2000,1,1), date(2000,12,31))

        # length < 1 day
        with self.assertRaises(ValueError):
            UtilBill.validate_utilbill_period(date(2000,1,1), date(2000,1,1))
        with self.assertRaises(ValueError):
            UtilBill.validate_utilbill_period(date(2000,1,2), date(2000,1,1))

        # length > 365 days
        with self.assertRaises(ValueError):
            UtilBill.validate_utilbill_period(date(2000,1,1), date(2001,1,2))

    def test_get_next_meter_read_date(self):
        utilbill = UtilBill(MagicMock(), MagicMock(), MagicMock())
        utilbill.period_end = date(2000,1,1)
        self.assertEqual(None, utilbill.get_next_meter_read_date())

        utilbill.set_next_meter_read_date(date(2000,2,5))
        self.assertEqual(date(2000,2,5), utilbill.get_next_meter_read_date())

    def test_get_set_total_energy(self):
        utilbill = UtilBill(MagicMock(), MagicMock(), MagicMock())

        self.assertEqual(0, utilbill.get_total_energy_consumption())

        # currently, a "REG_TOTAL" register is required to exist, but is not
        # added when a utility bill is created. this prevents
        # set_total_energy from working.
        with self.assertRaises(StopIteration):
            utilbill.set_total_energy(10)

        # when the register is present, set_total_energy should work
        # without requiring consumers to know about _registers.
        # TODO...

    def test_get_register_by_binding(self):
        utility = Utility(name='utility')
        rate_class = RateClass(utility=utility)
        bill = UtilBill(MagicMock(), utility, rate_class)
        self.assertIsInstance(bill.get_register_by_binding(Register.TOTAL),
                              Register)
        with self.assertRaises(BillingError):
            bill.get_register_by_binding('xyz')

    def test_regenerate_charges(self):
        a, b, c = Charge('a'), Charge('b'), Charge('c')

        utilbill = UtilBill(MagicMock(), None, None)
        utilbill.charges = [a]

        pricing_model = Mock(autospec=PricingModel)
        pricing_model.get_predicted_charges.return_value = [b, c]

        utilbill.regenerate_charges(pricing_model)
        self.assertEqual([b, c], utilbill.charges)
        self.assertIsNone(a.utilbill)

    def test_processed(self):
        utilbill = UtilBill(MagicMock(), None, None)
        self.assertFalse(utilbill.processed)

        # repeating the same value is OK
        utilbill.set_processed(False)
        self.assertFalse(utilbill.processed)

        # required values are missing
        self.assertFalse(utilbill.is_processable())
        with self.assertRaises(NotProcessable):
            utilbill.set_processed(True)

        # fill in missing values
        utilbill.period_start = date(2000,1,1)
        utilbill.period_end = date(2000,2,1)
        utilbill.utility = MagicMock()
        utilbill.rate_class = MagicMock()
        utilbill.supplier = MagicMock()
        utilbill.supply_group = MagicMock()
        self.assertTrue(utilbill.is_processable())

        utilbill.set_processed(True)
        self.assertTrue(utilbill.processed)

    def test_suplier_suply_group(self):
        utilbill = UtilBill(MagicMock(), None, None)
        supplier = Supplier(name='supplier')
        supply_group = SupplyGroup(supplier=supplier, name='supply group',
                               service=ELECTRIC)
        other_supplier = Supplier(name='other')

        self.assertIsNone(utilbill.get_supplier())
        self.assertIsNone(utilbill.get_supplier_name())
        self.assertIsNone(utilbill.get_supply_group())
        self.assertIsNone(utilbill.get_supply_group_name())

        utilbill.set_supplier(supplier)
        self.assertEqual(supplier, utilbill.get_supplier())
        self.assertEqual('supplier', utilbill.get_supplier_name())
        self.assertIsNone(utilbill.get_supply_group())
        self.assertIsNone(utilbill.get_supply_group_name())

        utilbill.set_supply_group(supply_group)
        self.assertIs(supplier, utilbill.get_supplier())
        self.assertEqual('supplier', utilbill.get_supplier_name())
        self.assertIs(supply_group, utilbill.get_supply_group())
        self.assertEqual('supply group', utilbill.get_supply_group_name())
        self.assertEqual(ELECTRIC, supply_group.get_service())

        # when the same supplier is set again, supply group is unchanged
        utilbill.set_supplier(supplier)
        self.assertIs(supplier, utilbill.get_supplier())
        self.assertEqual('supplier', utilbill.get_supplier_name())
        self.assertIs(supply_group, utilbill.get_supply_group())
        self.assertEqual('supply group', utilbill.get_supply_group_name())
        self.assertEqual(ELECTRIC, supply_group.get_service())

        # when a different supplier is chosen, supply group is unknown
        utilbill.set_supplier(other_supplier)
        self.assertEqual(other_supplier, utilbill.get_supplier())
        self.assertEqual('other', utilbill.get_supplier_name())
        self.assertIsNone(utilbill.get_supply_group())
        self.assertIsNone(utilbill.get_supply_group_name())


        # supplier and supply group can be set to None
        utilbill.set_supplier(None)
        utilbill.set_supply_group(None)
        self.assertIsNone(utilbill.get_supplier())
        self.assertIsNone(utilbill.get_supplier_name())
        self.assertIsNone(utilbill.get_supply_group())
        self.assertIsNone(utilbill.get_supply_group_name())
        self.assertIsNone(utilbill.get_service())

    def test_utility_rate_class(self):
        utilbill = UtilBill(MagicMock(), None, None)
        utility = Utility(name='utility')
        rate_class = RateClass(utility=utility, name='rate class',
                               service=ELECTRIC)
        other_utility = Utility(name='other')

        self.assertIsNone(utilbill.get_utility())
        self.assertIsNone(utilbill.get_utility_name())
        self.assertIsNone(utilbill.get_rate_class())
        self.assertIsNone(utilbill.get_rate_class_name())
        self.assertIsNone(utilbill.get_service())

        utilbill.set_utility(utility)
        self.assertEqual(utility, utilbill.get_utility())
        self.assertEqual('utility', utilbill.get_utility_name())
        self.assertIsNone(utilbill.get_rate_class())
        self.assertIsNone(utilbill.get_rate_class_name())
        self.assertIsNone(utilbill.get_service())

        utilbill.set_rate_class(rate_class)
        self.assertIs(utility, utilbill.get_utility())
        self.assertEqual('utility', utilbill.get_utility_name())
        self.assertIs(rate_class, utilbill.get_rate_class())
        self.assertEqual('rate class', utilbill.get_rate_class_name())
        self.assertEqual(ELECTRIC, utilbill.get_service())

        # when there's a rate class, you can get/set total energy
        utilbill.set_total_energy(1)
        self.assertEqual(1, utilbill.get_total_energy())
        self.assertEqual('kWh', utilbill.get_total_energy_unit())

        # when the same utility is set again, rate class is unchanged
        utilbill.set_utility(utility)
        self.assertIs(utility, utilbill.get_utility())
        self.assertEqual('utility', utilbill.get_utility_name())
        self.assertIs(rate_class, utilbill.get_rate_class())
        self.assertEqual('rate class', utilbill.get_rate_class_name())
        self.assertEqual(ELECTRIC, utilbill.get_service())

        # when a different utility is chosen, rate class is unknown
        utilbill.set_utility(other_utility)
        self.assertEqual(other_utility, utilbill.get_utility())
        self.assertEqual('other', utilbill.get_utility_name())
        self.assertIsNone(utilbill.get_rate_class())
        self.assertIsNone(utilbill.get_rate_class_name())
        self.assertIsNone(utilbill.get_service())

        # with no rate class, there are no _registers, so you can't set the
        # energy, but you can get it (it will always be 0)
        with self.assertRaises(StopIteration):
            utilbill.set_total_energy(1)
        self.assertEqual(0, utilbill.get_total_energy())
        self.assertEqual(None, utilbill.get_total_energy_unit())

        # utility and rate class can be set to None
        utilbill.set_utility(None)
        utilbill.set_rate_class(None)
        self.assertIsNone(utilbill.get_utility())
        self.assertIsNone(utilbill.get_utility_name())
        self.assertIsNone(utilbill.get_rate_class())
        self.assertIsNone(utilbill.get_rate_class_name())
        self.assertIsNone(utilbill.get_service())

    def test_get_text(self):
        utilbill = UtilBill(MagicMock(), None, None)
        bfh = Mock(autospec=BillFileHandler)
        pdf_util = Mock(autospec=PDFUtil)
        pdf_util.get_pdf_text.return_value = 'example text'

        # if file is missing, text is empty (and is not cached)
        bfh.write_copy_to_file.side_effect = MissingFileError
        self.assertEqual('', utilbill.get_text(bfh, pdf_util))

        # get the text
        bfh.reset_mock()
        pdf_util.reset_mock()
        bfh.write_copy_to_file.side_effect = None
        self.assertEqual('example text', utilbill.get_text(bfh, pdf_util))
        self.assertEqual(1, bfh.write_copy_to_file.call_count)
        self.assertEqual(1, pdf_util.get_pdf_text.call_count)

        # text is cached the 2nd time so methods to get the file and text are
        # not called
        bfh.reset_mock()
        pdf_util.reset_mock()
        self.assertEqual('example text', utilbill.get_text(bfh, pdf_util))
        self.assertEqual(0, bfh.write_copy_to_file.call_count)
        self.assertEqual(0, pdf_util.get_pdf_text.call_count)

    def test_has_file(self):
        # UtilBill is created with default state Complete, which means it has
        # a file. UtilityEstimated also has a file, but Estimated does not.
        utilbill = UtilBill(MagicMock(), None, None)
        self.assertEqual(UtilBill.Complete, utilbill.state)
        self.assertTrue(utilbill.has_file())
        utilbill.state = UtilBill.UtilityEstimated
        self.assertTrue(utilbill.has_file())
        utilbill.state = UtilBill.Estimated
        self.assertFalse(utilbill.has_file())

    def test_replace_estimated_with_complete(self):
        # estimated bill and real bill have different data
        est_bill = UtilBill(MagicMock(), None, None, state=UtilBill.Estimated,
                            period_start=date(2000,1,1), target_total=12.34)
        real_bill = UtilBill(MagicMock(), None, None, state=UtilBill.Complete,
                             period_start=date(2000,1,2), target_total=56.78,
                             sha256_hexdigest='abc123')
        real_bill.charges = [Charge('a', target_total=9.10)]

        # these are the attributes that will be transferred from the real
        # bill to the estimated one. must be saved in advance because some
        # child objects will be moved from one to the other rather than copied.
        attr_names = est_bill.column_names() + [
            'utility_account',
            'supplier',
            'rate_class',
            'billing_address',
            'service_address',
            'utility',
            'charges',
            '_registers',
        ]
        real_bill_data = {attr_name: getattr(real_bill, attr_name)
                          for attr_name in attr_names}

        bill_file_handler = Mock(autospec=BillFileHandler)
        est_bill.replace_estimated_with_complete(real_bill, bill_file_handler)

        # all attributes in estimated bill should match the other that were
        # originally in real bill
        for attr_name in attr_names:
            self.assertEqual(real_bill_data[attr_name],
                             getattr(est_bill, attr_name))

        # values of parent attributes should not be duplicated
        # (parents in terms of foreign keys, not in terms of which classes
        # contain have the SQLAlchemy relationship attributes defined in them)
        self.assertIs(real_bill.utility, est_bill.utility)
        self.assertIs(real_bill.rate_class, est_bill.rate_class)
        self.assertIs(real_bill.supplier, est_bill.supplier)
        self.assertIs(real_bill.supply_group, est_bill.supply_group)

        # values of child attributes should be duplicated
        self.assertEqual(len(est_bill.charges), len(real_bill.charges))
        for c1, c2 in zip(est_bill.charges, real_bill.charges):
            self.assertEqual(c1, c2)
            self.assertIsNot(c1, c2)
        self.assertEqual(len(est_bill._registers), len(real_bill._registers))
        for r1, r2 in zip(est_bill._registers, real_bill._registers):
            self.assertEqual(r1, r2)
            self.assertIsNot(r1, r2)
        self.assertEqual(est_bill.billing_address, real_bill.billing_address)
        self.assertEqual(est_bill.service_address, real_bill.service_address)
        self.assertIsNot(est_bill.billing_address, real_bill.billing_address)
        self.assertIsNot(est_bill.service_address, real_bill.service_address)


class UtilBillTestWithDB(TestCase):
    """Tests for UtilBill that require the database.
    """
    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()

    def setUp(self):
        clear_db()
        self.supplier = Supplier(name='supplier', address=Address())
        self.utility = Utility(name='utility', address=Address())

        self.utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass(name='FB Test Rate Class', utility=self.utility,
                      service='gas'), Address(), Address())
        self.rate_class = RateClass(name='rate class', utility=self.utility,
                                    service='gas')

    def tearDown(self):
        Session.remove()

    def assert_error(self, c, error_message):
        '''Assert that the Charge 'c' has None for its quantity/rate/total
        and 'error_message' in its 'error' field.
        '''
        self.assertIsNone(c.quantity)
        self.assertIsNone(c.total)
        self.assertIsNotNone(c.error)
        self.assertEqual(error_message, c.error)

    def assert_charge_values(self, quantity, rate, c):
        '''Assert that the charge 'c' has the given quantity and rate,
        total = quantity * rate, and no error.
        '''
        self.assertEqual(quantity, c.quantity)
        self.assertEqual(rate, c.rate)
        self.assertEqual(quantity * rate, c.total)
        self.assertEqual(None, c.error)

    def test_charge_relationship(self):
        utilbill = UtilBill(self.utility_account, self.utility, self.rate_class)
        a, b = Charge('a', unit='kWh'), Charge('b', unit='kWh')
        s = Session()
        s.add(utilbill)

        # any charge associated with 'utilbill' gets added to the session,
        # and any charge not associated with it gets removed
        utilbill.charges = [a]
        utilbill.charges = [b]

        # if the UtilBill-Charge relationship has the wrong cascade setting,
        # this flush will fail with a constraint violation when it tries to
        # save 'a'
        s.flush()

        # 'a' should have been deleted when it was removed from the list of
        # charges, so 'b' is the only charge left in the database
        self.assertEqual(1, s.query(Charge).count())

    def test_invalid_utilbill_dates(self):
        supplier = Supplier(name='supplier', address=Address())
        utility = Utility(name='utility', address=Address())
        utility_account = UtilityAccount(
            'someone', '98989', utility, supplier,
            RateClass(name='FB Test Rate Class', utility=utility,
                      service='gas'), Address(), Address())
        utilbill = UtilBill(utility_account, utility,
                            RateClass(name='rate class', utility=utility,
                                      service='gas'),
                            supplier=supplier,
                            period_start=date(0215, 01, 01),
                            period_end=date(0215, 02, 01))
        utilbill.set_next_meter_read_date(date(0215, 01, 01))
        Session().add(utilbill)
        # flushing the changes should through integrity error as the dates
        # entered for period_start, period_end and next_meter_read_date
        # violates the defined column check constraint that checks date >
        # 1900-01-01
        self.assertRaises(IntegrityError, Session().flush)
        utilbill.set_next_meter_read_date(date(2000,02,01))
        utilbill.period_start = date(2000, 01, 01)
        utilbill.period_end = date(2000, 02, 01)
        # Since the dates entered for period_start, period_end and
        # next_meter_read_date don't violate the check constraint, flushing
        # changes should succeed
        Session().flush()

    def test_processed_editable(self):
        utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass(name='FB Test Rate Class', utility=self.utility,
                      service='gas'), None, Address(), Address())
        utilbill = UtilBill(utility_account, self.utility,
                            RateClass(name='rate class', utility=self.utility,
                                      service='gas'),
                            supplier=self.supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))

        self.assertFalse(utilbill.processed)
        utilbill.check_editable()

        utilbill.processed = True
        self.assertTrue(utilbill.processed)
        self.assertRaises(UnEditableBillError, utilbill.check_editable)

    def test_processable(self):
        utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass(name='FB Test Rate Class', utility=self.utility,
                      service='gas'), None, Address(), Address())
        for attr in ('period_start', 'period_end', 'rate_class', 'utility',
                     'supplier'):
            ub = UtilBill(
                utility_account, self.utility,
                RateClass(name='rate class', utility=self.utility,
                        service='gas'),
                supplier=self.supplier,
                period_start=date(2000, 1, 1), period_end=date(2000, 2, 1))
            setattr(ub, attr, None)
            self.assertRaises(NotProcessable, ub.check_processable)

        ub = UtilBill(utility_account, self.utility,
                      RateClass(name='rate class', utility=self.utility,
                                service='gas'), supplier=self.supplier,
                      period_start=date(2000, 1, 1),
                      period_end=date(2000, 2, 1),
                      supply_group='test')

    def test_add_charge(self):
        utility_account = UtilityAccount(
            'someone', '98989', self.utility, self.supplier,
            RateClass(name='FB Test Rate Class', utility=self.utility,
                      service='gas'),
            Address(), Address())
        rate_class = RateClass(name='rate class', utility=self.utility,
                               service='gas')
        rate_class.register_templates = [
            RegisterTemplate(register_binding=Register.TOTAL, unit='therms'),
            RegisterTemplate(register_binding=Register.DEMAND, unit='kWD')]
        utilbill = UtilBill(utility_account, self.utility,
                            rate_class, supplier=self.supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        assert len(utilbill._registers) == 2

        session = Session()
        session.add(utilbill)
        session.flush()

        formula = Charge.get_simple_formula(Register.TOTAL)
        fpm = Mock(autospec=FuzzyPricingModel)
        fpm.get_closest_occurrence_of_charge.return_value = Charge(
            "rsi_binding does't matter", formula=formula, rate=1.234)
        charge = utilbill.add_charge({})
        self.assertEqual(formula, charge.quantity_formula)

        session.delete(charge)

    def test_compute(self):
        fb_utility = Utility(name='FB Test Utility', address=Address())
        utility = Utility(name='utility', address=Address())
        utilbill = UtilBill(
            UtilityAccount('someone', '98989', fb_utility, 'FB Test Supplier',
                           RateClass(name='FB Test Rate Class',
                                     utility=fb_utility, service='gas'),
                           None, Address(), Address()), utility,
            RateClass(name='rate class', utility=utility, service='gas'),
            supplier=Supplier(name='supplier', address=Address()),
            period_start=date(2000, 1, 1), period_end=date(2000, 2, 1))
        register = Register(Register.TOTAL, 'therms', quantity=150)
        utilbill._registers = [register]
        charges = [
            dict(
                rsi_binding='CONSTANT',
                formula='100',
                quantity_units='dollars',
                rate=0.4,
            ),
            dict(
                rsi_binding='LINEAR',
                formula='REG_TOTAL.quantity * 3',
                quantity_units='therms',
                rate=0.1,
            ),
            dict(
                rsi_binding='LINEAR_PLUS_CONSTANT',
                formula='REG_TOTAL.quantity * 2 + 10',
                quantity_units='therms',
                rate=0.1,
            ),
            dict(
                rsi_binding='BLOCK_1',
                formula='min(100, REG_TOTAL.quantity)',
                quantity_units='therms',
                rate=0.3,
            ),
            dict(
                rsi_binding='BLOCK_2',
                formula='min(200, max(0, REG_TOTAL.quantity - 100))',
                quantity_units='therms',
                rate=0.2,
            ),
            dict(
                rsi_binding='BLOCK_3',
                formula='max(0, REG_TOTAL.quantity - 200)',
                quantity_units='therms',
                rate=0.1,
            ),
            dict(
                rsi_binding='REFERENCES_ANOTHER',
                # TODO also try "total" here
                formula='REFERENCED_BY_ANOTHER.quantity + '
                         'REFERENCED_BY_ANOTHER.rate',
                quantity_units='therms',
                rate=1,
            ),
            dict(
                rsi_binding='NO_CHARGE_FOR_THIS_RSI',
                formula='1',
                quantity_units='therms',
                rate=1,
            ),
            # this RSI has no charge associated with it, but is used to
            # provide identifiers in the formula of the "REFERENCES_ANOTHER"
            # RSI in 'uprs'
            dict(
                rsi_binding='REFERENCED_BY_ANOTHER',
                formula='2',
                quantity_units='therms',
                rate=3,
            ),
            dict(
                rsi_binding='SYNTAX_ERROR',
                formula='5 + ',
                quantity_units='therms',
                rate=1,
            ),
            dict(
                rsi_binding='DIV_BY_ZERO_ERROR',
                formula='1 / 0',
                quantity_units='therms',
                rate=1,
            ),
            # shows that quantity formula error takes priority over rate
            # formula error
            dict(
                rsi_binding='UNKNOWN_IDENTIFIER',
                formula='x * 2',
                quantity_units='therms',
                rate=1,
            ),
        ]
        utilbill.charges = [Charge(c['rsi_binding'], rate=c['rate'],
                formula=c['formula'], description="Insert description here",
                unit=c['quantity_units']) for c in charges]

        get = utilbill.get_charge_by_rsi_binding

        # 'raise_exception' argument validates that all charges were computed
        # without errors. if this argument is given, all the charges without
        # errors still be correct, and the exception raised only after computing
        # all the charges
        with self.assertRaises(RSIError):
            utilbill.compute_charges(raise_exception=True)
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(450, .1, get('LINEAR'))
        self.assert_charge_values(310, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(50, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_charge_values(2, 3, get('REFERENCED_BY_ANOTHER'))
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('SYNTAX_ERROR'),
                'Syntax error')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('DIV_BY_ZERO_ERROR'),
                'Error: division by zero')
        self.assert_error(
                utilbill.get_charge_by_rsi_binding('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")

        # TODO enable when bug #76318266 is fixed
        # self.assertEqual(40 + 45 + 31 + 30 + 10 + 0 + 5 + 6,
        #         utilbill.total_charge())

        # check "total" for each of the charges in the utility bill at the
        # register quantity of 150 therms. there should not be a charge for
        # NO_CHARGE_FOR_THIS_RSI even though that RSI was in the rate
        # structure.
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(450, 0.1, get('LINEAR'))
        self.assert_charge_values(310, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(50, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(get('SYNTAX_ERROR'), 'Syntax error')
        self.assert_error(get('DIV_BY_ZERO_ERROR'), 'Error: division by zero')

        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")

        # try a different quantity: 250 therms
        register.quantity = 250
        utilbill.compute_charges()
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(750, 0.1, get('LINEAR'))
        self.assert_charge_values(510, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(100, 0.3, get('BLOCK_1'))
        self.assert_charge_values(150, 0.2, get('BLOCK_2'))
        self.assert_charge_values(50, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(get('SYNTAX_ERROR'), 'Syntax error')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")

        # and another quantity: 0
        register.quantity = 0
        utilbill.compute_charges()
        self.assert_charge_values(100, 0.4, get('CONSTANT'))
        self.assert_charge_values(0, 0.1, get('LINEAR'))
        self.assert_charge_values(10, 0.1, get('LINEAR_PLUS_CONSTANT'))
        self.assert_charge_values(0, 0.3, get('BLOCK_1'))
        self.assert_charge_values(0, 0.2, get('BLOCK_2'))
        self.assert_charge_values(0, 0.1, get('BLOCK_3'))
        self.assert_charge_values(5, 1, get('REFERENCES_ANOTHER'))
        self.assert_error(get('SYNTAX_ERROR'), 'Syntax error')
        self.assert_error(get('DIV_BY_ZERO_ERROR'),
                'Error: division by zero')
        self.assert_error(get('UNKNOWN_IDENTIFIER'),
                "Error: name 'x' is not defined")


    def test_compute_charges_empty(self):
        '''Compute utility bill with no charges.
        '''
        utility_account = UtilityAccount('someone', '99999',
                Utility(name='utility'), None,
                None, None, Address(), Address())
        utilbill = UtilBill(utility_account, None, None)
        utilbill.compute_charges()
        self.assertEqual([], utilbill.charges)
        self.assertEqual(0, utilbill.get_total_charges())

    def test_compute_charges_independent(self):
        utility = Utility(name='utility', address=Address())
        supplier = Supplier(name='supplier', address=Address())
        utility_account = UtilityAccount('someone', '99999',
                utility, supplier,
                RateClass(name='rate class', utility=utility, service='gas'),
                Address(), Address())
        utilbill = UtilBill(utility_account, utility,
                            RateClass(name='rate class', utility=utility,
                                      service='gas'), supplier=supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        utilbill._registers = [Register(Register.TOTAL, 'kWh', quantity=150)]
        utilbill.charges = [
            Charge('A', rate=1, formula='REG_TOTAL.quantity'),
            Charge('B', rate=3, formula='2'),
            # this has an error
            Charge('C', rate=0, formula='1/0'),
            # the following should not be included in the total computation
            Charge('D', rate=1, formula='REG_TOTAL.quantity', has_charge=False)
        ]
        Session().add(utilbill)
        utilbill.compute_charges()

        self.assert_charge_values(150, 1,
                utilbill.get_charge_by_rsi_binding('A'))
        self.assert_charge_values(2, 3,
                utilbill.get_charge_by_rsi_binding('B'))
        self.assert_error(utilbill.get_charge_by_rsi_binding('C'),
                'Error: division by zero')
        self.assertEqual(150 + 6, utilbill.get_total_charges())

    def test_compute_charges_with_cycle(self):
        """Test computing charges whose dependencies form a cycle.
        All such charges should have errors.
        """
        utility = Utility(name='utility', address=Address())
        supplier = Supplier(name='supplier', address=Address())
        utility_account = UtilityAccount('someone', '99999',
                utility, supplier,
                RateClass(name='rate class', utility=utility, service='gas'),
                Address(), Address())
        utilbill = UtilBill(utility_account, utility,
                            RateClass(name='rate class', utility=utility,
                                      service='gas'), supplier=supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        utilbill.charges = [
            # circular dependency between A and B: A depends on B's "quantity"
            # and B depends on A's "rate", which is not allowed even though
            # theoretically both could be computed.
            Charge('A', formula='B.formula'),
            Charge('B', formula='A.rate'),
            # C depends on itself
            Charge('C', formula='C.total'),
            # D depends on A, which has a circular dependency with B. it should
            # not be computable because A is not computable.
            Charge('D', formula='A.total'),
            Charge('E', rate=3, formula='2'),
        ]
        Session().add(utilbill)
        utilbill.compute_charges()

        self.assert_error(utilbill.get_charge_by_rsi_binding('A'),
                          "Error: name 'B' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('B'),
                          "Error: name 'A' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('C'),
                          "Error: name 'C' is not defined")
        self.assert_error(utilbill.get_charge_by_rsi_binding('D'),
                          "Error: name 'A' is not defined")
        self.assert_charge_values(2, 3, utilbill.get_charge_by_rsi_binding('E'))

    def test_ordered_charges_cycle_tsort_keyerror(self):
        """This causes a KeyError to be raised in tsort.topological_sort
        instead of the expected GraphError, covering the "except KeyError"
        block in UtilBill.ordered_charges.
        """
        utilbill = UtilBill(MagicMock(), None, None)
        charges = [Charge('a', rate=0, formula='b'),
                   Charge('b', rate=0, formula='b')]
        utilbill.charges = charges
        ordered_charges = utilbill.ordered_charges()
        # in this case any order is OK as long as all the charges are there
        self.assertEqual(set(utilbill.charges), set(ordered_charges))

    def test_processed_utility_bills(self):
        '''
        test for making sure processed bills cannot be edited
        '''
        utility = Utility(name='utility', address=Address())
        supplier = Supplier(name='supplier', address=Address())
        utility_account = UtilityAccount('someone', '99999',
                utility, supplier,
                RateClass(name='rate class', utility=utility, service='gas'),
                Address(), Address())
        utilbill = UtilBill(utility_account, utility,
                            RateClass(name='rate class', utility=utility,
                                      service='gas'), supplier=self.supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        utilbill._registers = [Register(Register.TOTAL, 'kWh', quantity=150)]
        utilbill.charges = [
            Charge('A', rate=1, formula=Register.TOTAL + '.quantity'),
            Charge('B', rate=3, formula='2'),
            # this has an error
            Charge('C', rate=0, formula='1/0'),
        ]
        self.assertTrue(utilbill.editable())
        Session().add(utilbill)
        utilbill.processed = True
        self.assertRaises(UnEditableBillError, utilbill.compute_charges)
        self.assertFalse(utilbill.editable())

    def test_get_total_energy_consumption(self):
        utilbill = UtilBill(self.utility_account, self.utility, self.rate_class,
                            supplier=self.supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        utilbill._registers = [Register('X', 'kWh', quantity=1),
                              Register(Register.TOTAL, 'kWh', quantity=2)]
        self.assertEqual(2, utilbill.get_total_energy_consumption())

    def test_charge_types(self):
        utilbill = UtilBill(self.utility_account, self.utility, self.rate_class,
                            supplier=self.supplier,
                            period_start=date(2000, 1, 1),
                            period_end=date(2000, 2, 1))
        the_charges = [
            Charge('A', formula='', rate=1, target_total=1, type='distribution'),
            Charge('B', formula='4', rate=1, type='distribution'),
            # a Charge does not count as a real charge if has_charge=False.
            Charge('C', formula='3', rate=1, type='supply', has_charge=False),
            Charge('D', formula='5', rate=1, target_total=5, type='supply'),
            Charge('E', formula='syntax error', rate=1, type='supply'),
            Charge('F', formula='7', rate=1, type='distribution'),
        ]
        utilbill.charges = the_charges
        self.assertEqual(the_charges, utilbill.charges)

        # supply charge with a syntax error counts as one of the "supply
        # charges"
        self.assertEqual(the_charges[3:5], utilbill.get_supply_charges())

        # but it does not count toward the "supply target total"
        utilbill.compute_charges()
        self.assertEqual(5, utilbill.get_supply_target_total())

        # TODO: test methods that use other charge types (distribution,
        # other) here when they are added.
        self.assertEqual(3, len(utilbill.get_distribution_charges()))

    def test_replace_estimated_with_complete_db(self):
        """Test for the database aspect of
        UtilBill.test_replace_estimated_with_complete: deleting the
        non-estimated bill. (See UtilBillTest for the copying of data from
        one bill to the other.)
        """
        est_bill = UtilBill(self.utility_account, None, None,
                            state=UtilBill.Estimated)
        real_bill = UtilBill(self.utility_account, None, None)
        s = Session()
        s.add_all([est_bill, real_bill])

        # at first both bills are (going to be inserted in) the db
        self.assertTrue(inspect(est_bill).pending)
        self.assertTrue(inspect(real_bill).pending)

        est_bill.replace_estimated_with_complete(
            real_bill, Mock(autospec=BillFileHandler))

        # real bill gets deleted (or in this case, is removed from the
        # session before it gets inserted), estimated bill doesn't
        self.assertNotIn(real_bill, s)
        self.assertTrue(inspect(est_bill).pending)
        self.assertTrue(inspect(real_bill).transient)

