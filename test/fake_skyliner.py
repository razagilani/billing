from random import Random, gauss
from math import ceil, log
from operator import add
from datetime import date, datetime, timedelta
from decimal import Decimal
from skyliner.sky_handlers import cross_range
from billing.monthmath import Month
from sys import stderr

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

class FakeSplinter(object):
    def __init__(self, deterministic=True):
        self.deterministic = deterministic
        self._guru = FakeMonguru(deterministic=deterministic)

    def get_install_obj_for(self, olap_id):
        return FakeSkyInstall(deterministic=self.deterministic)

    def get_monguru(self):
        return self._guru
    guru = property(get_monguru)

class FakeSkyInstall(object):
    def __init__(self, deterministic=True, *args, **kwargs):
        self.deterministic = deterministic
        self.name = 'Fake SkyInstall'

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

class FakeCubeDocument(object):
    def __init__(self, energy_sold):
        self.timestamp = datetime.utcnow()
        self.energy_sold = energy_sold

class FakeMonguru(object):
    def __init__(self, deterministic=True):
        self.deterministic = deterministic

    def get_data_for_hour(self, install, day, hour):
        hour = datetime(day.year, day.month, day.day, hour)
        return FakeCubeDocument(hour_of_energy(hour,
                deterministic=self.deterministic))

    def get_data_for_day(self, install, day):
        hours = [datetime(day.year, day.month, day.day, hour)
                for hour in range(24)]
        return FakeCubeDocument(sum(hour_of_energy(hour,
                deterministic=self.deterministic) for hour in hours))

    def get_data_for_week(self, install, year, week):
        raise NotImplementedError()

    def get_data_for_month(self, install, year, month):
        hours = reduce(add, [[datetime(day.year, day.month, day.day, hour)
                for hour in range(24)] for day in Month(year, month)])
        return FakeCubeDocument(sum(hour_of_energy(hour,
                deterministic=self.deterministic) for hour in hours))
