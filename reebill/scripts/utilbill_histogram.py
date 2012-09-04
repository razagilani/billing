#!/usr/bin/python
'''Prints histograms of bill period lengths in days and the day-of-month
components of utility bill start and end dates, using utility bills in the
MySQL database below.'''
from billing.processing.state import StateDB
state_db = StateDB(
    host='tyrell',
    database='skyline_stage',
    user='stage',
    password='stage'
)

print 'Period lenth distribution (days):'
length_histogram = {}
total = 0
count = 0
for account in state_db.listAccounts(state_db.session()):
    for ub in state_db.list_utilbills(state_db.session(), account)[0]:
        delta = ub.period_end - ub.period_start
        length_histogram[delta.days] = length_histogram.get(delta.days, 0) + 1
        total += delta.days
        count += 1

least_length = min(length_histogram.items(), key=lambda x: x[0])[0]
greatest_length = max(length_histogram.items(), key=lambda x: x[0])[0]
for length in range(least_length, greatest_length+1):
    count = length_histogram.get(length, 0)
    print '%3d: %3d %s' % (length, count, '*'*int(count))
print 'average: %s\n' % (total/float(count))


print 'Day-of-month distribution:'
day_histogram = {}
for account in state_db.listAccounts(state_db.session()):
    for ub in state_db.list_utilbills(state_db.session(), account)[0]:
        start_day = ub.period_start.day
        end_day = ub.period_end.day
        for day in (start_day, end_day):
            day_histogram[day] = day_histogram.get(day, 0) + 1
for day in range(1,32):
    count = day_histogram.get(day, 0)
    print '%3d: %3d %s' % (day, count, '*'*int(count))
