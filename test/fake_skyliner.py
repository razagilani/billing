from random import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from skyliner.sky_handlers import cross_range

def random_hour_of_energy():
    '''In BTU.'''
    return 50000 * (1 + random())

class FakeSplinter(object):
    def __init__(self, random=True):
        self.random = random
        self._guru = FakeMonguru(random)

    def get_install_obj_for(self, olap_id):
        return FakeSkyInstall(random=self.random)

    def get_monguru(self):
        return self._guru
    guru = property(get_monguru)

class FakeSkyInstall(object):
    def __init__(self, random=True, *args, **kwargs):
        self.random = random
        self.name = 'Fake SkyInstall'

    #def get_billable_energy(self, day, hour_range=(0,24), places=5):
        #hours = hour_range[1] - hour_range[0]
        #if self.random:
            ## NOTE you can't pass a float into Decimal() in 2.6, only 2.7
            #energy = Decimal(str(random_hour_of_energy())) * hours
        #else:
            #energy = Decimal('100000') * hours
        #return energy.quantize(Decimal('1.'+'0'*places))

    def get_billable_energy_timeseries(self, start, end, places=None):
        if self.random:
            # NOTE you can't pass a float into Decimal() in 2.6, only 2.7
            return [(hour, Decimal(str(random_hour_of_energy()))) for hour in cross_range(start, end)]
        return [(hour, 100000) for hour in cross_range(start, end)]
            
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
    def __init__(self, random=True):
        self.random = random

    def get_data_for_hour(self, install, day, hour):
        if self.random:
            energy = random_hour_of_energy()
        else:
            energy = 100000
        return FakeCubeDocument(energy)

    def get_data_for_day(self, install, day):
        if self.random:
            energy = random_hour_of_energy() * 24
        else:
            energy = 100000 * 24
        return FakeCubeDocument(energy * 24)

    def get_data_for_week(self, install, year, week):
        raise NotImplementedError()

    def get_data_for_month(self, install, year, month):
        if self.random:
            energy = random_hour_of_energy() * 24
        else:
            energy = 100000 * 24
        return FakeCubeDocument(energy * 24 * 30)

