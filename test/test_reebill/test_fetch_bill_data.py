from StringIO import StringIO
import csv
import random
import unittest
from datetime import date, datetime, timedelta
from mock import Mock, call
from core.model import Utility, Session, SupplyGroup
from skyliner.sky_install import SkyInstall
from skyliner.skymap.monguru import CubeDocument, Monguru

from reebill.reebill_model import ReeBill, UtilBill, Address, \
    Register, Reading, ReeBillCustomer
from core.model import UtilityAccount, RateClass, Supplier
from skyliner.sky_handlers import cross_range
from util import dateutils
from skyliner.mock_skyliner import MockSplinter, MockSkyInstall
import reebill.fetch_bill_data as fbd
from util.dateutils import date_to_datetime



def make_big_interval_meter_test_csv(start_date, end_date, csv_file):
    '''Writes a sample CSV to csv_file with file with random energy values
    every 15 minutes from start_date to end_date (exclusive). Uses default
    interval meter data format.'''
    writer = csv.writer(csv_file)
    for day in dateutils.date_generator(start_date, end_date):
        dt = datetime(day.year, day.month, day.day, 0)
        while dt.day == day.day:
            dt += timedelta(hours=0.25)
            writer.writerow([
                datetime.strftime(dt, dateutils.ISO_8601_DATETIME),
                random.random(),
                'therms'
            ])

def make_atsite_test_csv(start_date, end_date, csv_file):
    '''Writes a sample CSV like the above, but imitating the format of AtSite's
    example file.'''
    csv.register_dialect('atsite', delimiter=',', quotechar='"',
            quoting=csv.QUOTE_ALL)
    writer = csv.writer(csv_file, 'atsite')
        
    header_row = [cell.strip('"') for cell in '''"time(UTC)","error","lowalarm","highalarm","Natural Gas Meter (CF)","Natural Gas Meter Ave Rate (CFm)","Natural Gas Meter Instantaneous (CFm)","Natural Gas Meter Min (CFm)","Natural Gas Meter Max (CFm)","Water Meter - Main (CUFT)","Water Meter - Main Ave Rate (CUFT per hour)","Water Meter - Main Instantaneous (CUFT per hour)","Water Meter - Main Min (CUFT per hour)","Water Meter - Main Max (CUFT per hour)","Small Water meter A (Cubic Feet)","Small Water meter A Ave Rate (CFm)","Small Water meter A Instantaneous (CFm)","Small Water meter A Min (CFm)","Small Water meter A Max (CFm)","Small Water meter B (Cubic Feet)","Small Water meter B Ave Rate (CFm)","Small Water meter B Instantaneous (CFm)","Small Water meter B Min (CFm)","Small Water meter B Max (CFm)","PEPCO Meter (kwh)","PEPCO Meter Demand (kW)","PEPCO Meter Instantaneous (kW)","PEPCO Meter Min (kW)","PEPCO Meter Max (kW)","Input 6","-","-","-","-","Input 7","-","-","-","-","Input 8","-","-","-","-","Output 01","Output 02"'''.split(',')]
    writer.writerow(header_row)

    for day in dateutils.date_generator(start_date, end_date):
        dt = datetime(day.year, day.month, day.day, 0)
        while dt.day == day.day:
            dt += timedelta(hours=0.25)
            # each row after header is timestamp, 23 blanks, and a number
            row = [datetime.strftime(dt, '%Y-%m-%d %H:%M:%S')] + [''] * 23 \
                    + [random.random() * 1000000]
            writer.writerow(row)


