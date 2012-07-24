from random import random
from datetime import date, datetime, timedelta
from decimal import Decimal

def one_hour_of_energy():
    '''In BTU.'''
    return 50000 * (1 + random())

class FakeSplinter(object):
    def __init__(self, random=True):
        self.random = random
        self.monguru = FakeMonguru()

    def get_install_obj_for(self, olap_id):
        return FakeSkyInstall(random=self.random)

    def get_monguru(self):
        return self.monguru

class FakeSkyInstall(object):
    def __init__(self, random=True, *args, **kwargs):
        self.random = random

    def get_billable_energy(self, day, hour_range=(0,24), places=5):
        hours = hour_range[1] - hour_range[0]

        if self.random:
            # NOTE you can't pass a float into Decimal() in 2.6, only 2.7
            energy = Decimal(str(one_hour_of_energy())) * hours
        else:
            energy = Decimal('100000') * hours

        return energy.quantize(Decimal('1.'+'0'*places))

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
    def get_data_for_hour(self, install, day, hour):
        return FakeCubeDocument(one_hour_of_energy())

    def get_data_for_day(self, install, day):
        return FakeCubeDocument(one_hour_of_energy() * 24)

    def get_data_for_week(self, install, year, week):
        raise NotImplementedError()

    def get_data_for_month(self, install, year, month):
        return FakeCubeDocument(one_hour_of_energy() * 24 * 30)

if __name__ == '__main__':
    splinter = FakeSplinter()
    install = splinter.get_install_obj_for('fake')
    print install.get_billable_energy(datetime.utcnow())

    monguru = splinter.get_monguru()
    now = datetime.utcnow()
    print monguru.get_data_for_hour(install, now.date(), now.hour).energy_sold
    print monguru.get_data_for_day(install, now.date()).energy_sold
    print monguru.get_data_for_month(install, now.year, now.month).energy_sold
