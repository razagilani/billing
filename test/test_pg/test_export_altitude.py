from StringIO import StringIO
from datetime import datetime
from unittest import TestCase
from uuid import uuid5
from uuid import NAMESPACE_DNS

from mock import Mock

from core.model import UtilBill
from pg.export_altitude import PGAltitudeExporter


class TestExportAltitude(TestCase):
    def setUp(self):
        u1 = Mock(autospec=UtilBill)
        u1.get_nextility_account_number.return_value = '11111'
        # TODO Altitude GUIDS
        u1.service = 'electric'
        u1.get_utility_account_number.return_value = '1'
        u1.period_start = datetime(2000,1,1)
        u1.period_end = datetime(2000,2,1)
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

        u2 = Mock(autospec=UtilBill)
        u2.get_nextility_account_number.return_value = '22222'
        # TODO Altitude GUIDS
        u2.service = 'gas'
        u2.get_utility_account_number.return_value = '2'
        u2.period_start = datetime(2000,1,15)
        u2.period_end = datetime(2000,2,15)
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

        self.utilbills = [u1, u2]

        altitude_converter = Mock()
        altitude_converter.get_guid_for_utility\
            .return_value = 'A' * 36
        altitude_converter.get_guid_for_supplier\
            .return_value = 'B' * 36
        uuid_func = lambda: uuid5(NAMESPACE_DNS, 'example.com')
        self.uuid = str(uuid_func())
        self.pgae = PGAltitudeExporter(uuid_func, altitude_converter)

    def test_get_dataset(self):
        dataset = self.pgae.get_dataset(self.utilbills)
        self.assertEqual(2, len(dataset))
        self.assertEqual((
                             '11111',
                             self.uuid,
                             'A' * 36,
                             'B' * 36,
                             'electric',
                             '1',
                             '2000-01-01T00:00:00Z',
                             '2000-02-01T00:00:00Z',
                             10,
                             100,
                             'rate class 1',
                             '',
                             '1 Fake St.',
                             'Washington',
                             'DC',
                             '10000',
                             '2001-01-01T00:00:00Z',
                             '2001-01-02T00:00:00Z',
                         ), dataset[0])
        self.assertEqual((
                             '22222',
                             self.uuid,
                             'A' * 36,
                             'B' * 36,
                             'gas',
                             '2',
                             '2000-01-15T00:00:00Z',
                             '2000-02-15T00:00:00Z',
                             20,
                             200,
                             'rate class 2',
                             '123xyz',
                             '2 Fake St.',
                             'Washington',
                             'DC',
                             '20000',
                             '',
                             '',
                         ), dataset[1])

    def test_export_csv(self):
        '''Just check that something gets written.
        '''
        s = StringIO()
        self.pgae.write_csv(self.utilbills, s)
        self.assertGreater(s.tell(), 0)