class FetchTest(unittest.TestCase):
    def setUp(self):
        utility_account = UtilityAccount('someone', '12345',
            Mock(autospec=Utility), Mock(autospec=Supplier),
            Mock(autospec=RateClass), Mock(autospec=SupplyGroup),
            Address(), Address())
        reebill_customer = ReeBillCustomer(name='someone', discount_rate=0.5,
                                late_charge_rate=0.1, service='thermal',
                                bill_email_recipient='example@example.com',
                                utility_account=utility_account)
        utility = Utility(name='Washington Gas')
        rate_class = RateClass('DC Non Residential Non Heat', utility=utility)
        utilbill = UtilBill(utility_account, utility, rate_class=rate_class,
                period_start=date(2000,1,1), period_end=date(2000,2,1))
        utilbill.registers = [Register(Register.TOTAL, 'therms')]
        self.reebill = ReeBill(reebill_customer, 1, utilbills=[utilbill])
        self.reebill.replace_readings_from_utility_bill_registers(utilbill)

        mock_install_1 = MockSkyInstall(name='example-1')
        mock_install_2 = MockSkyInstall(name='example-2')
        self.splinter = MockSplinter(deterministic=True,
                installs=[mock_install_1, mock_install_2])
        self.nexus_util = Mock()
        self.nexus_util.olap_id.return_value = 'example-1'
        self.ree_getter = fbd.RenewableEnergyGetter(self.splinter,
                                                    self.nexus_util, None)
        
    def test_get_interval_meter_data_source(self):
        csv_file = StringIO('\n'.join([
            # note that 01:00:00 is not included, and that units column is
            # meaningless
            '2012-01-01T01:15:00Z, 2, therms',
            '2012-01-01T01:30:00Z, 3, therms',
            '2012-01-01T01:45:00Z, 4, therms',
            '2012-01-01T02:00:00Z, 5, therms',
            '2012-01-01T02:15:00Z, 6, therms',
            '2012-01-01T02:30:00Z, 7, therms',
            '2012-01-01T02:45:00Z, 8, therms',
            '2012-01-01T03:00:00Z, 9, therms',
            '2012-01-01T03:15:00Z, 10, therms',
            '2012-01-01T03:30:00Z, 11, therms',
            '2012-01-01T03:45:00Z, 12, therms',
        ]))
        get_energy_for_hour = self.ree_getter.get_interval_meter_data_source(
                csv_file)

        # outside allowed time range
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,12,31), [0,0])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,12,31), [12,23])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [0,0])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [0,1])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [1,4])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [3,3])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,2), [0,0])

        # 1:00 and 2:00 are valid hours
        self.assertEquals(14, get_energy_for_hour(date(2012,1,1), [1,1]))
        self.assertEquals(30, get_energy_for_hour(date(2012,1,1), [2,2]))
        self.assertEquals(44, get_energy_for_hour(date(2012,1,1), [1,2]))

        # a case where the query lines up with the end of the data
        csv2 = StringIO('\n'.join([
            '2012-01-01T01:15:00Z, 2, therms',
            '2012-01-01T01:30:00Z, 3, therms',
            '2012-01-01T01:45:00Z, 4, therms',
            '2012-01-01T02:00:00Z, 5, therms',
            ]))
        get_energy_for_hour = self.ree_getter.get_interval_meter_data_source(
                csv2)
        self.assertEquals(14, get_energy_for_hour(date(2012,1,1),[1,1]))

        # TODO test a csv with bad timestamps


    def test_get_interval_meter_data_source_atsite(self):
        '''Test of getting interval meter data from AtSite's example
        spreadsheet. Unlike the test above, this uses a non-default timestamp
        format and energy column.'''
        # i sorted the rows of AtSite's example CSV file so the timestamps are
        # actually in order. we do require the timestamps to be in order.
        # (TODO tolerate backwards timestamps...then we can't binary search for the time range endpoints, right?)
        atsite_csv = StringIO('''"time(UTC)","error","lowalarm","highalarm","Natural Gas Meter (CF)","Natural Gas Meter Ave Rate (CFm)","Natural Gas Meter Instantaneous (CFm)","Natural Gas Meter Min (CFm)","Natural Gas Meter Max (CFm)","Water Meter - Main (CUFT)","Water Meter - Main Ave Rate (CUFT per hour)","Water Meter - Main Instantaneous (CUFT per hour)","Water Meter - Main Min (CUFT per hour)","Water Meter - Main Max (CUFT per hour)","Small Water meter A (Cubic Feet)","Small Water meter A Ave Rate (CFm)","Small Water meter A Instantaneous (CFm)","Small Water meter A Min (CFm)","Small Water meter A Max (CFm)","Small Water meter B (Cubic Feet)","Small Water meter B Ave Rate (CFm)","Small Water meter B Instantaneous (CFm)","Small Water meter B Min (CFm)","Small Water meter B Max (CFm)","PEPCO Meter (kwh)","PEPCO Meter Demand (kW)","PEPCO Meter Instantaneous (kW)","PEPCO Meter Min (kW)","PEPCO Meter Max (kW)","Input 6","-","-","-","-","Input 7","-","-","-","-","Input 8","-","-","-","-","Output 01","Output 02"
"2012-03-28 18:15:00",0,0,0,2277750,0,,,,4029260,0,,,,2644405.305,9.19,2.812,0.17,45,319,0,,,,2217592.033,206.28,202.5,173.571,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 18:30:00",0,0,0,2277750,0,,,,4029260,0,,,,2644515.255,7.33,3.214,0.294,45,319,0,,,,2217643.333,205.2,202.5,186.923,243,,,,,,,,,,,,,,,,0,0
"2012-03-28 18:45:00",0,0,0,2277750,0,,,,4029260,0,,,,2644626.405,7.41,1.154,0.152,45,319,0,,,,2217693.148,199.26,202.5,173.571,243,,,,,,,,,,,,,,,,0,0
"2012-03-28 19:00:00",0,0,0,2277750,0,,,,4029260,0,,,,2644828.155,13.45,6.429,0.222,45,319,0,,,,2217742.963,199.26,202.5,186.923,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 19:15:00",0,0,0,2277750,0,,,,4029260,0,,,,2645060.955,15.52,45,0.441,45,319,0,,,,2217792.913,199.8,186.923,173.571,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 19:30:00",0,0,0,2277760,0.667,0.203,0.203,0.203,4029260,0,,,,2645199.855,9.26,0.75,0.126,45,319,0,,,,2217844.078,204.66,186.923,173.571,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 19:45:00",0,0,0,2277760,0,,,,4029260,0,,,,2645298.555,6.58,45,0.263,45,319,0,,,,2217892.813,194.94,202.5,162,243,,,,,,,,,,,,,,,,0,0
"2012-03-28 20:00:00",0,0,0,2277760,0,,,,4029260,0,,,,2645380.755,5.48,3.462,0.147,45,319,0,,,,2217939.658,187.38,186.923,162,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 20:15:00",0,0,0,2277760,0,,,,4029260,0,,,,2645444.055,4.22,0.789,0.154,45,319,0,,,,2217986.773,188.46,186.923,162,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 20:30:00",0,0,0,2277760,0,,,,4029260,0,,,,2645687.355,16.22,22.5,0.121,45,319,0,,,,2218036.048,197.1,173.571,173.571,220.909,,,,,,,,,,,,,,,,0,0
"2012-03-28 20:45:00",0,0,0,2277760,0,,,,4029260,0,,,,2645831.505,9.61,1.957,0.145,45,319,0,,,,2218082.218,184.68,186.923,173.571,202.5,,,,,,,,,,,,,,,,0,0
"2012-03-28 21:00:00",0,0,0,2277760,0,,,,4029260,0,,,,2645978.655,9.81,9,0.315,45,319,0,,,,2218128.388,184.68,186.923,162,220.909,,,,,,,,,,,,,,,,0,0''')
 
        # the column we care about is "PEPCO Meter (kwh)" at index 24
        get_energy_for_hour = self.ree_getter.get_interval_meter_data_source(
                atsite_csv,
                timestamp_column=0, energy_column=24,
                timestamp_format='%Y-%m-%d %H:%M:%S', energy_unit='kwh')

        self.assertRaises(IndexError, get_energy_for_hour, date(2012,3,28), [17,18])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,3,28), [21,21])

        # total energy during hours 19 and 20 converted from kWh to BTU
        total_kwh_19 = 2217792.913 + 2217844.078 + 2217892.813 + 2217939.658
        total_kwh_20 = 2217986.773 + 2218036.048 + 2218082.218 + 2218128.388
        total_btu_19 = total_kwh_19 / 3412.14163
        total_btu_20 = total_kwh_20 / 3412.14163

        # these are not quite the same due to floating-point errors
        # (assertAlmostEqual checks 7 decimal places by default)
        self.assertAlmostEqual(total_btu_19,
                get_energy_for_hour(date(2012,3,28), [19,19]))
        self.assertAlmostEqual(total_btu_19 + total_btu_20,
                get_energy_for_hour(date(2012,3,28), [19,20]))


    def test_fetch_oltp_data_simple(self):
        '''Put energy in a bill with a simple "total" register, and make sure
        the register contains the right amount of energy.
        '''
        # create mock skyliner objects
        monguru = self.splinter.get_monguru()
        install = self.splinter.get_install_obj_for('example-1')

        # gather REE data into the reebill
        self.ree_getter.update_renewable_readings(self.reebill)

        # get total REE for all hours in the reebill's meter read period,
        # according to 'monguru'
        total_btu = 0
        for hour in cross_range(*(date_to_datetime(d) for d in self.reebill\
                .get_period())):
            day = date(hour.year, hour.month, hour.day)
            total_btu += monguru.get_data_for_hour(install, day,
                    hour.hour).energy_sold
        
        # compare 'total_btu' to reebill's total REE (converted from therms to
        # BTU).
        self.assertAlmostEqual(total_btu,
                self.reebill.get_total_renewable_energy() * 100000)

