#!/usr/bin/python
import unittest
import datetime
from billing.processing.fetch_bill_data import get_energy_for_time_interval

class FetchTest(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_energy_for_time_interval(self):
        data = [
            (datetime.datetime(2012,1,1, 2), 10.),
            (datetime.datetime(2012,1,1, 4), 25.),
            (datetime.datetime(2012,1,1, 6), 30.),
            (datetime.datetime(2012,1,1, 8), 15.),
        ]
        # nb zip* produces list of tuples no matter what its argument is
        timestamps, values = zip(*data)

        # querying for time interval that extends before earliest timestamp or
        # after last timestamp should raise IndexError
        # (we do have the energy for the earliest timestamp but we don't know
        # what time period it extended over, so it's useless)
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 0),
                datetime.datetime(2012,1,1, 1))
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 0),
                datetime.datetime(2012,1,1, 2))
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 0),
                datetime.datetime(2012,1,1, 3))
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 0),
                datetime.datetime(2012,1,1, 9))
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 7),
                datetime.datetime(2012,1,1, 9))
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 8),
                datetime.datetime(2012,1,1, 9))
        self.assertRaises(IndexError, get_energy_for_time_interval, timestamps,
                values, datetime.datetime(2012,1,1, 9),
                datetime.datetime(2012,1,1, 10))

        # interval of 0 length has no energy
        self.assertEquals(0, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 2),
                datetime.datetime(2012,1,1, 2)))
        self.assertEquals(0, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 4,30),
                datetime.datetime(2012,1,1, 4,30)))

        # 2:00 to 2:30: 1/4 of the 25 energy units between 2:00 and 4:00
        self.assertEquals(25/4., get_energy_for_time_interval(timestamps,
                values, datetime.datetime(2012,1,1, 2),
                datetime.datetime(2012,1,1, 2, 30)))

        # 2:30 to 4:00: 3/4 of the 25 energy units between 2:00 and 4:00
        self.assertEquals(25*3/4., get_energy_for_time_interval(timestamps, 
                values, datetime.datetime(2012,1,1, 2, 30),
                datetime.datetime(2012,1,1, 4)))

        # 2:30 to 6:30: 25/2 + 30 + 15/2 = 50
        self.assertEquals(50, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 2,30),
                datetime.datetime(2012,1,1, 6,30)))

        # 5:00 to 8:00: 30/2 + 30 = 45
        self.assertEquals(45, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 5),
                datetime.datetime(2012,1,1, 8)))

        # some exactly-on-timestamp ranges
        self.assertEquals(25, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 2),
                datetime.datetime(2012,1,1, 4)))
        self.assertEquals(30, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 4),
                datetime.datetime(2012,1,1, 6)))
        self.assertEquals(15, get_energy_for_time_interval(timestamps, values,
                datetime.datetime(2012,1,1, 6),
                datetime.datetime(2012,1,1, 8)))
        self.assertEquals(25 + 30 + 15, get_energy_for_time_interval(
                timestamps, values,
                datetime.datetime(2012,1,1, 6),
                datetime.datetime(2012,1,1, 8)))
        
if __name__ == '__main__':
    unittest.main()
