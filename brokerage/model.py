


class ServiceLocation():
    pass

class QuantityUse(object):
    """Represents a quantity use at a certain location"""

    def __init__(self,  quantity_used, address, start_time, end_time):
        self.quantity_used = quantity_used
        self.address = address
        self.start_time = start_time
        self.end_time = end_time


class GasUsePeriod(object):
    """"""
    def __init__(self):