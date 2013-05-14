#!/usr/bin/python
from datetime import date, datetime, timedelta
'''Note that these objects have additional properties besides the ones defined
here, due to relationships defined in state.py.'''

class Customer(object):
    def __init__(self, name, account, discount_rate, late_charge_rate):
        self.name = name
        self.account = account
        self.discountrate = discount_rate
        self.latechargerate = late_charge_rate
    def __repr__(self):
        return '<Customer(name=%s, account=%s, discountrate=%s)>' \
                % (self.name, self.account, self.discountrate)

class ReeBill(object):
    def __init__(self, customer, sequence, version=0):
        self.customer = customer
        self.sequence = sequence
        self.issued = 0
        self.version = version
    def __repr__(self):
        return '<ReeBill(customer=%s, sequence=%s, version=%s, issued=%s)>' \
                % (self.customer, self.sequence, self.version, self.issued)

class UtilBill(object):
    '''Represents a particular version of a utility bill: either the current
    editable version, or a copy that is attached to a particular reebill
    version.'''

    # utility bill states:
    # 0. Complete: actual non-estimated utility bill.
    # 1. Utility estimated: actual utility bill whose contents were estimated by
    # the utility (and which will be corrected later to become Complete).
    # 2. Skyline estimated: a bill that is known to exist (and whose dates are
    # correct) but whose contents were estimated by Skyline.
    # 3. Hypothetical: Skyline supposes that there is probably a bill during a
    # certain time period and estimates what its contents would be if it existed.
    # Such a bill may not really exist (since we can't even know how many bills
    # there are in a given period of time), and if it does exist, its actual dates
    # will probably be different than the guessed ones.
    # TODO 38385969: not sure this strategy is a good idea
    Complete, UtilityEstimated, SkylineEstimated, Hypothetical = range(4)

    def __init__(self, customer, state, service, period_start=None,
            period_end=None, total_charges=0, date_received=None,
            reebill=None):
        '''State should be one of UtilBill.Complete, UtilBill.UtilityEstimated,
        UtilBill.SkylineEstimated, UtilBill.Hypothetical.'''
        # utility bill objects also have an 'id' property that SQLAlchemy
        # automatically adds from the database column
        self.customer = customer
        self.state = state
        self.service = service
        self.period_start = period_start
        self.period_end = period_end
        self.total_charges = total_charges
        self.date_received = date_received
        self.reebill = reebill # newly-created utilbill has NULL in reebill_id column

    @property
    def has_reebill(self):
        return self.reebill != None

    def __repr__(self):
        return '<UtilBill(customer=%s, service=%s, period_start=%s, period_end=%s)>' \
                % (self.customer, self.service, self.period_start, self.period_end)


class Payment(object):
    '''date_received is the datetime when Skyline recorded the payment.
    date_applied is the date that the payment is "for", from the customer's
    perspective. Normally these are on the same day, but an error in an old
    payment can be corrected by entering a new payment with the same
    date_applied as the old one, whose credit is the true amount minus the
    previously-entered amount.'''
    def __init__(self, customer, date_received, date_applied, description,
            credit):
        self.customer = customer
        self.date_received = date_received # datetime
        self.date_applied = date_applied   # date
        self.description = description
        self.credit = credit

    def to_dict(self):
        return {
            'id': self.id, 
            'date_received': self.date_received,
            'date_applied': self.date_applied,
            'description': self.description,
            'credit': self.credit,
            'editable': datetime.utcnow() - self.date_received < timedelta(hours=24)
        }

    def __repr__(self):
        return '<Payment(%s, %s, %s, %s, %s)>' \
                % (self.customer, self.date_received, \
                        self.date_applied, self.description, self.credit)

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

