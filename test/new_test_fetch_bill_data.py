#!/usr/bin/python
import unittest
from datetime import date
from StringIO import StringIO
import csv
from billing.processing.fetch_bill_data import get_interval_meter_data_source

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
        get_energy_for_hour = get_interval_meter_data_source(csv_file)

        ## outside allowed time range
        #self.assertRaises(IndexError, get_energy_for_hour, date(2012,12,31), 0)
        #self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), 0)
        #self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), 3)
        #self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), 4)
        #self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,2), 0)

        ## 1:00 and 2:00 are valid hours
        #self.assertEquals(14, get_energy_for_hour(date(2012,1,1), 1))
        #self.assertEquals(30, get_energy_for_hour(date(2012,1,1), 2))

        # outside allowed time range
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,12,31), [0,0])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,12,31), [12,23])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [0,0])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [0,1])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [1,4])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,1), [3,3])
        self.assertRaises(IndexError, get_energy_for_hour, date(2012,1,2), [0,0])

        # TODO test bad timestamps

        # 1:00 and 2:00 are valid hours
        self.assertEquals(14, get_energy_for_hour(date(2012,1,1), [1,1]))
        self.assertEquals(30, get_energy_for_hour(date(2012,1,1), [2,2]))
        self.assertEquals(44, get_energy_for_hour(date(2012,1,1), [1,2]))

if __name__ == '__main__':
    unittest.main()
