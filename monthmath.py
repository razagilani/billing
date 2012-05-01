import calendar
from datetime import date, datetime, timedelta

# TODO: tests

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
        month.'''
        if isinstance(other, int):
            quotient, remainder = divmod(self.month + other, 12)
            return Month(self.year + quotient, (self.month + remainder) % 12)
        if isinstance(other, timedelta):
            return self.first() + other

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

    def __iter__(self):
        '''Generates days of the month.'''
        day = self.first
        while day <= self.last:
            yield day
            day += timedelta(1)

    @property
    def first(self):
        '''Returns the first day of the month (date).'''
        return date(self.year, self.month, 1)

    @property
    def last(self):
        '''Returns the last day of the month (date).'''
        return date(self.year, self.month, len(self))

    def strftime(self, format):
        return datetime.strftime(self.first(), format)
    
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

def approximate_month(start, end):
    '''Returns the month with the most days between 'start' and 'end'.'''
    # TODO move dateutils function into here
    from billing import dateutils
    return Month(*dateutils.estimate_month(start, end))

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
    # TODO move dateutils function into here
    from billing import dateutils
    return [Month(y,m) for (y,m) in dateutils.months_of_past_year(end_month.year, end_month.month)]

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
