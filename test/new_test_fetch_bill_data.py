#!/usr/bin/python
import sys
import random
import unittest
import csv
from datetime import date
from StringIO import StringIO
import billing.processing.fetch_bill_data as fbd
from datetime import date, datetime, timedelta
from billing import dateutils, mongo
from decimal import Decimal
import pprint
pp = pprint.PrettyPrinter().pprint

def make_big_interval_meter_test_csv(start_date, end_date, csv_file):
    '''Writes a sample CSV to csv_file with file with random energy values
    every 15 minutes in the format used by fetch_interval_meter_data.
    Command-line arguments are file name, start date (ISO 8601, inclusive), end
    date (exclusive). E.g:
        make_sample_csv.py interval_meter_sample.csv 2012-11-10 2012-12-12
    Returns the sum of all energy in the file.
    '''
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

class FetchTest(unittest.TestCase):
    def setUp(self):
        self.reebill_dao = mongo.ReebillDAO({
            'billpath': '/db-dev/skyline/bills/',
            'database': 'skyline',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'reebills',
            'host': 'localhost',
            'port': '27017'
        })
        
    def test_get_interval_meter_data_source(self):
        csv_file = StringIO('\n'.join([
            # note that 01:00:00 is not included
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
        get_energy_for_hour = fbd.get_interval_meter_data_source(csv_file)

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
        get_energy_for_hour = fbd.get_interval_meter_data_source(csv2)
        self.assertEquals(14, get_energy_for_hour(date(2012,1,1),[1,1]))

        # TODO test a csv with bad timestamps


    def test_fetch_interval_meter_data(self):
        '''Realistic test of loading interval meter data with an entire utility
        bill date range. Tests lack of errors but not correctness.'''
        # TODO would be great to have a way of getting a fake reebill for
        # testing. here i just count on this reebill existing and then modify
        # it but don't save it
        reebill = self.reebill_dao.load_reebill('10002', 21)
        # these are the dates i expect that bill to have
        assert reebill.period_begin == date(2011,11,10)
        assert reebill.period_end == date(2011,12,12)

        # generate example csv file whose time range exactly matches the bill
        # period
        csv_file = StringIO()
        make_big_interval_meter_test_csv(reebill.period_begin,
                reebill.period_end, csv_file)
        # writing the file puts the file pointer at the end, so move it back
        csv_file.seek(0)

        fbd.fetch_interval_meter_data(reebill, csv_file)


    def test_fetch_interval_meter_data_with_meter(self):
        # test with a specific meter. here's a bill with 2 meters, 1 of which
        # contains shadow registers and the other of which does not. (currently
        # all customers have exactly 1 shadowed meter). putting energy into the
        # shadow registers of that specific meter is the same as putting it
        # into all shadowed meters.
        reebill = self.reebill_dao.load_reebill('10004', 18)
        assert reebill.period_begin == date(2011,9,5)
        assert reebill.period_end == date(2011,10,4)
        meters = reduce(lambda x,y:x+y, [reebill.meters_for_service(s) for s in reebill.services], [])
        pp(meters)
        print len(meters)

        # should have 2 meters with the identifiers shown
        assert len(meters) == 2
        assert len([m for m in meters if m['identifier'] == '028702956']) == 1
        assert len([m for m in meters if m['identifier'] == '027870434']) == 1
        meter1 = [m for m in meters if m['identifier'] == '028702956'][0]
        meter2 = [m for m in meters if m['identifier'] == '027870434'][0]

        # only the second contains shadow registers
        shadow_registers = [r for r in meter1['registers'] +
                meter2['registers'] if r['shadow'] is True]
        pp(shadow_registers)
        assert len(shadow_registers) == 1
        assert [r for r in shadow_registers if r['identifier'] == '028702956'] == []
        assert [r for r in shadow_registers if r['identifier'] == '027870434'] != []

        # set value of all registers in both meters to an arbitrary value
        # (also set unit to 'therms' instead of 'Ccf' because ccf isn't
        # really an energy unit)
        for r in meter1['registers'] + meter2['registers']:
            r['quantity'] = Decimal(-1234567890)
            r['quantity_units'] = 'therms'
        pp(meter1['registers'] + meter2['registers'])
        pp(shadow_registers)
        # accumulate energy into shadow registers
        csv_file = StringIO()
        make_big_interval_meter_test_csv(reebill.period_begin,
                reebill.period_end, csv_file)
        csv_file.seek(0)

        fbd.fetch_interval_meter_data(reebill, csv_file, '027870434')

        # check that shadow register changed value and other registers didn't
        for r in meter1['registers'] + meter2['registers']:
            if r in shadow_registers:
                self.assertNotEquals(Decimal(-1234567890), r['quantity'])
            else:
                self.assertEquals(Decimal(-1234567890), r['quantity'])

if __name__ == '__main__':
    unittest.main()
