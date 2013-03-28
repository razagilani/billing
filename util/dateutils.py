'''Date/time/datetime-related utility functions. Tests for this file are in
test/test_dateutil.py (remember to move it if this goes outside billing).'''
import calendar
from datetime import date, datetime, timedelta
import unittest
import math

# convenient format strings
ISO_8601_DATE = '%Y-%m-%d'
ISO_8601_DATETIME = '%Y-%m-%dT%H:%M:%SZ'
ISO_8601_DATETIME_WITHOUT_ZONE = '%Y-%m-%dT%H:%M:%S'

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


################################################################################
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

def length_of_w_week(year, w_week):
    '''Returns the number of days in the given "%W" week.'''
    if w_week == 0:
        # start of week 0 is always Jan. 1, but week 0 may not always exist
        week_start = date(year, 1, 1)
        if week_start.weekday() == 0:
            raise ValueError('%s has no week 0' % year)
    else:
        # every week other than 0 has a monday in it
        week_start = get_w_week_start(date_by_w_week(year, w_week, 1))
    return (next_w_week_start(week_start) - week_start).days

################################################################################
# months #######################################################################

# TODO remove: this has become monthmath.Month.overlap_with_period
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

# TODO remove; has gone into monthmath.approximate_month
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

# TODO remove; has gone into monthmath
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

# TODO remove; replaced with arithmetic on monthmath.Months
def month_offset(year, month, number_of_months):
    '''Returns the month that occurs 'number_of_months' after 'month' of 'year'
    as a (year, month) tuple. 'number_of_months' may be negative. For example,
    to find the month that occurs 10 months after (2012,4), you call
    month_offset(2012,4,10), and the result is (2013,2).'''
    year_offset, result_month_index = divmod(month + number_of_months - 1, 12)
    return year + year_offset, result_month_index + 1

# TODO remove; replaced with arithmetic on monthmath.Months
def month_difference(year1, month1, year2, month2):
    '''Returns the number of months between (year1, month1) and (year2,
    month2). For example, month_difference(2012, 3), month_difference(2012,
    3).'''
    year_difference = year2 - year1
    month_difference = month2 - month1
    return year_difference * 12 + month_difference

# TODO move into monthmath?
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



if __name__ == '__main__':
    unittest.main()

    #import pprint
    #pprint.PrettyPrinter().pprint(sorted([(name, holiday(2011)) for holiday, name in FEDERAL_HOLIDAYS.iteritems()], key=lambda t:(t[1], t[0])))
    # TODO unit-test the holiday code
