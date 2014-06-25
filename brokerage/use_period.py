



class UsePeriod(object):
    """Represents a quantity used over a certain time"""

    def __init__(self,  quantity, start_time, end_time, peak_quantity=None,
                 off_peak_quantity=None):
        self.quantity = quantity
        self.start_time = start_time
        self.end_time = end_time
        self.peak_quantity = peak_quantity
        self.off_peak_quantity = off_peak_quantity
