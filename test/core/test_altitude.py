from unittest import TestCase
from mock import Mock
from sqlalchemy.orm.exc import FlushError

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

class TestWithDB(TestCase):
    '''Test with database for data access function.
    '''
    def setUp(self):
        self.u = Utility('A Utility', Address())
        self.au = AltitudeUtility(self.u, 'abc')

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
