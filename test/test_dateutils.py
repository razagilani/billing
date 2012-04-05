import unittest
import calendar
import math
from datetime import date, time, timedelta
from billing.dateutils import *

class DateUtilsTest(unittest.TestCase):
    def test_iso_year_start(self):
        self.assertEquals(date(2008,12,29), iso_year_start(2009))
        self.assertEquals(date(2010,1,4), iso_year_start(2010))
        self.assertEquals(date(2011,1,3), iso_year_start(2011))
        self.assertEquals(date(2012,1,2), iso_year_start(2012))
        self.assertEquals(date(2012,12,31), iso_year_start(2013))

    def test_iso_to_date(self):
        self.assertEquals(date(2012,1,2), iso_to_date(2012,1))
        self.assertEquals(date(2012,1,2), iso_to_date(2012,1, iso_weekday=1))
        self.assertEquals(date(2012,1,3), iso_to_date(2012,1, iso_weekday=2))
        self.assertEquals(date(2012,1,8), iso_to_date(2012,1, iso_weekday=7))

        self.assertEquals(date(2012,3,19), iso_to_date(2012,12))
        self.assertEquals(date(2012,3,19), iso_to_date(2012,12, iso_weekday=1))
        self.assertEquals(date(2012,3,25), iso_to_date(2012,12, iso_weekday=7))

        self.assertEquals(date(2012,12,24), iso_to_date(2012,52))
        self.assertEquals(date(2012,12,24), iso_to_date(2012,52, iso_weekday=1))
        self.assertEquals(date(2012,12,30), iso_to_date(2012,52, iso_weekday=7))

    def test_iso_week_generator(self):
        weeks = list(iso_week_generator((2012,1), (2013,1)))
        self.assertEquals(52, len(weeks))
        self.assertTrue(all(year == 2012 for (year, week) in weeks))
        self.assertEquals((2012,1), weeks[0])
        self.assertEquals((2012,2), weeks[1])
        self.assertEquals((2012,3), weeks[2])
        self.assertEquals((2012,50), weeks[49])
        self.assertEquals((2012,51), weeks[50])
        self.assertEquals((2012,52), weeks[51])
    
    def test_w_week(self):
        self.assertEquals(0, w_week_number(date(2012,1,1)))
        self.assertEquals(1, w_week_number(date(2012,1,2)))
        self.assertEquals(1, w_week_number(date(2012,1,3)))
        self.assertEquals(1, w_week_number(date(2012,1,7)))
        self.assertEquals(1, w_week_number(date(2012,1,8)))
        self.assertEquals(2, w_week_number(date(2012,1,9)))
        self.assertEquals(2, w_week_number(date(2012,1,15)))
        self.assertEquals(51, w_week_number(date(2012,12,23)))
        self.assertEquals(52, w_week_number(date(2012,12,24)))
        self.assertEquals(52, w_week_number(date(2012,12,30)))
        self.assertEquals(53, w_week_number(date(2012,12,31)))

        # 2018 has no week 0 because it starts on a Monday
        self.assertEquals(1, w_week_number(date(2018,1,1)))

    def test_date_by_w_week(self):
        # first day of 2012: Sunday in week 0
        self.assertEquals(date(2012,1,1), date_by_w_week(2012, 0, 0))

        # there is no Monday in week 0 of 2012
        self.assertRaises(ValueError, date_by_w_week, 2012, 0, 1)

        # first "real" week of 2012 is week 1: Monday Jan. 2 - Sunday Jan. 8
        self.assertEquals(date(2012,1,2), date_by_w_week(2012, 1, 1))
        self.assertEquals(date(2012,1,3), date_by_w_week(2012, 1, 2))
        self.assertEquals(date(2012,1,7), date_by_w_week(2012, 1, 6))
        self.assertEquals(date(2012,1,8), date_by_w_week(2012, 1, 0))

        # another week in 2012
        self.assertEquals(date(2012,3,19), date_by_w_week(2012, 12, 1))
        self.assertEquals(date(2012,3,20), date_by_w_week(2012, 12, 2))
        self.assertEquals(date(2012,3,24), date_by_w_week(2012, 12, 6))
        self.assertEquals(date(2012,3,25), date_by_w_week(2012, 12, 0))

        # end of 2012
        self.assertEquals(date(2012,12,23), date_by_w_week(2012, 51, 0))
        self.assertEquals(date(2012,12,24), date_by_w_week(2012, 52, 1))
        self.assertEquals(date(2012,12,30), date_by_w_week(2012, 52, 0))
        self.assertEquals(date(2012,12,31), date_by_w_week(2012, 53, 1))
        self.assertRaises(ValueError, date_by_w_week, 2012, 53, 2)
        self.assertRaises(ValueError, date_by_w_week, 2012, 53, 0)

        # 2018 has no week 0 because it starts on a Monday
        self.assertRaises(ValueError, date_by_w_week, 2018, 0, 1)
        self.assertRaises(ValueError, date_by_w_week, 2018, 0, 2)
        self.assertRaises(ValueError, date_by_w_week, 2018, 0, 6)
        self.assertRaises(ValueError, date_by_w_week, 2018, 0, 0)

    def test_get_w_week_start(self):
        self.assertEquals(date(2011,1,1), get_w_week_start(date(2011,1,1)))
        self.assertEquals(date(2011,1,1), get_w_week_start(date(2011,1,2)))
        self.assertEquals(date(2011,1,3), get_w_week_start(date(2011,1,3)))
        self.assertEquals(date(2011,1,3), get_w_week_start(date(2011,1,4)))
        self.assertEquals(date(2011,1,3), get_w_week_start(date(2011,1,9)))
        self.assertEquals(date(2011,1,10), get_w_week_start(date(2011,1,10)))
        self.assertEquals(date(2012,1,1), get_w_week_start(date(2012,1,1)))
        self.assertEquals(date(2012,1,2), get_w_week_start(date(2012,1,2)))
        self.assertEquals(date(2012,1,2), get_w_week_start(date(2012,1,3)))
        self.assertEquals(date(2018,1,1), get_w_week_start(date(2018,1,1)))

    def test_next_w_week_start(self):
        self.assertEquals(date(2012,1,1), next_w_week_start(date(2011,12,31)))
        self.assertEquals(date(2012,1,2), next_w_week_start(date(2012,1,1)))
        self.assertEquals(date(2012,1,9), next_w_week_start(date(2012,1,2)))
        self.assertEquals(date(2012,1,9), next_w_week_start(date(2012,1,3)))
        self.assertEquals(date(2012,1,9), next_w_week_start(date(2012,1,8)))
        self.assertEquals(date(2012,12,31), next_w_week_start(date(2012,12,24)))
        self.assertEquals(date(2012,12,31), next_w_week_start(date(2012,12,30)))
        self.assertEquals(date(2013,1,1), next_w_week_start(date(2012,12,31)))
        self.assertEquals(date(2018,1,8), get_w_week_start(date(2018,1,8)))

    def test_length_of_w_week(self):
        self.assertEquals(6, length_of_w_week(2011,52))
        self.assertEquals(1, length_of_w_week(2012,0))
        self.assertEquals(7, length_of_w_week(2012,1))
        self.assertEquals(7, length_of_w_week(2012,2))
        self.assertEquals(7, length_of_w_week(2012,3))
        self.assertEquals(7, length_of_w_week(2012,51))
        self.assertEquals(7, length_of_w_week(2012,52))
        self.assertEquals(1, length_of_w_week(2012,53))
        self.assertEquals(6, length_of_w_week(2013,0))
        self.assertEquals(7, length_of_w_week(2013,1))
        self.assertRaises(ValueError, length_of_w_week, 2018, 0)

    def test_days_in_month(self):
        jul15 = date(2011,7,15)
        aug5 = date(2011,8,5)
        aug6 = date(2011,8,6)
        aug12 = date(2011,8,12)
        sep1 = date(2011,9,1)
        aug122012 = date(2012,8,12)
        
        # previous year
        self.assertEqual(days_in_month(2010,7, jul15, sep1), 0)

        # month before start_date in same year
        self.assertEqual(days_in_month(2011,6, jul15, sep1), 0)

        # month after end_date in same year
        self.assertEqual(days_in_month(2011,10, jul15, sep1), 0)

        # next year
        self.assertEqual(days_in_month(2012, 8, jul15, sep1), 0)

        # start_date & end_date in same month
        self.assertEqual(days_in_month(2011, 8, aug5, aug12), 7)

        # start_date & end_date equal: error
        self.assertRaises(ValueError, days_in_month, 2011, 8, aug12, aug12)

        # start_date before end_date: error
        self.assertRaises(ValueError, days_in_month, 2011, 8, aug12, aug5)

        # start_date & end_date 1 day apart
        self.assertEqual(days_in_month(2011, 8, aug5, aug6), 1)

        # start_date & end_date in successive months
        self.assertEquals(days_in_month(2011, 6, jul15, aug12), 0)
        self.assertEquals(days_in_month(2011, 7, jul15, aug12), 17)
        self.assertEquals(days_in_month(2011, 8, jul15, aug12), 11)
        self.assertEquals(days_in_month(2011, 9, jul15, aug12), 0)
        
        # start_date & end_date in non-successive months
        self.assertEquals(days_in_month(2011, 6, jul15, sep1), 0)
        self.assertEquals(days_in_month(2011, 7, jul15, sep1), 17)
        self.assertEquals(days_in_month(2011, 8, jul15, sep1), 31)
        self.assertEquals(days_in_month(2011, 9, jul15, sep1), 0)
        
        # start_date & end_date in different years
        self.assertEquals(days_in_month(2011, 6, jul15, aug122012), 0)
        self.assertEquals(days_in_month(2011, 7, jul15, aug122012), 17)
        for month in range(8,12):
            self.assertEquals(days_in_month(2011, month, jul15, aug122012), \
                    calendar.monthrange(2011, month)[1])
        for month in range(1,8):
            self.assertEquals(days_in_month(2012, month, jul15, aug122012), \
                    calendar.monthrange(2012, month)[1])
        self.assertEquals(days_in_month(2012, 8, jul15, aug122012), 11)

    def test_estimate_month(self):
        jul15 = date(2011,7,15)
        aug5 = date(2011,8,5)
        aug31 = date(2011,8,31)
        sep2 = date(2011,9,2)
        aug122012 = date(2012,8,12)

        # start_date before end_date
        self.assertRaises(ValueError, days_in_month, 2011, 8, aug31, aug5)

        # start_date & end_date equal
        self.assertRaises(ValueError, days_in_month, 2011, 8, aug5, aug5)
        
        # start & end in same month
        self.assertEquals(estimate_month(aug5, aug31), (2011, 8))

        # start & end in successive months, more days in the first
        self.assertEquals(estimate_month(jul15, aug5), (2011, 7))

        # start & end in successive months, more days in the second
        self.assertEquals(estimate_month(jul15, aug31), (2011, 8))
        
        # start & end in successive months, same number of days: prefer the
        # first month
        self.assertEquals(estimate_month(aug31, sep2), (2011, 8))

        # start & end in non-successive months
        self.assertEquals(estimate_month(jul15, sep2), (2011, 8))

        # start & end very far apart: prefer first month with 31 days
        self.assertEquals(estimate_month(jul15, aug122012), (2011, 8))

    def test_months_of_past_year(self):
        self.assertEquals(
            [(2011,2), (2011,3), (2011,4), (2011,5), (2011,6), (2011,7),
            (2011,8), (2011,9), (2011,10), (2011,11), (2011,12), (2012,1)],
            months_of_past_year(2012,1))
        self.assertEquals(
            [(2011,3), (2011,4), (2011,5), (2011,6), (2011,7), (2011,8),
            (2011,9), (2011,10), (2011,11), (2011,12), (2012,1), (2012,2)],
            months_of_past_year(2012,2))
        self.assertEquals(
            [(2011,4), (2011,5), (2011,6), (2011,7), (2011,8), (2011,9),
            (2011,10), (2011,11), (2011,12), (2012,1), (2012,2), (2012,3)],
            months_of_past_year(2012,3))
        self.assertEquals(
            [(2012,1), (2012,2), (2012,3), (2012,4), (2012,5), (2012,6),
            (2012,7), (2012,8), (2012,9), (2012,10), (2012,11), (2012,12)],
            months_of_past_year(2012,12))

    def test_month_offset(self):
        self.assertEquals((2012,1), month_offset(2012,1, 0))
        self.assertEquals((2012,2), month_offset(2012,1, 1))
        self.assertEquals((2012,3), month_offset(2012,1, 2))
        self.assertEquals((2012,12), month_offset(2012,1, 11))
        self.assertEquals((2013,1), month_offset(2012,1, 12))
        self.assertEquals((2013,2), month_offset(2012,1, 13))
        self.assertEquals((2011,11), month_offset(2012,6, -7))
        self.assertEquals((2012,4), month_offset(2012,6, -2))
        self.assertEquals((2012,6), month_offset(2012,6, 0))
        self.assertEquals((2012,8), month_offset(2012,6, 2))
        self.assertEquals((2013,2), month_offset(2012,6, 8))
        self.assertEquals((2015,1), month_offset(2012,12, 25))

    def test_month_difference(self):
        self.assertEquals(0, month_difference(2012, 1, 2012, 1))
        self.assertEquals(1, month_difference(2012, 1, 2012, 2))
        self.assertEquals(-1, month_difference(2012, 1, 2011, 12))
        self.assertEquals(6, month_difference(2012, 1, 2012, 7))
        self.assertEquals(12, month_difference(2012, 3, 2013, 3))
        self.assertEquals(-25, month_difference(2012, 12, 2010, 11))

    def test_date_generator(self):
        oct1 = date(2011,10,1)
        oct2 = date(2011,10,2)
        oct27 = date(2011,10,27)
        oct28 = date(2011,10,28)
        self.assertEquals([], list(date_generator(oct1, oct1)))
        self.assertEquals([oct1], list(date_generator(oct1, oct2)))
        self.assertEquals(27, len(list(date_generator(oct1, oct28))))
        self.assertEquals(oct1, list(date_generator(oct1, oct28))[0])
        self.assertEquals(oct2, list(date_generator(oct1, oct28))[1])
        self.assertEquals(oct27, list(date_generator(oct1, oct28))[-1])
        self.assertEquals([], list(date_generator(oct28, oct2)))

    def test_nth_weekday(self):
        sat_oct1 = date(2011,10,1)
        sat_oct8 = date(2011,10,8)
        sat_oct15 = date(2011,10,15)
        sat_oct22 = date(2011,10,22)
        sat_oct29 = date(2011,10,29)
        fri_oct7 = date(2011,10,7)
        fri_oct14 = date(2011,10,14)
        fri_oct21 = date(2011,10,21)
        fri_oct28 = date(2011,10,28)
        wed_oct26 = date(2011,10,26)
        mon_oct31 = date(2011,10,31)

        self.assertEquals([sat_oct1, sat_oct8, sat_oct15, sat_oct22, sat_oct29],
                [nth_weekday(n, 6, 10)(2011) for n in [1,2,3,4,5]])
        self.assertRaises(IndexError, nth_weekday(-1, 6, 10), 2011)
        self.assertRaises(IndexError, nth_weekday(0, 6, 10), 2011)
        self.assertRaises(IndexError, nth_weekday(6, 6, 10), 2011)
        self.assertEquals([fri_oct7, fri_oct14, fri_oct21, fri_oct28],
                [nth_weekday(n, 5, 10)(2011) for n in [1,2,3,4]])
        self.assertRaises(IndexError, nth_weekday(-1, 5, 10), 2011)
        self.assertRaises(IndexError, nth_weekday(0, 5, 10), 2011)
        self.assertRaises(IndexError, nth_weekday(5, 5, 10), 2011)
        self.assertEquals(wed_oct26, nth_weekday('last', 3, 10)(2011))
        self.assertEquals(mon_oct31, nth_weekday('last', 1, 10)(2011))

        self.assertEquals(date(2013,2,18), nth_weekday(3,1,2)(2013))

if __name__ == '__main__':
    unittest.main()