class ReeGetterTestPV(unittest.TestCase):
    '''Test for ReeGetter involving a PV bill with both energy and demand
    registers.
    Unlike the above, this has proper mocking and doesn't depend on
    SQLAlchemy objects.
    '''
    # TODO: test_fetch_oltp_data should be moved into here, or another class
    # that sets up mocks in a similar way.

    def setUp(self):
        utilbill = Mock()
        utilbill.period_start = date(2000,1,1)
        utilbill.period_end = date(2000,2,1)
        energy_register = Mock(autospec=Register)
        energy_register.register_binding = Register.TOTAL
        energy_register.get_active_periods.return_value = {
            'active_periods_weekday': [(0, 23)],
            'active_periods_weekend': [(0, 23)],
            'active_periods_holiday': [(0, 23)],
        }
        demand_register = Mock(autospec=Register)
        demand_register.register_binding = Register.DEMAND
        demand_register.get_active_periods.return_value = \
                energy_register.get_active_periods.return_value
        utilbill.registers = [energy_register, demand_register]

        self.reebill = Mock()
        self.reebill.utilbill = utilbill
        self.reebill.get_period.return_value = (date(2000,1,1), date(2000,2,1))

        # reading quantities will get overwritten
        self.energy_reading = Mock(autospec=Reading)
        self.energy_reading.register_binding = \
                energy_register.register_binding
        self.energy_reading.measure = 'Energy Sold'
        self.energy_reading.aggregate_function = 'SUM'
        self.energy_reading.get_aggregation_function.return_value = sum
        self.energy_reading.unit = 'kWh'
        self.energy_reading.conventional_quantity = -1
        self.energy_reading.renewable_quantity = -2
        self.demand_reading = Mock()
        self.demand_reading.register_binding = \
                demand_register.register_binding
        self.demand_reading.conventional_quantity = -3
        self.demand_reading.renewable_quantity = -4
        self.demand_reading.measure = 'Demand'
        self.demand_reading.aggregate_function = 'MAX'
        self.demand_reading.get_aggregation_function.return_value = max
        self.demand_reading.unit = 'kWD'
        self.reebill.readings = [self.energy_reading, self.demand_reading]

        self.monguru = Mock(autospec=Monguru)
        self.install = Mock(autospec=SkyInstall)
        self.install.get_annotations.return_value = []

        # 1 BTU of energy consumed per day, 2 kWD of demand every day
        mock_facts_doc = Mock(autospec=CubeDocument)
        mock_facts_doc.energy_sold = 1
        mock_facts_doc.demand = 2
        self.monguru.get_data_for_hour.return_value = mock_facts_doc

        splinter = Mock()
        splinter._guru = self.monguru
        splinter.get_install_obj_for.return_value = self.install
        self.ree_getter = fbd.RenewableEnergyGetter(splinter, Mock(), None)

    def test_set_renewable_energy_readings_pv(self):
        self.ree_getter.update_renewable_readings(self.reebill)
        start, end = self.reebill.get_period()
        expected_total_energy_sold = 1 * (end - start).days * 24
        expected_max_demand = 2

        self.reebill.set_renewable_energy_reading.assert_has_calls([
            call(self.energy_reading.register_binding,
                 expected_total_energy_sold),
            call(self.demand_reading.register_binding, expected_max_demand),
        ])
