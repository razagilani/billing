import calendar
from datetime import date, datetime, timedelta

# TODO:
# iso week, %w week iterators
# move nth_weekday from dateutils here and make it a method of Month

class Month(object):
    
    def __init__(self, *args):
        if len(args) == 1:
            if isinstance(args[0], date) or isinstance(args[0], datetime):
                self.year = args[0].year
                self.month = args[0].month
            elif map(type, args[0]) in [(int, int), [int, int]]:
                self.year, self.month = args[0]
            else:
                raise ValueError(('Single argument must be a date, datetime,'
                        ' or (year, month) tuple/list'))
        elif len(args) == 2:
            if not isinstance(args[0], int) or not isinstance(args[1], int):
                raise ValueError(('Pair of arguments must be integers (year,'
                ' month)'))
            if args[1] < 1 or args[1] > 12:
                raise ValueError('Illegal month number %s (must be in 1..12)' %
                        args[1])
            self.year = args[0]
            self.month = args[1]
        else:
            raise ValueError('Arguments must be date, datetime, or year and month numbers')
        self._calendar = calendar.Calendar()

    def __repr__(self):
        return 'Month<(%s, %s)>' % (self.year, self.month)

    def __str__(self):
        return '%s %s' % (calendar.month_name[self.month], self.year)

    def __cmp__(self, other):
        '''A Month can be compared to another Month or a (year, month)
        tuple.'''
        if type(other) is tuple:
            return cmp((self.year, self.month), other)
        return cmp((self.year, self.month), (other.year, other.month))

    def __add__(self, other):
        '''Adding a Month to an int x returns the Month x months later. Adding a
        timedelta returns that amount of time after midnight on the first of the
        month (a datetime).'''
        if isinstance(other, int):
            # extra years are the whole quotient left over after integer
            # division by 12. month is the remainder, but it's in 0-based
            # numbering, so add 1 to convert it to 1-based.
            quotient, remainder = divmod(self.month + other - 1, 12)
            return Month(self.year + quotient, remainder + 1)
        if isinstance(other, timedelta):
            # date + timedelta = date (rounded to the nearest day), so convert
            # the date into a datetime before adding
            first = self.first
            return datetime(first.year, first.month, first.day) + other

    def __sub__(self, other):
        '''Subtracting two months gives the number of months difference (int).
        Subtracting an int from a Month gives a Month that many months earlier.
        Subtracting a month gives a month 0.'''
        if isinstance(other, Month):
            year_difference = self.year - other.year
            month_difference = self.month - other.month
            return 12 * year_difference + month_difference
        return self + (- other)

    def __len__(self):
        '''Returns the number of days in the month.'''
        return calendar.monthrange(self.year, self.month)[1]

    # TODO iterate by other time units, like weeks or hours
    def __iter__(self):
        '''Generates days of the month.'''
        day = self.first
        while day <= self.last:
            yield day
            day += timedelta(1)

    def __hash__(self):
        return hash((self.year, self.month))

    def overlap_with_period(self, start_date, end_date):
        '''Returns the number of days in this month between start_date
        (inclusive) and end_date (exclusive).'''
        # check that start_date < end_date
        if start_date >= end_date:
            raise ValueError("end date must be later than start date")

        # if the month is before start_date's month or after end_date's month,
        # there are no days
        if (self.year < start_date.year) \
                or (self.year == start_date.year and self.month < start_date.month) \
                or (self.year == end_date.year and self.month > end_date.month) \
                or (self.year > end_date.year):
            return 0

        # if start_date and end_date are both in month, subtract their days
        if self.month == start_date.month and self.month == end_date.month:
            return end_date.day - start_date.day
        
        # if month is the same as the start month, return number of days
        # between start_date and end of month (inclusive)
        if self.year == start_date.year and self.month == start_date.month:
            return calendar.monthrange(self.year, self.month)[1] - start_date.day + 1

        # if month is the same as the end month, return number of days between
        # beginning of moth and end_date (exclusive)
        if self.year == end_date.year and self.month == end_date.month:
            return end_date.day - 1

        # otherwise just return number of days in the month
        return calendar.monthrange(self.year, self.month)[1]

    @property
    def first(self):
        '''Returns the first day of the month (date).'''
        return date(self.year, self.month, 1)

    @property
    def last(self):
        '''Returns the last day of the month (date).'''
        return date(self.year, self.month, len(self))

    def strftime(self, format):
        return datetime.strftime(self.first, format)
    
    @property
    def name(self):
        '''Returns the English full name of the month (e.g. "January").'''
        return calendar.month_name[self.month]

    @property
    def abbr(self):
        '''Returns the English abbreviation for the month (e.g. "Jan").'''
        return calendar.month_abbr[self.month]

def current_utc():
    '''Returns the current UTC month.'''
    return Month(datetime.utcnow())

def months_of_year(year):
    return [Month(year, i) for i in range(1,13)]

def approximate_month(start_date, end_date):
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
            days = Month(year, month).overlap_with_period(start_date, end_date)
            if days > most_days:
                most_days = days
                max_month = month
                max_year = year
    return Month(max_year, max_month)

# TODO replace with some kind of general month iterator function (like
# dateutils.date_generator but for months)
def months_of_past_year(*args):
    '''Returns a list of all Months in the year preceding and including the
    given Month or year and month. (not including the same month in the
    previous year, so there are always 12 months). With no arguments, returns
    the last 12 months from the present UTC month.'''
    if args == ():
        end_month = current_utc()
    elif len(args) == 1:
        end_month = args[0]
    elif len(args) == 2:
        end_month = Month(*args)
    else:
        raise ValueError('Arguments must be a Month or year and month numbers: %s' % args)
    #return _months_of_past_year(end_month.year, end_month.month)
    result = []
    a_year = end_month.year - 1 if end_month.month < 12 else end_month.year
    a_month = end_month.month % 12 + 1 # i.e. the month after 'month' in 1-based numbering
    while a_year < end_month.year or (a_year == end_month.year and a_month <=
            end_month.month):
        result.append(Month(a_year, a_month))
        if a_month == 12:
            a_year += 1
        a_month = a_month % 12 + 1
    return result


if __name__ == '__main__':
    #import pdb; pdb.set_trace()
    print Month((2012,1))
    print Month([2012,1])
    print Month(2012,1)
    print Month(date(2012,1,5))
    print Month(datetime(2012,1,5,6))
    m = Month(2012,1)
    #print m - 3
    #print m + 50
    #print len(m)
    #print m.first()
    #print m.last()
    #print Month(2012,10) - Month(2012,5)
    #for m in months_of_year(2012):
        #print m, m.name, m.abbr
    for day in m:
        print day
