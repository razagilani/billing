from StringIO import StringIO
from datetime import datetime, date
from unittest import TestCase
from uuid import uuid5, uuid4
from uuid import NAMESPACE_DNS

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from sqlalchemy.orm import Query
import tablib
from test import init_test_config
init_test_config()

from mock import Mock
from core import altitude, init_model
from core.altitude import AltitudeBill, AltitudeSupplier, AltitudeUtility, \
    AltitudeAccount

from core.model import UtilBill, UtilityAccount, Utility, Address, Session, \
    RateClass, Supplier, Register
from brokerage.brokerage_model import BrokerageAccount
from brokerage.export_altitude import PGAltitudeExporter, \
    _create_brokerage_accounts_for_utility_accounts, _load_pg_utilbills
from test import init_test_config, clear_db, create_tables
from util.dateutils import ISO_8601_DATETIME


def setUpModule():
    init_test_config()
    create_tables()
    init_model()

class TestUtilityAccountLoaderMethods(TestCase):

    def setUp(self):
        clear_db()
        self.utility = Utility('test utility')
        self.supplier = Supplier(name='test supplier')
        self.rate_class = RateClass(name='test rate class',
                                    utility=self.utility)

    def test_create_brokerage_accounts_for_utility_accounts(self):
        ua1 = UtilityAccount('', '20022', self.utility, self.supplier,
                             self.rate_class, Address(), Address())
        ua2 = UtilityAccount('', '20023', self.utility, self.supplier,
                             self.rate_class, Address(), Address())
        Session().add_all([ua1, ua2])

        _create_brokerage_accounts_for_utility_accounts()
        ba1 = Session().query(BrokerageAccount).filter(
            BrokerageAccount.utility_account==ua1).one()
        ba2 = Session().query(BrokerageAccount).filter(
            BrokerageAccount.utility_account==ua2).one()
        self.assertEqual(ba1.utility_account, ua1)
        self.assertEqual(ba2.utility_account, ua2)


    def test_load_pg_utilbills(self):
        # Just excecise the code
        _load_pg_utilbills().all()


class TestExportAltitude(TestCase):
    def setUp(self):
        u1 = Mock(autospec=UtilBill)
        u1.get_nextility_account_number.return_value = '11111'
        # TODO Altitude GUIDS
        u1.get_service.return_value = 'electric'
        u1.get_utility_account_number.return_value = '1'
        u1.period_start = datetime(2000,1,1)
        u1.period_end = datetime(2000,2,1)
        u1.due_date = datetime(2000,3,1)
        u1.get_next_meter_read_date.return_value = datetime(2000,3,1)
        u1.get_total_energy_consumption.return_value = 10
        u1.get_supply_target_total.return_value = 100
        u1.get_rate_class_name.return_value = 'rate class 1'
        u1.service_address.street = '1 Fake St.'
        u1.service_address.city = 'Washington'
        u1.service_address.state = 'DC'
        u1.service_address.postal_code = '10000'
        u1.date_received = datetime(2001,1,1)
        u1.date_modified = datetime(2001,1,2)
        u1.supply_choice_id = None
        u1.get_total_meter_identifier.return_value = ''
        u1.tou = False

        u2 = Mock(autospec=UtilBill)
        u2.get_nextility_account_number.return_value = '22222'
        # TODO Altitude GUIDS
        u2.get_service.return_value = None
        u2.get_utility_account_number.return_value = '2'
        u2.period_start = datetime(2000,1,15)
        u2.period_end = datetime(2000,2,15)
        u2.due_date = datetime(2000,3,15)
        u2.get_next_meter_read_date.return_value = datetime(2000,3,15)
        u2.get_total_energy_consumption.return_value = 20
        u2.get_supply_target_total.return_value = 200
        u2.get_rate_class_name.return_value = 'rate class 2'
        u2.service_address.street = '2 Fake St.'
        u2.service_address.city = 'Washington'
        u2.service_address.state = 'DC'
        u2.service_address.postal_code = '20000'
        u2.date_received = None
        u2.date_modified = None
        u2.supply_choice_id = '123xyz'
        u2.get_total_meter_identifier.return_value = ''
        u2.tou = False

        self.utilbills = Mock(autospec=Query)
        self.utilbills.yield_per.return_value = [u1, u2]

        altitude_converter = Mock()
        altitude_converter.get_guid_for_utility\
            .return_value = 'A' * 36
        altitude_converter.get_one_altitude_account_guid_for_utility_account\
            .side_effect = ['C' * 36, None]
        self.uuids = [str(uuid5(NAMESPACE_DNS, 'a')),
                      str(uuid5(NAMESPACE_DNS, 'b')),
                      str(uuid5(NAMESPACE_DNS, 'c')),
                      str(uuid5(NAMESPACE_DNS, 'd'))]
        def uuid_func(count=[0]):
            result = self.uuids[count[0]]
            count[0] += 1
            return result
        altitude_converter.get_or_create_guid_for_utilbill.side_effect = [
            self.uuids[0], self.uuids[2]]
        altitude_converter.get_or_create_guid_for_supplier\
            .side_effect = [self.uuids[1], self.uuids[3]]
        self.pgae = PGAltitudeExporter(uuid_func, altitude_converter)

    def test_get_dataset(self):
        file = StringIO()
        self.pgae.write_csv(self.utilbills, file)

        file.seek(0)
        dataset = tablib.Dataset()
        dataset.csv = file.read()

        self.maxDiff = None
        self.assertEqual(2, len(dataset))
        self.assertEqual((
                             'C' * 36,
                             '11111',
                             str(self.uuids[0]),
                             'A' * 36,
                             str(self.uuids[1]),
                             'electric',
                             '1',
                             '2000-01-01T00:00:00Z',
                             '2000-02-01T00:00:00Z',
                             '2000-03-01T00:00:00Z',
                             '10',
                             '100',
                             'rate class 1',
                             '',
                             '1 Fake St.',
                             'Washington',
                             'DC',
                             '10000',
                             '2001-01-01T00:00:00Z',
                             '2001-01-02T00:00:00Z',
                             '2000-03-01T00:00:00Z',
                             '',
                             'FALSE'
                         ), dataset[0])
        self.assertEqual((
                             '',
                             '22222',
                             str(self.uuids[2]),
                             'A' * 36,
                             str(self.uuids[3]),
                             '',
                             '2',
                             '2000-01-15T00:00:00Z',
                             '2000-02-15T00:00:00Z',
                             '2000-03-15T00:00:00Z',
                             '20',
                             '200',
                             'rate class 2',
                             '123xyz',
                             '2 Fake St.',
                             'Washington',
                             'DC',
                             '20000',
                             '',
                             '',
                             '2000-03-15T00:00:00Z',
                             '',
                             'FALSE'
                         ), dataset[1])

    def test_export_csv(self):
        '''Just check that something gets written.
        '''
        s = StringIO()
        self.pgae.write_csv(self.utilbills, s)
        self.assertGreater(s.tell(), 0)

