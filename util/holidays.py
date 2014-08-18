''' How we keep track of federal holidays for time-of-use billing.'''
from datetime import date
from dateutils import nth_weekday

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
