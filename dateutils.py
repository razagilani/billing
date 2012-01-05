'''Date/time/datetime-related utility functions.'''
import calendar
from datetime import date, timedelta
import unittest

def timedelta_in_hours(delta):
    '''Returns the given timedelta converted into hours, rounded toward 0 to
    the nearest integer. (Used by scripts/deck/deck_uploader.py)'''
    # a timedelta stores time in days and seconds. each of these can be
    # positive or negative. convert each part into hours and round it toward 0.
    # (this is ugly because python rounding goes toward negative infinity by
    # default.)
    day_hours = delta.days * 24
    second_hours = delta.seconds / 3600.0
    total_hours = day_hours + second_hours
    # note: if you try to round these components separately and then add them,
    # you will get a strange result, because of timedelta's internal
    # representation: e.g. -1 second is represented as -1 days (negative) +
    # 86399 seconds (positive)
    if total_hours >= 0:
        return int(math.floor(total_hours))
    return - int(math.floor(abs(total_hours)))

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

def date_generator(from_date, to_date):
    """Yields dates based on from_date up to but excluding to_date.  The reason
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
        if type(n) is int and n-1 not in range(len(days)):
            raise IndexError("there's no %sth %sday of month %s in %s" % (
                n, weekday_number, month, year))
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
# this appears to be the official source for holiday dates:
# http://www.law.cornell.edu/uscode/5/6103.html

# the names (values in the dictionary below) just serve as documentation.
FEDERAL_HOLIDAYS = {
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
    nth_weekday(4, 4, 11): "Thanksgiving Day"
}

def all_holidays(year):
    '''Returns all the holidays in the given year as a set of dates.'''
    return set([holiday(year) for holiday in FEDERAL_HOLIDAYS
        if holiday(year) is not None])

def get_day_type(day):
    '''Returns "weekday", "weekend", or "holiday" to classify the given date.
    Holidays override regular weekday/weekend classifications.'''
    if day in all_holidays(day.year):
        return 'holiday'
    # python weeks start on monday
    if day.weekday() in [5,6]:
        return 'weekend'
    return 'weekday'
    


class DateUtilsTest(unittest.TestCase):
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

    def test_all_holidays(self):
        # source of holiday dates:
        # http://www.opm.gov/oca/worksch/html/holiday.asp
        # (note that some sources, such as
        # http://www.opm.gov/Operating_Status_Schedules/fedhol/2011.asp
        # report federal employee vacation days, which may differ from the
        # holidays themselves. we assume that utility billing holidays are the
        # actual holiday dates.)
        
        # 2013
        newyear11 = date(2011, 1, 1)
        mlk11 = date(2011, 1, 17)
        washington11 = date(2011, 2, 21)
        memorial11 = date(2011, 5, 30)
        independence11 = date(2011, 7, 4)
        labor11 = date(2011, 9, 5)
        columbus11 = date(2011, 10, 10)
        veterans11 = date(2011, 11, 11)
        thanks11 = date(2011, 11, 24)
        xmas11 = date(2011, 12, 25)
        all_2011 = set([newyear11, mlk11, washington11, memorial11,
            independence11, labor11, columbus11, veterans11, thanks11, xmas11])
        self.assertEquals(all_2011, all_holidays(2011))
        
        # 2012
        newyear12 = date(2012, 1, 1)
        mlk12 = date(2012, 1, 16)
        washington12 = date(2012, 2, 20)
        memorial12 = date(2012, 5, 28)
        independence12 = date(2012, 7, 4)
        labor12 = date(2012, 9, 3)
        columbus12 = date(2012, 10, 8)
        veterans12 = date(2012, 11, 11)
        thanks12 = date(2012, 11, 22)
        xmas12 = date(2012, 12, 25)
        all_2012 = set([newyear12, mlk12, washington12, memorial12,
            independence12, labor12, columbus12, veterans12, thanks12, xmas12])
        self.assertEquals(all_2012, all_holidays(2012))
        
        # 2013
        # manually checked
        newyear13 = date(2013, 1, 1)
        mlk13 = date(2013, 1, 21)
        washington13 = date(2013, 2, 18)
        memorial13 = date(2013, 5, 27)
        independence13 = date(2013, 7, 4)
        labor13 = date(2013, 9, 2)
        columbus13 = date(2013, 10, 14)
        veterans13 = date(2013, 11, 11)
        thanks13 = date(2013, 11, 28)
        xmas13 = date(2013, 12, 25)
        all_2013 = set([newyear13, mlk13, washington13, memorial13,
            independence13, labor13, columbus13, veterans13, thanks13, xmas13])
        self.assertEquals(all_2013, all_holidays(2013))


if __name__ == '__main__':
    unittest.main()

    import pprint
    pprint.PrettyPrinter().pprint(sorted([(name, holiday(2011)) for holiday, name in FEDERAL_HOLIDAYS.iteritems()], key=lambda t:(t[1], t[0])))
    # TODO unit-test the holiday code
