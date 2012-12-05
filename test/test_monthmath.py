from datetime import date, time, datetime, timedelta
import calendar
import unittest
from billing.util.monthmath import Month, approximate_month, months_of_past_year

class MonthmathTest(unittest.TestCase):
    def test_month(self):
        m = Month(2012,5)
        self.assertEquals(2012, m.year)
        self.assertEquals(5, m.month)

        # alternate constructors
        self.assertEquals(Month((2012,5)), m)
        self.assertEquals(Month([2012,5]), m)
        self.assertEquals(Month(date(2012,5,15)), m)
        self.assertEquals(Month(datetime(2012,5,15,12)), m)
        
        # month-to-month comparison
        self.assertLess(Month(2011,6), Month(2012,2))
        self.assertLess(Month(2012,1), Month(2012,2))
        self.assertGreater(Month(2012,3), Month(2012,2))
        self.assertGreater(Month(2015,1), Month(2012,2))
        
        # month-to-month comparison
        self.assertLess(Month(2011,6), Month(2012,2))
        self.assertLess(Month(2012,1), Month(2012,2))
        self.assertGreater(Month(2012,3), Month(2012,2))
        self.assertGreater(Month(2015,1), Month(2012,2))

        # month-tuple comparison
        self.assertEquals((2012,5), m)
        self.assertLess(Month(2011,6), (2012,2))
        self.assertLess(Month(2012,1), (2012,2))
        self.assertGreater(Month(2012,3), (2012,2))
        self.assertGreater(Month(2015,1), (2012,2))


    def test_days_in_month(self):
        jul15 = date(2011,7,15)
        aug5 = date(2011,8,5)
        aug6 = date(2011,8,6)
        aug12 = date(2011,8,12)
        sep1 = date(2011,9,1)
        aug122012 = date(2012,8,12)
        
        # previous year
        self.assertEqual(Month(2010,7).overlap_with_period(jul15, sep1), 0)

        # month before start_date in same year
        self.assertEqual(Month(2011,6).overlap_with_period(jul15, sep1), 0)

        # month after end_date in same year
        self.assertEqual(Month(2011,10).overlap_with_period(jul15, sep1), 0)

        # next year
        self.assertEqual(Month(2012, 8).overlap_with_period(jul15, sep1), 0)

        # start_date & end_date in same month
        self.assertEqual(Month(2011, 8).overlap_with_period(aug5, aug12), 7)

        # start_date & end_date equal: error
        self.assertRaises(ValueError, Month(2011, 8).overlap_with_period, aug12, aug12)

        # start_date before end_date: error
        self.assertRaises(ValueError, Month(2011,8).overlap_with_period, aug12, aug5)

        # start_date & end_date 1 day apart
        self.assertEqual(Month(2011, 8).overlap_with_period(aug5, aug6), 1)

        # start_date & end_date in successive months
        self.assertEquals(Month(2011,6).overlap_with_period(jul15, aug12), 0)
        self.assertEquals(Month(2011,7).overlap_with_period(jul15, aug12), 17)
        self.assertEquals(Month(2011,8).overlap_with_period(jul15, aug12), 11)
        self.assertEquals(Month(2011,9).overlap_with_period(jul15, aug12), 0)
        
        # start_date & end_date in non-successive months
        self.assertEquals(Month(2011,6).overlap_with_period(jul15, sep1), 0)
        self.assertEquals(Month(2011,7).overlap_with_period(jul15, sep1), 17)
        self.assertEquals(Month(2011,8).overlap_with_period(jul15, sep1), 31)
        self.assertEquals(Month(2011,9).overlap_with_period(jul15, sep1), 0)
        
        # start_date & end_date in different years
        self.assertEquals(Month(2011,6).overlap_with_period(jul15, aug122012), 0)
        self.assertEquals(Month(2011, 7).overlap_with_period(jul15, aug122012), 17)
        for month in range(8,12):
            self.assertEquals(Month(2011, month).overlap_with_period(jul15, aug122012), \
                    calendar.monthrange(2011, month)[1])
        for month in range(1,8):
            self.assertEquals(Month(2012, month).overlap_with_period(jul15, aug122012), \
                    calendar.monthrange(2012, month)[1])
        self.assertEquals(Month(2012, 8).overlap_with_period(jul15, aug122012), 11)

    def test_approximate_month(self):
        jul15 = date(2011,7,15)
        aug5 = date(2011,8,5)
        aug31 = date(2011,8,31)
        sep2 = date(2011,9,2)
        aug122012 = date(2012,8,12)

        # start_date before end_date
        self.assertRaises(ValueError, approximate_month, aug31, aug5)

        # start_date & end_date equal
        self.assertRaises(ValueError, approximate_month, aug5, aug5)
        
        # start & end in same month
        self.assertEquals(approximate_month(aug5, aug31), Month(2011, 8))

        # start & end in successive months, more days in the first
        self.assertEquals(approximate_month(jul15, aug5), Month(2011, 7))

        # start & end in successive months, more days in the second
        self.assertEquals(approximate_month(jul15, aug31), Month(2011, 8))
        
        # start & end in successive months, same number of days: prefer the
        # first month
        self.assertEquals(approximate_month(aug31, sep2), Month(2011, 8))

        # start & end in non-successive months
        self.assertEquals(approximate_month(jul15, sep2), Month(2011, 8))

        # start & end very far apart: prefer first month with 31 days
        self.assertEquals(approximate_month(jul15, aug122012), Month(2011, 8))

    def test_months_of_past_year(self):
        self.assertEquals([Month(2011,2), Month(2011,3), Month(2011,4),
            Month(2011,5), Month(2011,6), Month(2011,7), Month(2011,8),
            Month(2011,9), Month(2011,10), Month(2011,11), Month(2011,12),
            Month(2012,1)], months_of_past_year(2012,1))

        self.assertEquals([Month(2011,3), Month(2011,4), Month(2011,5),
            Month(2011,6), Month(2011,7), Month(2011,8), Month(2011,9),
            Month(2011,10), Month(2011,11), Month(2011,12), Month(2012,1),
            Month(2012,2)], months_of_past_year(2012,2))

        self.assertEquals( [Month(2011,4), Month(2011,5), Month(2011,6),
            Month(2011,7), Month(2011,8), Month(2011,9), Month(2011,10),
            Month(2011,11), Month(2011,12), Month(2012,1), Month(2012,2),
            Month(2012,3)], months_of_past_year(2012,3))

        self.assertEquals([Month(2012,1), Month(2012,2), Month(2012,3),
            Month(2012,4), Month(2012,5), Month(2012,6), Month(2012,7),
            Month(2012,8), Month(2012,9), Month(2012,10), Month(2012,11),
            Month(2012,12)], months_of_past_year(2012,12))

    def test_month_arithmetic(self):
        # month +/- int = month
        self.assertEquals(Month(2012,1), Month(2012,1) + 0)
        self.assertEquals(Month(2012,1), Month(2012,1) - 0)
        self.assertEquals(Month(2012,2), Month(2012,1) + 1)
        self.assertEquals(Month(2012,3), Month(2012,1) + 2)
        self.assertEquals(Month(2012,12), Month(2012,1) + 11)
        self.assertEquals(Month(2013,1), Month(2012,1) + 12)
        self.assertEquals(Month(2013,2), Month(2012,1) + 13)
        self.assertEquals(Month(2011,11), Month(2012,6) -7)
        self.assertEquals(Month(2012,4), Month(2012,6) -2)
        self.assertEquals(Month(2012,6), Month(2012,6) + 0)
        self.assertEquals(Month(2012,8), Month(2012,6) + 2)
        self.assertEquals(Month(2013,2), Month(2012,6) + 8)
        self.assertEquals(Month(2015,1), Month(2012,12) + 25)

        # month +/- timedelta = datetime
        self.assertEquals(datetime(2012,1,2, 0), Month(2012,1) + timedelta(days=1))
        self.assertEquals(datetime(2012,1,3, 0), Month(2012,1) + timedelta(days=2))
        self.assertEquals(datetime(2012,1,31, 0), Month(2012,1) + timedelta(days=30))
        self.assertEquals(datetime(2012,2,1, 0), Month(2012,1) + timedelta(days=31))
        self.assertEquals(datetime(2011,12,31, 0), Month(2012,1) + timedelta(days=-1))
        self.assertEquals(datetime(2011,12,31, 0), Month(2012,1) - timedelta(days=1))
        self.assertEquals(datetime(2012,1,1, 1), Month(2012,1) + timedelta(hours=1))
        self.assertEquals(datetime(2012,1,2, 0), Month(2012,1) + timedelta(hours=24))
        self.assertEquals(datetime(2012,1,2, 1), Month(2012,1) + timedelta(hours=25))
        self.assertEquals(datetime(2011,12,31, 12), Month(2012,1) + timedelta(hours=-12))
        self.assertEquals(datetime(2011,12,31, 12), Month(2012,1) - timedelta(hours=12))

        # month - month = int
        self.assertEquals(0, Month(2012, 1) - Month(2012, 1))
        self.assertEquals(-1, Month(2012, 1) - Month(2012, 2))
        self.assertEquals(1, Month(2012, 1) - Month(2011, 12))
        self.assertEquals(6, Month(2012, 7) - Month(2012, 1))
        self.assertEquals(-6, Month(2012, 1) - Month(2012, 7))
        self.assertEquals(-12, Month(2012, 3) - Month(2013, 3))
        self.assertEquals(25, Month(2012, 12) - Month(2010, 11))

    def test_strftime(self):
        self.assertEquals('2012-01-01T00:00:00Z',
                Month(2012,1).strftime('%Y-%m-%dT%H:%M:%SZ'))

if __name__ == '__main__':
    unittest.main()
