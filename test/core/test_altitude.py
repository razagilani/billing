from unittest import TestCase
from mock import Mock

from billing import init_config, init_model
init_config()
init_model()
from billing.core.model import Utility, Supplier, Address, Session
from billing.core.altitude import AltitudeUtility, AltitudeSupplier,\
    get_utility_from_guid

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

class TestGetUtilityFromGUID(TestCase):
    '''Test with database for data access function.
    '''
    def test_get_utility_from_guid(self):
        u = Utility('A Utility', Address())
        au = AltitudeUtility(u, 'abc')
        s = Session()
        s.add_all([u, au])
        self.assertEqual(u, get_utility_from_guid('abc'))
