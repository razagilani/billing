from itertools import chain
from StringIO import StringIO
import csv
import random
import unittest
import sqlalchemy
import pymongo
from mock import Mock
from billing.processing.state import ReeBill, Customer, UtilBill
from skyliner.sky_handlers import cross_range
from billing.processing import mongo
from billing.util import dateutils
from billing.processing import state
from billing.test import example_data
from skyliner.mock_skyliner import MockSplinter, MockSkyInstall
from datetime import date, datetime, timedelta
import billing.processing.fetch_bill_data as fbd

import pprint
pp = pprint.PrettyPrinter().pprint

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
        #sqlalchemy.orm.clear_mappers()
        self.state_db = state.StateDB(**{
            'user': 'dev',
            'password': 'dev',
            'host': 'localhost',
            'database': 'skyline_dev'
        })
        reebill_dao = mongo.ReebillDAO(None,
                pymongo.Connection('localhost', 27017)['skyline-dev'])

        customer = Customer('someone', '12345', 0.5, 0.1,
                            '000000000000000000000000', 'example@example.com')
        utilbill = UtilBill(customer, UtilBill.Complete, 'gas', 'washgas',
                'DC Non Residential Non Heat', period_start=date(2000,1,1),
                period_end=date(2000,2,1))
        utilbill_doc = example_data.get_utilbill_dict('12345',
                start=date(2000,1,1), end=date(2000,2,1), utility='washgas',
                service='gas')
        self.reebill = ReeBill(customer, 1, utilbills=[utilbill])
        self.reebill.update_readings_from_document(self.state_db.session(),
                utilbill_doc)
        self.reebill_doc = example_data.get_reebill('12345', 1,
                start=date(2000,1,1), end=date(2000,1,1))
        reebill_dao = Mock()
        reebill_dao.load_reebill.return_value = self.reebill_doc
        reebill_dao.load_doc_for_utilbill.return_value = utilbill_doc

        mock_install_1 = MockSkyInstall(name='example-1')
        mock_install_2 = MockSkyInstall(name='example-2')
        self.splinter = MockSplinter(deterministic=True,
                installs=[mock_install_1, mock_install_2])
        self.ree_getter = fbd.RenewableEnergyGetter(self.splinter,
                                                    reebill_dao)
        
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


    def test_fetch_interval_meter_data(self):
        '''Realistic test of loading interval meter data with an entire utility
        bill date range. Tests lack of errors but not correctness.'''
        # reebill = example_data.get_reebill('10002', 21)

        # generate example csv file whose time range exactly matches the bill
        # period
        csv_file = StringIO()
        start, end = self.reebill.get_period()
        make_big_interval_meter_test_csv(start, end, csv_file)
        # writing the file puts the file pointer at the end, so move it back
        csv_file.seek(0)

        self.ree_getter.fetch_interval_meter_data(self.reebill, csv_file)


    def test_fetch_oltp_data(self):
        '''Put energy in a bill with a simple "total" register, and make sure the
        register contains the right amount of energy.'''
        # create mock skyliner objects
        monguru = self.splinter.get_monguru()
        install = self.splinter.get_install_obj_for('example-1')

        # gather REE data into the reebill
        self.ree_getter.update_renewable_readings(install.name, self.reebill)

        # get total REE for all hours in the reebill's meter read period,
        # according to 'monguru'
        total_btu = 0
        #for hour in cross_range(*reebill.meter_read_period('gas')):
        from billing.util.dateutils import date_to_datetime
        for hour in cross_range(*(date_to_datetime(d) for d in self.reebill\
                .get_period())):
            day = date(hour.year, hour.month, hour.day)
            total_btu += monguru.get_data_for_hour(install, day,
                    hour.hour).energy_sold
        
        # compare 'total_btu' to reebill's total REE (converted from therms to
        # BTU).
        self.assertAlmostEqual(total_btu,
                self.reebill.get_total_renewable_energy() * 100000)

if __name__ == '__main__':
    unittest.main()
