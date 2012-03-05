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

def make_big_interval_meter_test_csv(start_date, end_date, csv_file):
    '''Writes a sample CSV to csv_file with file with random energy values
    every 15 minutes in the format used by fetch_interval_meter_data.
    Command-line arguments are file name, start date (ISO 8601, inclusive), end
    date (exclusive). E.g:
        make_sample_csv.py interval_meter_sample.csv 2012-11-10 2012-12-12
    '''
    writer = csv.writer(csv_file)
    for day in dateutils.date_generator(start_date, end_date - timedelta(days=1)):
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
        pass
        
    def test_get_interval_meter_data(self):
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


        # TODO test a csv with bad timestamps


    def test_fetch_interval_meter_data(self):
        '''Realistic test of loading interval meter data with an entire utility
        bill date range. Tests that it worked but not that it was correct.'''
        # TODO would be great to have a way of getting a fake reebill for
        # testing. here i just count on this reebill existing and then modify
        # it but don't save it
        reebill_dao = mongo.ReebillDAO({
            'billpath': '/db-dev/skyline/bills/',
            'database': 'skyline',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'reebills',
            'host': 'localhost',
            'port': '27017'
        })
        reebill = reebill_dao.load_reebill('10002', 21)

        csv_file = StringIO()
        make_big_interval_meter_test_csv(reebill.period_begin, reebill.period_end, csv_file)
        # writing the file puts the file pointer at the end, so move it back
        csv_file.seek(0)

        fbd.fetch_interval_meter_data(reebill, csv_file)

if __name__ == '__main__':
    unittest.main()
