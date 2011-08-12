'''Month-related utility functions. estimate_month() can be used for deciding
which calendar month to associate with a utility billing period.'''
import calendar
from datetime import date
import unittest

def days_in_month(year, month, start_date, end_date):
    '''Returns the number of days in 'month' of 'year' between start_date and
    end_date (inclusive).'''
    # check that start_date <= end_date
    if start_date > end_date:
        raise ValueError("start_date can't be later than end_date")

    # if the month is before start_date's month or after end_date's month,
    # there are no days
    if (year < start_date.year) \
            or (year == start_date.year and month < start_date.month) \
            or (year == end_date.year and month > end_date.month) \
            or (year > end_date.year):
        return 0

    # if start_date and end_date are both in month, subtract their days
    if month == start_date.month and month == end_date.month:
        return end_date.day - start_date.day + 1
    
    # if month is the same as the start month, return number of days
    # between start_date and end of month
    if year == start_date.year and month == start_date.month:
        return calendar.monthrange(year, month)[1] - start_date.day + 1

    # if month is the same as the end month, return number of days between
    # beginning of moth and end_date
    if year == end_date.year and month == end_date.month:
        return end_date.day

    # otherwise just return number of days in the month
    return calendar.monthrange(year, month)[1]


def estimate_month(start_date, end_date):
    '''Returns the year and month of the month with the most days between
    start_date and end_date (as a (year, month) tuple).'''
    # check that start_date <= end_date
    if start_date > end_date:
        raise ValueError("start_date can't be later than end_date")
    
    # count days in each month between start_date and end_date, and return the
    # one with the most days
    max_year = max_month = None
    most_days = -1
    for year in range(start_date.year, end_date.year + 1):
        for month in range(1, 13):
            days = days_in_month(year, month, start_date, end_date)
            if days > most_days:
                most_days = days
                max_month = month
                max_year = year
    return max_year, max_month



class MonthTest(unittest.TestCase):
    def test_days_in_month(self):
        jul15 = date(2011,7,15)
        aug5 = date(2011,8,5)
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
        self.assertEqual(days_in_month(2011, 8, aug5, aug12), 8)

        # start_date & end_date equal
        self.assertEqual(days_in_month(2011, 8, aug12, aug12), 1)

        # start_date before end_date
        self.assertRaises(ValueError, days_in_month, 2011, 8, aug12, aug5)

        # start_date & end_date in successive months
        self.assertEquals(days_in_month(2011, 6, jul15, aug12), 0)
        self.assertEquals(days_in_month(2011, 7, jul15, aug12), 17)
        self.assertEquals(days_in_month(2011, 8, jul15, aug12), 12)
        self.assertEquals(days_in_month(2011, 9, jul15, aug12), 0)
        
        # start_date & end_date in non-successive months
        self.assertEquals(days_in_month(2011, 6, jul15, sep1), 0)
        self.assertEquals(days_in_month(2011, 7, jul15, sep1), 17)
        self.assertEquals(days_in_month(2011, 8, jul15, sep1), 31)
        self.assertEquals(days_in_month(2011, 9, jul15, sep1), 1)
        
        # start_date & end_date in different years
        self.assertEquals(days_in_month(2011, 6, jul15, aug122012), 0)
        self.assertEquals(days_in_month(2011, 7, jul15, aug122012), 17)
        for month in range(8,12):
            self.assertEquals(days_in_month(2011, month, jul15, aug122012), \
                    calendar.monthrange(2011, month)[1])
        for month in range(1,8):
            self.assertEquals(days_in_month(2012, month, jul15, aug122012), \
                    calendar.monthrange(2012, month)[1])
        self.assertEquals(days_in_month(2012, 8, jul15, aug122012), 12)

    def test_estimate_month(self):
        jul15 = date(2011,7,15)
        aug5 = date(2011,8,5)
        aug31 = date(2011,8,31)
        sep1 = date(2011,9,1)
        aug122012 = date(2012,8,12)

        # start_date before end_date
        self.assertRaises(ValueError, days_in_month, 2011, 8, aug31, aug5)

        # start & end in same month
        self.assertEquals(estimate_month(jul15, jul15), (2011, 7))

        # start & end in successive months, more days in the first
        self.assertEquals(estimate_month(jul15, aug5), (2011, 7))

        # start & end in successive months, more days in the second
        self.assertEquals(estimate_month(jul15, aug31), (2011, 8))
        
        # start & end in successive months, same number of days: prefer the
        # first month
        self.assertEquals(estimate_month(aug31, sep1), (2011, 8))

        # start & end in non-successive months
        self.assertEquals(estimate_month(jul15, sep1), (2011, 8))

        # start & end very far apart: prefer first month with 31 days
        self.assertEquals(estimate_month(jul15, aug122012), (2011, 8))

if __name__ == '__main__':
    unittest.main()
