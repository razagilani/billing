#!/usr/bin/python
'''
Code for accumulating Skyline-generated energy into "shadow" registers in
meters of reebills.
'''
import sys
import os  
from pprint import pprint, pformat
from types import NoneType
from datetime import date, datetime,timedelta, time
import calendar
import random
import csv
import bisect
from optparse import OptionParser
from skyliner import sky_install
from skyliner import splinter
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from billing import mongo
from billing.dictutils import dict_merge
from billing import dateutils

def find_le(a, x):
    'Find rightmost value less than or equal to x'
    i = bisect.bisect_right(a, x)
    if i:
        #return a[i-1]
        return i-1
    raise IndexError

def get_energy_for_time_interval(timestamps, values, t1, t2):
    '''Returns interval meter energy for the time interval [t1, t2) as best we
    can estimate it. We assume that for each i, the energy value at values[i]
    covers the time period between timestamps[i-1] and timestamps[i], and that
    energy is evenly distrubuted over each period. This is only accurate if t1
    and t2 are in 'timestamps', but they're not, it should be approximately
    right, especially if the time resolution is high.'''
    # binary search the list of timestamps to find the last data point
    # preceding t1 and the first one following it: call these t1_early and t1_late.
    # (if t1 exactly matches a timestamp, t1_early == t1.)
    t1_early_index = find_le(timestamps, t1)
    t1_early = timestamps[t1_early_index]
    t1_late = timestamps[t1_early_index + 1]

    # assume the energy associated with the timestamp t1_late is distributed
    # evenly over the time interval (t1_early, t1_late].
    total_energy = values[t1_early_index] * (t1_late - t1).seconds / (t1_late - t1_early).seconds
    
    # accumulate energy from data points with timestamps following t1_late up
    # to the last one before t2 (call that t2_early)
    i = t1_early_index + 2
    while timestamps[i] < t2:
        total_energy += values[i]
        i += 1
    t2_late_index = i
    t2_early_index = i - 1
    t2_late = timestamps[t2_late_index]
    t2_early = timestamps[t2_early_index]
    
    # we have counted energy from the entire interval [t2_early, t2_late)
    # above, so we need to subtract the energy in (t2, t2_late) from the total
    last_interval_length = (t2_late - t2_early).seconds
    total_energy -= values[t2_early_index] * (timestamps[t2_late_index] - t2).seconds / last_interval_length

    return total_energy

def get_interval_meter_data_source(csv_file):
    '''Returns a function mapping hours (as datetimes) to hourly energy
    measurements from an interval meter. These measurements should come as a
    CSV file with timestamps in the first column and kwh in the
    second.

    We can't compute the energy offset provided by the difference between
    two measurements when there are time-of-use registers, because it depends
    what the utility would have measured at a particular time, and we have no
    way to know that--so instead we put the full amount of energy measured by
    the interval meter into the shadow registers. This energy is not an offset,
    so we're using the shadow registers in a completely different way from how
    they were intended to be used. But the meaning of shadow registers will
    change: instead of using real and shadow registers to compute actual and
    hypothetical charges as we do for Skyline bills, we will treat them just as
    pairs of energy measurements whose meaning can change depending on how
    they're used. '''

    # read data in format [(timestamp, value)]
    timestamps = []
    values  = []
    reader = csv.reader(csv_file)
    for row in reader:
        timestamp_str, value, unit = row
        timestamp_str = datetime.datetime.strptime('format goes here', timestamp_str)
        if unit == 'therms':
            value = value
        else:
            raise Exception('unknown unit')
        timestamps.append(timestamp)
        values.append(value)

    # function that will return energy for an hour
    return lambda hour: get_energy_for_time_interval(timestamps, values, hour,
            hour + datetime.timedelta(hours=1))

def get_shadow_register_data(reebill):
    '''Returns a list of shadow registers in all meters of the given
    MongoReebill. The returned dictionaries are the same as register
    subdocuments in mongo plus read dates of their containing meters.'''
    result = []
    service_meters_dict = reebill.meters # poorly-named attribute
    for service, meters in service_meters_dict.iteritems():
        for meter in meters:
            for register in meter['registers']:
                if register['shadow'] == True:
                    result.append(dict_merge(register.copy(), {
                        'prior_read_date': meter['prior_read_date'],
                        'present_read_date': meter['present_read_date']
                    }))
    return result

def usage_data_to_virtual_register(install, reebill, splinter):
    '''Gets energy quantities from OLTP and puts them in the total fields of
    the appropriate shadow registers in the MongoReebill object reebill.
    Returns the document so it can be saved in Mongo.'''
    # get identifiers of all shadow registers in reebill from mongo
    registers = get_shadow_register_data(reebill)
    inst_obj = splinter.get_install_obj_for(install)

    # now that a list of shadow registers are initialized, accumulate energy
    # into them for the specified date range
    for register in registers:
        # service date range
        begin_date = register['prior_read_date'] # inclusive
        end_date = register['present_read_date'] # exclusive

        # get service type of this register (gas or electric)
        # TODO replace this ugly hack with something better
        # (and probably make it a method of MongoReebill)
        service_of_this_register = None
        for service in reebill.services:
            for register_dict in reebill.shadow_registers(service):
                if register_dict['identifier'] == register['identifier']:
                    service_of_this_register = service
                    break
        assert service_of_this_register is not None
        
        # reset register in case energy was previously accumulated
        register['quantity'] = 0

        for day in dateutils.date_generator(begin_date, end_date):
            # the hour ranges during which we want to accumulate energy in this
            # shadow register is the entire day for normal registers, or
            # periods given by 'active_periods_weekday/weekend/holiday' for
            # time-of-use registers
            # TODO make this a method of MongoReebill
            hour_ranges = None
            if 'active_periods_weekday' in register:
                # a tou register should have all 3 active_periods_... keys
                assert 'active_periods_weekend' in register
                assert 'active_periods_holiday' in register
                hour_ranges = map(tuple,
                        register['active_periods_' + dateutils.get_day_type(day)]) 
            else:
                hour_ranges = [(0,23)]

            energy_today = None
            for hourrange in hour_ranges:
                # 5 digits after the decimal points is an arbitrary decision
                # TODO decide what our precision actually is: see
                # https://www.pivotaltracker.com/story/show/24088787
                energy_today = inst_obj.get_billable_energy(day, hourrange, places=5)
                
                # convert units from BTU to kWh (for electric) or therms (for gas)
                if register['quantity_units'].lower() == 'kwh':
                    #energy_today /= 3412.14
                    # energy comes out in kwh
                    pass
                elif register['quantity_units'].lower() == 'therms':
                    energy_today /= 100000
                else:
                    raise Exception('unknown energy unit %s' % register['quantity_units'])

                print 'register %s accumulating energy %s %s' % (
                        register['identifier'], energy_today,
                        register['quantity_units'])
                register['quantity'] += energy_today

        # update the reebill: put the total skyline energy in the shadow register
        reebill.set_shadow_register_quantity(register['identifier'],
                register['quantity'])

    # return the updated reebill
    return reebill


# TODO: kill this function
def fetch_bill_data(server, olap_id, reebill):
    # update values of shadow registers in reebill with skyline generated energy
    reebill = usage_data_to_virtual_register(olap_id, reebill, server=server)


