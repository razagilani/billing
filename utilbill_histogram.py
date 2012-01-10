#!/usr/bin/python
'''Prints a histogram of bill period lengths in days using utility bills in the
MySQL database below.'''
from billing.processing.state import StateDB
state_db = StateDB({
    'host':'tyrell',
    'database':'skyline_stage',
    'user':'stage',
    'password':'stage'
})
histogram = {}
for account in state_db.listAccounts(state_db.session()):
    for ub in state_db.list_utilbills(state_db.session(), account)[0]:
        delta = ub.period_end - ub.period_start
        histogram[delta.days] = histogram.get(delta.days, 0) + 1

for length, count in sorted(histogram.items()):
    print '%s:\t%s' % (length, count)