class TestAltitudeBillStorage(TestCase):
    """Test with the database, involving creating and
    querying AltitudeBill objects.
    """
    def setUp(self):
        clear_db()
        utility = Utility(name='example', address=None)
        rate_class = RateClass(name='Rate Class', utility=utility,
                               service='electric')
        supplier = Supplier(name='Supplier', address=Address())
        ua = UtilityAccount('', '', utility, None, None, Address(),
                            Address())
        self.utilbill = UtilBill(
            ua, utility, rate_class, supplier=supplier,
            billing_address=Address(street='1 Billing St.'),
            service_address=Address(street='1 Service St.'),
            period_start=date(2000,1,1), period_end=date(2000,1,1),
            due_date=date(2000,2,1))
        self.utilbill._registers[0].quantity = 150.
        self.utilbill._registers[0].meter_identifier = 'GHIJKL'
        self.utilbill.utility_account_number = '12345'
        altitude_account = AltitudeAccount(ua, 'aaa')
        altitude_utility = AltitudeUtility(utility, guid='uuu')
        altitude_supplier = AltitudeSupplier(supplier, guid='sss')
        altitude_bill = AltitudeBill(self.utilbill, 'bbb')
        Session().add_all([utility, rate_class, supplier, self.utilbill,
                          altitude_account, altitude_utility, altitude_supplier,
                          altitude_bill])
        self.pgae = PGAltitudeExporter(lambda: str(uuid4()), altitude)

    def tearDown(self):
        clear_db()

    def test_export_with_db(self):
        """Integration test with core.altitude module and database, making sure
        that CSV file contents are actually what was expected.
        """
        s = Session()
        s.add(self.utilbill)

        csv_file = StringIO()
        self.pgae.write_csv(s.query(UtilBill), csv_file)
        expected_csv = (
            'customer_account_guid,billing_customer_id,utility_bill_guid,'
            'utility_guid,supplier_guid,service_type,utility_account_number,'
            'billing_period_start_date,billing_period_end_date,'
            'next_estimated_meter_read_date,total_usage,total_supply_charge,'
            'rate_class,secondary_utility_account_number,'
            'service_address_street,service_address_city,service_address_state,'
            'service_address_postal_code,create_date,modified_date,'
            'ordering_date,meter_number,time_of_use\r\n'
            'aaa,,bbb,uuu,sss,electric,,2000-01-01T00:00:00Z,'
            '2000-01-01T00:00:00Z,,150.0,0,Rate Class,,1 Service St.,,,,,%s,%s,%s,%s\r\n' %
            (self.utilbill.date_modified.strftime(ISO_8601_DATETIME),
            self.utilbill.due_date.strftime(ISO_8601_DATETIME),'GHIJKL', 'FALSE'))
        csv_file.seek(0)
        actual_csv = csv_file.read()
        self.assertEqual(expected_csv, actual_csv)

    def test_altitude_bill_consistency(self):
        """Check that an AlititudeBill is created only once and reused
        during repeated calls to get_dataset for the same bill.
        """
        s = Session()
        s.query(AltitudeBill).delete()
        self.assertEqual(0, s.query(AltitudeBill).count())

        query = Mock(autospec=Query)
        query.yield_per.return_value = [self.utilbill]

        self.pgae.write_csv(query, StringIO())
        self.assertEqual(1, s.query(AltitudeBill).count())

        self.pgae.write_csv(query, StringIO())
        self.assertEqual(1, s.query(AltitudeBill).count())

    def test_altitude_supplier_consistency(self):
        """Check that an AlititudeSupplier is created only once and reused
        during repeated calls to get_dataset for the same supplier.
        """
        s = Session()
        s.query(AltitudeSupplier).delete()
        self.assertEqual(0, s.query(AltitudeSupplier).count())

        query = Mock(autospec=Query)
        query.yield_per.return_value = [self.utilbill]

        self.pgae.write_csv(query, StringIO())
        self.assertEqual(1, s.query(AltitudeSupplier).count())

        self.pgae.write_csv(query, StringIO())
        self.assertEqual(1, s.query(AltitudeSupplier).count())

