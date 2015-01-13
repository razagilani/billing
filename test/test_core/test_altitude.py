from unittest import TestCase
from mock import Mock
from sqlalchemy.orm.exc import FlushError

from billing import init_model
# TODO importing setup_teardown here causes core.model to be imported,
# which defines Session with bind=None.
from billing.test.setup_teardown import TestCaseWithSetup
from billing.test import init_test_config
init_test_config()
init_model()

from billing.core.model import Utility, Supplier, Address, Session, \
    UtilityAccount, RateClass
from billing.core.altitude import AltitudeUtility, AltitudeSupplier,\
    get_utility_from_guid, update_altitude_account_guids, AltitudeAccount


class TestAltitudeModelClasses(TestCase):
    '''Very simple test just to get coverage, since these classes hardly do
    anything.
    '''
    def setUp(self):
        self.utility = Mock(autospec=Utility)
        self.utility.id = 1
        self.supplier = Mock(autospec=Supplier)
        self.supplier.id = 2

    def test_altitude_utility(self):
        au = AltitudeUtility(self.utility, 'abc')
        self.assertEqual(self.utility, au.utility)
        self.assertEqual('abc', au.guid)

    def test_altitude_supplier(self):
        asu = AltitudeSupplier(self.supplier, 'def')
        self.assertEqual(self.supplier, asu.supplier)
        self.assertEqual('def', asu.guid)

class TestWithDB(TestCase):
    '''Test with database for data access function.
    '''
    def setUp(self):
        # don't use everything in TestCaseWithSetup because it needs to be
        # broken into smaller parts
        TestCaseWithSetup.delete_data(Session())

        self.u = Utility('A Utility', Address())
        self.au = AltitudeUtility(self.u, 'abc')

    def tearDown(self):
        s = Session()
        s.rollback()
        TestCaseWithSetup.delete_data(s)

    def test_get_utility_from_guid(self):
        s = Session()
        s.add_all([self.u, self.au])
        self.assertEqual(self.u, get_utility_from_guid('abc'))

    def test_relationship(self):
        # multiple Altitude GUIDs map to one utility, and vice versa
        s = Session()
        s.add_all([self.u, self.au])
        s.add(AltitudeUtility(self.u, 'def'))
        v = Utility('Other', Address())
        s.add(AltitudeUtility(v, 'abc'))
        s.flush()

        # but you can't add more than one AltitudeUtility with the same
        # utility_id and guid
        s.flush()
        s.add(AltitudeUtility(self.u, 'abc'))
        with self.assertRaises(FlushError):
            s.flush()

    def test_update_altitude_account_guids(self):
        s = Session()
        ua = UtilityAccount('example', '00001', self.u,
                            Supplier('s', Address()), RateClass('r', self.u),
                            Address(), Address(), account_number='1')
        s.add(ua)

        self.assertEqual(0, s.query(AltitudeAccount).count())

        update_altitude_account_guids(ua, ['a'])
        a = s.query(AltitudeAccount).one()
        self.assertEqual(ua, a.utility_account)
        self.assertEqual('a', a.guid)

        update_altitude_account_guids(ua, ['a', 'b'])
        a, b = s.query(AltitudeAccount).order_by(AltitudeAccount.guid).all()
        self.assertEqual(ua, a.utility_account)
        self.assertEqual('a', a.guid)
        self.assertEqual(ua, b.utility_account)
        self.assertEqual('b', b.guid)

        update_altitude_account_guids(ua, ['c'])
        c = s.query(AltitudeAccount).one()
        self.assertEqual(ua, c.utility_account)
        self.assertEqual('c', c.guid)

        # more than one utility account can share the same AltitudeAccount
        ua2 = UtilityAccount('example2', '00002', self.u, ua.fb_supplier,
                             ua.fb_rate_class, Address(), Address(),
                             account_number='2')
        update_altitude_account_guids(ua2, ['c'])
        c1, c2 = s.query(AltitudeAccount).order_by(
            AltitudeAccount.utility_account_id).all()
        self.assertEqual('c', c1.guid)
        self.assertEqual(ua, c1.utility_account)
        self.assertEqual('c', c2.guid)
        self.assertEqual(ua2, c2.utility_account)

        # delete AltitudeAccount for one UtilityAccount, leaving the other
        update_altitude_account_guids(ua, [])
        c2 = s.query(AltitudeAccount).one()
        self.assertEqual('c', c2.guid)
        self.assertEqual(ua2, c2.utility_account)
