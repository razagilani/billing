



class UsePeriod(object):
    """Represents a quantity used over a certain time"""

    def __init__(self,  quantity, start_time, end_time):
        self.quantity = quantity
        self.start_time = start_time
        self.end_time = end_time


class GasUsePeriod(UsePeriod):
    units = 'therms'

    def __init__(self, quantity, start_time, end_time):
        super(GasUsePeriod, self).__init__(quantity, start_time, end_time)


class ElectricUsePeriod(UsePeriod):
    units = 'kwh'

    def __init__(self, quantity, start_time, end_time, peak_quantity,
                 off_peak_quantity):
        self.peak_quantity = peak_quantity
        self.off_peak_quantity = off_peak_quantity
        super(ElectricUsePeriod, self).__init__(quantity, start_time, end_time)