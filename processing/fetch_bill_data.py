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
from optparse import OptionParser
from skyliner import sky_install
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from billing import mongo
from billing.dictutils import dict_merge
from billing import dateutils, holidays
from decimal import Decimal

def fetch_oltp_data(splinter, olap_id, reebill):
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


def get_shadow_register_data(reebill, meter_identifier=None):
    # TODO duplicate of mongo.shadow_registers? move this to mongo.py to
    # replace that function
    '''Returns a list of shadow registers in all meters of the given
    MongoReebill, or if meter_identifier is given, only meters with that
    identifier. The returned dictionaries are the same as register subdocuments
    in mongo plus read dates of their containing meters.'''
    result = []
    service_meters_dict = reebill.meters # poorly-named attribute
    for service, meters in service_meters_dict.iteritems():
        for meter in meters:
            if meter_identifier == None or meter['identifier'] == meter_identifier:
                for register in meter['registers']:
                    if register['shadow'] == True:
                        result.append(dict_merge(register.copy(), {
                            'prior_read_date': meter['prior_read_date'],
                            'present_read_date': meter['present_read_date']
                        }))
    return result


def usage_data_to_virtual_register(reebill, energy_function,
        meter_identifier=None):
    '''Gets energy quantities from 'energy_function' and puts them in the total
    fields of the appropriate shadow registers in the MongoReebill object
    reebill. 'energy_function' should be a function mapping a date and an hour
    range (2-tuple of integers in [0,23]) to a Decimal representing energy used
    during that time. (Energy is measured in therms, even if it's gas.) If
    meter_identifier is given, accumulate energy only into the shadow registers
    of meters with that identifier.'''
    # get all shadow registers in reebill from mongo
    registers = get_shadow_register_data(reebill, meter_identifier)
    
    if registers == []:
        raise Exception(('Meter "%s" doesn\'t exist or contains no shadow'
            ' registers') % meter_identifier)

    # accumulate energy into the shadow registers for the specified date range
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
        # TODO 28245047: use set_shadow_register_quantity function in reebill
        register['quantity'] = 0.0

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
                        register['active_periods_' + holidays.get_day_type(day)]) 
            else:
                hour_ranges = [(0,23)]

            energy_today = None
            for hourrange in hour_ranges:
                print >> sys.stderr, day, hourrange
                # 5 digits after the decimal points is an arbitrary decision
                # TODO decide what our precision actually is: see
                # https://www.pivotaltracker.com/story/show/24088787
                energy_today = energy_function(day, hourrange)
                
                # convert units from BTU to kWh (for electric) or therms (for gas)
                # TODO 28245047: use set_shadow_register_quantity function in reebill

                if register['quantity_units'].lower() == 'kwh':
                    energy_today /= Decimal('3412.14')
                elif register['quantity_units'].lower() == 'therms':
                    energy_today /= Decimal('100000.0')
                elif register['quantity_units'].lower() == 'ccf':
                    # TODO 28247371: this is an unfair conversion
                    energy_today /= Decimal('100000.0')
                else:
                    raise Exception('unknown energy unit %s' %
                            register['quantity_units'])

                print 'register %s accumulating energy %s %s' % (
                        register['identifier'], energy_today,
                        register['quantity_units'])
                # TODO 28304031 : register wants a float
                register['quantity'] += float(energy_today)

        # update the reebill: put the total skyline energy in the shadow register
        reebill.set_shadow_register_quantity(register['identifier'],
                register['quantity'])


