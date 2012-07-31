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
from bisect import bisect_left
import operator
from optparse import OptionParser
from skyliner import sky_install
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from billing import mongo
from billing.dictutils import dict_merge
from billing import dateutils, holidays
from decimal import Decimal

def fetch_oltp_data(splinter, olap_id, reebill, verbose=False):
    '''Update quantities of shadow registers in reebill with Skyline-generated
    energy from OLTP.'''
    inst_obj = splinter.get_install_obj_for(olap_id)
    energy_function = lambda day, hourrange: inst_obj.get_billable_energy(day,
            hourrange, places=5)
    usage_data_to_virtual_register(reebill, energy_function)

def fetch_interval_meter_data(reebill, csv_file, meter_identifier=None,
        timestamp_column=0, energy_column=1, energy_unit='btu',
        timestamp_format=dateutils.ISO_8601_DATETIME):
    '''Update quantities of shadow registers in reebill with interval-meter
    energy values from csv_file. If meter_identifier is given, energy will only
    go in shadow registers of meters with that identifier'''
    energy_function = get_interval_meter_data_source(csv_file,
            timestamp_column=timestamp_column, energy_column=energy_column,
            timestamp_format=timestamp_format, energy_unit=energy_unit)
    usage_data_to_virtual_register(reebill, energy_function,
            meter_identifier=meter_identifier)

def get_interval_meter_data_source(csv_file, timestamp_column=0,
        energy_column=1, timestamp_format=dateutils.ISO_8601_DATETIME,
        energy_unit='btu'):
    '''Returns a function mapping hours (as datetimes) to hourly energy
    measurements (in BTU) from an interval meter. These measurements should
    come as a CSV file with timestamps in timestamp_format in
    'timestamp_column' and energy measured in 'energy_unit' in 'energy_column'
    (0-indexed). E.g:

            2012-01-01T03:45:00Z, 1.234

    Timestamps must be at :00, :15, :30, :45, and the energy value associated
    with each timestamp is assumed to cover the quarter hour preceding that
    timestamp.

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

    # auto-detect csv format variation by reading the file, then reset file
    # pointer to beginning
    try:
        csv_dialect = csv.Sniffer().sniff(csv_file.read(1024))
    except:
        raise Exception('CSV file is malformed: could not detect the delimiter')
    csv_file.seek(0)

    reader = csv.reader(csv_file, dialect=csv_dialect)
    header_row_count = 0
    for row in reader:
        # make sure data are present in the relevant columns
        try:
            timestamp_str, value = row[timestamp_column], row[energy_column]
        except ValueError:
            raise Exception('CSV file is malformed: row does not contain 2 columns')

        # check timestamp: skip initial rows with invalid timestamps in the
        # timestamp column (they're probably header rows), but all timestamps
        # after the first valid timestamp must also be valid.
        try:
            timestamp = datetime.strptime(timestamp_str, timestamp_format)
        except ValueError:
            if timestamps == [] and header_row_count < 1:
                header_row_count += 1
                continue
            raise

        # convert energy_unit if necessary. (input is in energy_unit but output
        # must be in therms)
        # TODO add more units...
        if energy_unit.lower() == 'btu':
            value = float(value)
        elif energy_unit.lower() == 'therms':
            value = float(value) / 100000.
        elif energy_unit.lower() == 'kwh':
            value = float(value) / 3412.14163
        else:
            raise ValueError('Unknown energy unit: ' + energy_unit)

        timestamps.append(timestamp)
        values.append(value)

    if len(timestamps) < 4:
        raise Exception(('CSV file has only %s rows, but needs at least 4 '
                % (len(timestamps))))

    # function that will return energy for an hour range ((start, end) pair,
    # inclusive)
    def get_energy_for_hour_range(day, hour_range):
        # first timestamp is at [start hour]:15; last is at [end hour + 1]:00
        first_timestamp = datetime(day.year, day.month, day.day, hour_range[0], 15)
        last_timestamp = datetime(day.year, day.month, day.day, hour_range[1]) \
                + timedelta(hours=1)

        # validate hour range
        if first_timestamp < timestamps[0]:
            raise IndexError(('First timestamp for %s %s is %s, which precedes'
                ' earliest timestamp in CSV file: %s') % (day, hour_range,
                first_timestamp, timestamps[0]))
        elif last_timestamp > timestamps[-1]:
            raise IndexError(('Last timestamp for %s %s is %s, which follows'
                ' latest timestamp in CSV file: %s') % (day, hour_range,
                last_timestamp, timestamps[-1]))
        
        # binary search the timestamps list to find the first one >=
        # first_timestamp
        first_timestamp_index = bisect_left(timestamps, first_timestamp)

        # iterate over the hour range, adding up energy at 15-mintute intervals
        # and also checking timestamps
        total = Decimal(0)
        i = first_timestamp_index
        while timestamps[i] < last_timestamp:
            expected_timestamp = first_timestamp + timedelta(
                    hours=.25*(i - first_timestamp_index))
            if timestamps[i] != expected_timestamp:
                raise Exception(('Bad timestamps for hour range %s %s: '
                    'expected %s, found %s') % (day, hour_range,
                        expected_timestamp, timestamps[i]))
            total += Decimal(values[i])
            i+= 1
        # unfortunately the last energy value must be gotten separately.
        # TODO: add a do-while loop to python
        if timestamps[i] != last_timestamp:
            raise Exception(('Bad timestamps for hour range %s %s: '
                'expected %s, found %s') % (day, hour_range,
                    expected_timestamp, timestamps[i]))
        total += Decimal(values[i])

        return total

    return get_energy_for_hour_range


#def get_shadow_register_data(reebill, meter_identifier=None):
    ## TODO duplicate of mongo.shadow_registers? move this to mongo.py to
    ## replace that function
    #'''Returns a list of shadow registers in all meters of the given
    #MongoReebill, or if meter_identifier is given, only meters with that
    #identifier. The returned dictionaries are the same as register subdocuments
    #in mongo plus read dates of their containing meters.'''
    #result = []
    #service_meters_dict = reebill.meters # poorly-named attribute
    #for service, meters in service_meters_dict.iteritems():
        #for meter in meters:
            #if meter_identifier == None or meter['identifier'] == meter_identifier:
                #for register in meter['registers']:
                    #if register['shadow'] == True:
                        #result.append(dict_merge(register.copy(), {
                            #'prior_read_date': meter['prior_read_date'],
                            #'present_read_date': meter['present_read_date']
                        #}))
    #return result


