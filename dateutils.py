'''Date/time/datetime-related utility functions.'''
import calendar
from datetime import date, datetime, timedelta
import unittest
import math

# convenient format strings
ISO_8601_DATETIME = '%Y-%m-%dT%H:%M:%SZ'
ISO_8601_DATE = '%Y-%m-%d'


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

def date_to_datetime(d):
    '''Returns a datetime whose date component is d and whose time component is
    midnight.'''
    return datetime(d.year, d.month, d.day, 0)

################################################################################
# timedeltas ###################################################################

def timedelta_in_hours(delta):
    '''Returns the given timedelta converted into hours, rounded toward 0 to
    the nearest integer.'''
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


#################################################################################
## iso 8601 and %W and week numbering #########################################

# python datetime module defines isocalendar() and isoweekday() but not year or
# week number
def iso_year(d):
    return d.isocalendar()[0]
def iso_week(d):
    return d.isocalendar()[1]

def iso_year_start(iso_year):
    '''Returns the Gregorian calendar date of the first day of the given ISO
    year. Note that the ISO year may start on a day that is in the previous
    Gregorian year! For example, ISO 2013 starts on Dec. 31 2012.'''
    jan4 = date(iso_year, 1, 4)
    return jan4 - timedelta(days=jan4.isoweekday()-1)

def iso_to_date(iso_year, iso_week, iso_weekday=1):
    '''Returns the gregorian calendar date for the given ISO year, week, and
    day. If day is not given, it is assumed to be the ISO week start.'''
    year_start = iso_year_start(iso_year)
    return year_start + timedelta(days=iso_weekday-1, weeks=iso_week-1)

def iso_to_datetime(iso_year, iso_week, iso_weekday=1):
    '''Returns the gregorian calendar date for the given ISO year, week, and
    day as a datetime (at midnight). If day is not given, it is assumed to be
    the ISO week start.'''
    return date_to_datetime(iso_to_date(iso_year, iso_week, iso_weekday))

def iso_week_generator(start, end):
    '''Yields ISO weeks as (year, weeknumber) tuples in [start, end), where
    start and end are (year, weeknumber) tuples.'''
    d = iso_to_date(*start)
    end_date = iso_to_date(*end)
    while d < end_date:
        year, week = d.isocalendar()[:2]
        yield (year, week)
        d = min(d + timedelta(days=7), iso_year_start(d.year + 1))

def w_week_number(d):
    '''Returns the date's "%W" week number. "%W" weeks start on Monday, but
    unlike in the ISO 8601 calendar, days before the first Monday of the year
    are considered to be in the same year but in week 0.'''
    return int(d.strftime('%W'))

def date_by_w_week(year, w_week, weekday):
    '''Returns the date specified by its year, "%W" week number, and 0-based
    "%w" weekday number, starting on Sunday. (Note that "%W" weeks start on
    Monday, so the weekday numbers of each "%W" week are 1,2,3,4,5,6,0. This
    may suck but it's necessary for compatibility with Skyliner.)'''
    if weekday not in range(7):
        # strptime doesn't report this error clearly
        raise ValueError('Invalid weekday: %s' % weekday)
    date_string = '%.4d %.2d %d' % (year, w_week, weekday)
    result = datetime.strptime(date_string, '%Y %W %w').date()
    if result.year != year or w_week_number(result) != w_week:
        raise ValueError('There is no weekday %s of week %s in %s' % (weekday,
            w_week, year))
    return result

def get_w_week_start(d):
    '''Returns the date of the first day of the "%W" week containing the date
    'd'.'''
    # "%W" weeks with numbers >= 1 start on Monday, but the "week 0" that
    # covers the days before the first Monday of the year always starts on the
    # first day of the year, no matter what weekday that is.
    if w_week_number(d) > 0:
        return date_by_w_week(d.year, w_week_number(d), 1)
    return date(d.year, 1, 1)

def next_w_week_start(d):
    '''Returns the date of the start of the next "%W" week following the date
    or datetime d. (If d is itself the start of a "%W" week, the next week's
    start is returned.)'''
    if type(d) is datetime:
        d = d.date()
    d2 = d
    while get_w_week_start(d2) == get_w_week_start(d):
        d2 += timedelta(days=1)
    return d2

#def length_of_w_week(year, w_week):
    #'''Returns the number of days in the given "%W" week.'''
    #if w_week == 0:
        ## star of week 0 is always Jan. 1
        #week_start == date(d.year, 1, 1)
    #else:
        ## every week other than 0 has a monday in it
        #week_start = get_w_week_start(year, w_week, 1)
    #(return next_w_week_start(week_start) - week_start).days

################################################################################
# months #######################################################################

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

def months_of_past_year(year, month):
    '''Returns a list of (year, month) tuples representing all months in the
    year preceding and including ('year', 'month') (and not including the same
    month in the previous year).'''
    result = []
    a_year = year - 1 if month < 12 else year
    a_month = month % 12 + 1 # i.e. the month after 'month' in 1-based numbering
    while a_year < year or (a_year == year and a_month <= month):
        result.append((a_year, a_month))
        if a_month == 12:
            a_year += 1
        a_month = a_month % 12 + 1
    return result


################################################################################
# federal holidays (for time-of-use billing) ###################################

def nth_weekday(n, weekday_number, month):
    '''Returns a function mapping years to the 'n'th weekday of 'month' in the
    given year, so holidays like "3rd monday of February" can be defined. 'n'
    is ether a 1-based index or the string "last"; 'weekday_number' is 0-based
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
    

# TODO move out of this file
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

    #import pprint
    #pprint.PrettyPrinter().pprint(sorted([(name, holiday(2011)) for holiday, name in FEDERAL_HOLIDAYS.iteritems()], key=lambda t:(t[1], t[0])))
    # TODO unit-test the holiday code
