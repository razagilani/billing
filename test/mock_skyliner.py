from random import Random, gauss
from math import ceil, log
from operator import add
from datetime import date, datetime, timedelta
from decimal import Decimal
from skyliner.sky_handlers import cross_range
from billing.util.monthmath import Month

def hour_of_energy(hour, deterministic=True):
    '''Returns a made-up energy value in BTU for the given hour (datetime). If
    'deterministic' is True, the value is always the same for a given hour.'''
    if deterministic:
        # use random number generator with fixed seed
        r = Random(hour.year + hour.month + hour.day + hour.hour)
        return max(0, r.gauss(3000, 1000))
    # use time-seeded random number generator in the 'random' module (different
    # every time)
    return max(0, gauss(3000, 1000))

class MockSplinter(object):
    def __init__(self, deterministic=True):
        self.deterministic = deterministic
        self._guru = MockMonguru(deterministic=deterministic)

    def get_install_obj_for(self, olap_id):
        return MockSkyInstall(deterministic=self.deterministic)

    def get_monguru(self):
        return self._guru
    guru = property(get_monguru)

class MockSkyInstall(object):
    def __init__(self, deterministic=True, *args, **kwargs):
        self.deterministic = deterministic
        self.name = 'Mock SkyInstall'

    def get_billable_energy_timeseries(self, start, end, places=None):
        # NOTE you can't pass a float into Decimal() in 2.6, only 2.7
        return [(hour, Decimal(str(hour_of_energy(hour,
                deterministic=self.deterministic))))
                for hour in cross_range(start, end)]

    @property
    def install_commissioned(self):
        return date(2000, 1, 1)

    def get_annotations(self):
        return []

class MockCubeDocument(object):
    def __init__(self, energy_sold):
        self.timestamp = datetime.utcnow()
        self.energy_sold = energy_sold

class MockMonguru(object):
    def __init__(self, deterministic=True):
        self.deterministic = deterministic

    def get_data_for_hour(self, install, day, hour):
        hour = datetime(day.year, day.month, day.day, hour)
        return MockCubeDocument(hour_of_energy(hour,
                deterministic=self.deterministic))

    def get_data_for_day(self, install, day):
        hours = [datetime(day.year, day.month, day.day, hour)
                for hour in range(24)]
        return MockCubeDocument(sum(hour_of_energy(hour,
                deterministic=self.deterministic) for hour in hours))

    def get_data_for_week(self, install, year, week):
        raise NotImplementedError()

    def get_data_for_month(self, install, year, month):
        hours = reduce(add, [[datetime(day.year, day.month, day.day, hour)
                for hour in range(24)] for day in Month(year, month)])
        return MockCubeDocument(sum(hour_of_energy(hour,
                deterministic=self.deterministic) for hour in hours))

if __name__ == '__main__':
    '''Print out 2 deterministic and 2 random values for each hour in January
    1-2, 2012.'''
    m1 = MockMonguru(deterministic=True)
    m2 = MockMonguru(deterministic=False)
    print '%19s %16s %16s %16s %16s' % ('hour', 'deterministic 1',
            'deterministic 2', 'random 1', 'random 2')
    for hour in cross_range(datetime(2012,1,1), datetime(2012,1,3)):
        day = date(hour.year, hour.month, hour.day)
        print '%19s: %16s %16s %16s %16s' % (hour,
            # these 2 are always the same
            m1.get_data_for_hour('name', day, hour.hour).energy_sold,
            m1.get_data_for_hour('name', day, hour.hour).energy_sold,
            # these 2 are different
            m2.get_data_for_hour('name', day, hour.hour).energy_sold,
            m2.get_data_for_hour('name', day, hour.hour).energy_sold
        )
