#!/usr/bin/python
'''Note that these objects have additional properties besides the ones defined
here, due to relationships defined in state.py.'''

class Customer(object):
    def __init__(self, name, account, discountrate):
        self.name = name
        self.account = account
        self.discountrate = discountrate
    def __repr__(self):
        return '<Customer(%s, %s, %s)>' \
                % (self.name, self.account, self.discountrate)
class ReeBill(object):
    def __init__(self, customer, sequence):
        self.customer = customer
        self.sequence = sequence
        self.issued = 0
    def __repr__(self):
        return '<ReeBill(%s, %s, %s)>' \
                % (self.customer, self.sequence, self.issued)
class UtilBill(object):
    def __init__(self, customer, period_start, period_end, \
            estimated, processed, received):
        self.customer = customer
        self.period_start = period_start
        self.period_end = period_end
        self.estimated = estimated
        self.received = received
    def __repr__(self):
        return '<UtilBill(%s, %s, %s)>' \
                % (self.customer, self.period_start, self.period_end)

class Payment(object):
    def __init__(self, customer, date, description, credit):
        self.customer = customer
        self.date = date
        self.description = description
        self.credit = credit
    def __repr__(self):
        return '<Payment(%s, %s, %s, %s)>' \
                % (self.customer, self.date, \
                        self.description, self.credit)

class StatusUnbilled(object):
    def __init__(self, account):
        self.account = account
    def __repr__(self):
        return '<StatusUnbilled(%s)>' \
                % (self.account)

class StatusDaysSince(object):
    def __init__(self, account, dayssince):
        self.account = account
        self.dayssince = dayssince
    def __repr__(self):
        return '<StatusDaysSince(%s, %s)>' \
                % (self.account, self.dayssince)