def aggregate_total(energy_function, start, end, verbose=False):
    '''Returns all energy given by 'energy_function' in the date range [start,
    end), in BTU. 'energy_function' should be a function mapping a date and an
    hour range (2-tuple of integers in [0,23]) to a Decimal representing energy
    used during that time in BTU.'''
    result = Decimal(0)
    for day in dateutils.date_generator(start, end):
        print 'getting energy for %s' % day
        result += energy_function(day, (0, 23))
    return result

def aggregate_tou(day_type, hour_range, energy_function, start, end, verbose=False):
    '''Returns the sum of energy given by 'energy_function' during the hours
    'hour_range' (a 2-tuple of integers in [0,24)) on days of type 'day_type'
    ("weekday", "weekend", or "holiday"). 'energy_function' should be a
    function mapping a date and an hour range (2-tuple of integers in [0,23])
    to a Decimal representing energy used during that time in BTU.'''
    result = Decimal(0)
    for day in dateutils.date_generator(start, end):
        if holidays.get_day_type(day) != day_type:
            print 'getting energy for %s %s' % (day, hour_range)
            result += energy_function(day, hour_range)
    return result

def usage_data_to_virtual_register(reebill, energy_function,
        meter_identifier=None, verbose=False):
    '''Gets energy quantities from 'energy_function' and puts them in the
    quantity fields of the appropriate shadow registers in the MongoReebill
    'reebill'.  If meter_identifier is given, only puts energy in the registers
    of meters with the given identifier.'''
    # NOTE we have no way to determine what service we are offsetting (i.e. of
    # choosing a particular utility bill such that we put renewable energy only
    # in a shadow register corresponding to a register of that utility bill).
    # but we need a service to determine the meter whose read dates we're
    # using, which determine the date range for REE data. so just pick any
    # service.
    service = reebill.services[0]

    registers  = [r for r in reebill.shadow_registers(service) if
            meter_identifier is None or r['identifier'] == meter_identifier]

    if registers == []:
        raise Exception(('Meter "%s" doesn\'t exist or contains no shadow'
            ' registers') % meter_identifier)

    for register in registers:
        # using the service, go find the utility bill for that service, then
        # the shadow register in the reebill that corresponds to a register in
        # one of that utility bill's meters (there should be only one), then
        # get the dates of that meter.
        start, end = reebill.meter_read_dates_for_service(service)

        if 'active_periods_weekday' in register:
            # this is a TOU register: gets energy during certain parts of the
            # day, and those parts depend on what kind of day it is
            total_energy = Decimal(0)
            for day_type in ['weekday', 'weekend', 'holiday']:
                for hour_range in map(tuple, register['active_periods_' +
                        day_type]):
                    total_energy += aggregate_tou(day_type, hour_range,
                            energy_function, start, end, verbose=verbose)
            reebill.set_shadow_register_quantity(register['identifier'],
                    total_energy)
        else:
            reebill.set_shadow_register_quantity(register['identifier'],
                    aggregate_total(energy_function, start, end,
                    verbose=verbose))

