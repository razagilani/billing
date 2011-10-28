'''Date-related utility functions.'''
import calendar
from datetime import date, timedelta
import unittest

def days_in_month(year, month, start_date, end_date):
    '''Returns the number of days in 'month' of 'year' between start_date
    (inclusive) and end_date (exclusive).'''
    # check that start_date < end_date
    if start_date >= end_date:
        raise ValueError("end date must be later than start date")

    # if the month is before start_date's month or after end_date's month,
    # there are no days
    if (year < start_date.year) \
            or (year == start_date.year and month < start_date.month) \
            or (year == end_date.year and month > end_date.month) \
            or (year > end_date.year):
        return 0

    # if start_date and end_date are both in month, subtract their days
    if month == start_date.month and month == end_date.month:
        return end_date.day - start_date.day
    
    # if month is the same as the start month, return number of days
    # between start_date and end of month (inclusive)
    if year == start_date.year and month == start_date.month:
        return calendar.monthrange(year, month)[1] - start_date.day + 1

    # if month is the same as the end month, return number of days between
    # beginning of moth and end_date (exclusive)
    if year == end_date.year and month == end_date.month:
        return end_date.day - 1

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





def date_generator(from_date, to_date):
    """Yield dates based on from_date up to and excluding to_date.  The reason
    for the exclusion of to_date is that utility billing periods do not include
    the whole day for the end date specified for the period.  That is, the
    utility billing period range of 2/15 to 3/4, for example, is for the usage
    at 0:00 2/15 to 0:00 3/4.  0:00 3/4 is before the 3/4 begins."""
    if (from_date > to_date):
        return
    while from_date < to_date:
        yield from_date
        from_date = from_date + timedelta(days = 1)
    return

def nth_weekday(n, weekday_number, month):
    '''Returns a function mapping years to the 'n'th weekday of 'month' in the
    given year, so holidays like "3rd monday of February" can be defined
    without dealing with the insanity of the Python calendar library. 'n' is
    ether a 1-based index or the string "last"; weekday_number is 0-based
    starting at Sunday.'''
    cal = calendar.Calendar()
    def result(year):
        # calendar.itermonthdays2() returns (day number, weekday number)
        # tuples, where days outside the month are included (with day number =
        # 0) to get a complete week. as if that weren't bad enough, weekdays
        # are 0-indexed starting at monday (european-style, apparently). also
        # note that calendar.setfirstweekday(calendar.SUNDAY) has no effect.
        days = [day[0] for day in cal.itermonthdays2(year, month)
                if day[0] != 0 and day[1] == (weekday_number + 6) % 7]
        return date(year, month, days[-1 if n == 'last' else n-1])
    return result

# for time-of-use billing, holidays are stored as functions mapping a year to a
# date within the year: this allows potentially arbitarily rules (such as
# holiday dates changing from one year to another) with the reasonable
# assumption that a holiday occurs at most once per year (you could return None
# if it does not occur at all).
# for simplicity, we're assuming that utility billing holidays match defined
# federal holiday dates, not the dates on which federal employees get a
# vacation. this decision is not based on actual data, so we may have to
# correct it later.

# the names (values in the dictionary below) just serve as documentation.
HOLIDAYS = {
    # fixed-date holidays: date is independent of year
    lambda year: date(year, 1, 1) : "New Year's Day",
    lambda year: date(year, 7, 4) : "Independence Day",
    lambda year: date(year, 11, 11) : "Veterans' Day",
    lambda year: date(year, 12, 25) : "Christmas Day",

    # "nth weekday of month" holidays: nth_weekday(n, weekday, month)
    nth_weekday(3, 1, 1): "Martin Luther King Day",
    nth_weekday(3, 1, 2): "Presidents' Day",
    nth_weekday('last', 1, 5): "Memorial Day",
    nth_weekday(1, 1, 9): "Labor Day",
    nth_weekday(2, 1, 10): "Columbus Day",
    nth_weekday(4, 5, 11): "Thanksgiving Day"
}

def all_holidays(year):
    '''Returns all the holidays in the given year as a list of dates.'''
    return [holiday(year) for holiday in HOLIDAYS if holiday(year) is not None]

def get_day_type(day):
    '''Returns 'weekday', 'weekend', or 'holiday' to classify the given date.
    Holidays override regular weekday/weekend classifications.'''
    if day in all_holidays(day.year):
        return 'holiday'
    # python weeks start on monday
    if day.weekday() in [5,6]:
        return 'weekend'
    return 'weekday'
    


if __name__ == '__main__':
    unittest.main()

    # manual holiday test. check against:
    # http://www.opm.gov/Operating_Status_Schedules/fedhol/2011.asp
    # http://www.opm.gov/oca/worksch/html/holiday.asp
    import pprint
    pprint.PrettyPrinter().pprint(sorted([(name, holiday(2011)) for holiday, name in HOLIDAYS.iteritems()], key=lambda t:(t[1], t[0])))
    # TODO unit-test the holiday code
