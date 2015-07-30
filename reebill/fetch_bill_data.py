'''
Code for accumulating Skyline-generated energy into "shadow" registers in
meters of reebills.
'''
import sys
from datetime import date, datetime,timedelta
import csv
from bisect import bisect_left

from skyliner.sky_handlers import cross_range
from util import dateutils, holidays
from util.dateutils import date_to_datetime, timedelta_in_hours
from exc import MissingDataError, RegisterError


class RenewableEnergyGetter(object):

    def __init__(self, splinter, nexus_util, logger):
        self._splinter = splinter
        self._nexus_util = nexus_util
        self._logger = logger

    def get_billable_energy_timeseries(self, install, start, end,
            measure, verbose=False, ):
        '''Returns a list of hourly billable-energy values from OLAP during the
        datetime range [start, end) (endpoints must whole hours). Values during
        unbillable annotations are removed. If 'skip_missing' is True, missing OLAP
        documents or documents without the "energy_sold" measure are treated as
        0s.'''
        unbillable_annotations = [a for a in install.get_annotations(
            force_update=True) if a.unbillable]
        monguru = self._splinter._guru
        result = []
        for hour in cross_range(start, end):
            if any([a.contains(hour) for a in unbillable_annotations]):
                result.append(0)
                if verbose:
                    print >> sys.stderr, "skipping %s's %s: unbillable" % (
                            install.name, hour)
            else:
                day = date(hour.year, hour.month, hour.day)
                hour_number = hour.hour
                try:
                    try:
                        measure_value = monguru.get_measure_value_for_hour(
                            install, day, hour_number, measure)
                    except ValueError:
                        raise MissingDataError(
                            ("Couldn't get renewable energy data "
                                "for %s: OLAP document missing at %s") % (
                            install.name, hour))
                    if measure_value is None:
                        raise MissingDataError(
                            "OLAP document for %s lacks %s measure at %s" % (
                            install.name, measure, hour))
                except MissingDataError as e:
                    print >> sys.stderr, 'WARNING: ignoring missing data: %s' % e
                    result.append(0)
                else:
                    if verbose:
                        print >> sys.stderr, "%s's OLAP %s for %s: %s" % (
                                install.name, measure, hour, measure_value)
                    result.append(measure_value)
        return result

    def update_renewable_readings(self, reebill, use_olap=True, verbose=False):
        """Update hypothetical register quantities in 'reebill' with
        renewable energy.
        :param reebill: ReeBill to update
        :param use_olap: get data from OLAP database; if False, use OLTP
        database
        :param verbose: print log messages
        """
        olap_id = self._nexus_util.olap_id(reebill.get_account())
        install_obj = self._splinter.get_install_obj_for(olap_id)
        utilbill = reebill.utilbill
        start, end = reebill.get_period()
        # get hourly "energy sold" values during this period
        for reading in reebill.readings:
            if use_olap:
                timeseries = self.get_billable_energy_timeseries(install_obj,
                    date_to_datetime(start), date_to_datetime(end), reading.measure,
                    verbose=verbose)
            else:
                # NOTE if install_obj.get_billable_energy_timeseries() uses
                # die_fast=False, this timeseries may be shorter than anticipated and
                # energy_function below will fail.
                # TODO support die_fast=False: 35547299
                timeseries = [pair[1] for pair in
                    install_obj.get_billable_energy_timeseries(
                    date_to_datetime(start), date_to_datetime(end), reading.measure)]

            quantity = self._usage_data_to_virtual_register(utilbill,
                    reading, timeseries)
            assert isinstance(quantity, (float, int))
            try:
                reebill.set_renewable_energy_reading(reading.register_binding,
                                                     quantity)
            except RegisterError:
                # ignore any registers that exist in the utility bill
                # but don't have corresponding readings in the reebill
                self._logger.info(('In update_renewable_readings: skipped '
                        'register "%s" in %s') % (reading.register_binding,
                        reebill))

    # NOTE this is used only by fetch_interval_meter_data, which is obsolete.
    def get_interval_meter_data_source(self, csv_file, timestamp_column=0,
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
            total = 0
            i = first_timestamp_index
            while timestamps[i] < last_timestamp:
                expected_timestamp = first_timestamp + timedelta(
                        hours=.25*(i - first_timestamp_index))
                if timestamps[i] != expected_timestamp:
                    raise Exception(('Bad timestamps for hour range %s %s: '
                        'expected %s, found %s') % (day, hour_range,
                            expected_timestamp, timestamps[i]))
                total += values[i]
                i+= 1
            # unfortunately the last energy value must be gotten separately.
            # TODO: add a do-while loop to python
            if timestamps[i] != last_timestamp:
                raise Exception(('Bad timestamps for hour range %s %s: '
                    'expected %s, found %s') % (day, hour_range,
                        expected_timestamp, timestamps[i]))
            total += values[i]

            return total

        return get_energy_for_hour_range


    def _usage_data_to_virtual_register(self, utilbill, reading, timeseries):
        '''Gets energy quantities from 'timeseries' and returns new
        renewable energy register readings as a list of (register binding,
        quantity) pairs. The caller should put these values in the
        appropriate place.

        'timeseries' a list of hourly values used to determine the register's
        value, such as energy consumed in each hour. (Energy is measured in
        therms.)
        '''
        aggregation_function = reading.get_aggregation_function()
        def get_renewable_energy_for_register(register, start, end):
            aggregate_value = None

            for day in dateutils.date_generator(start, end):
                active_periods = register.get_active_periods()
                if holidays.is_weekday(day):
                    hour_ranges = map(tuple,
                                      active_periods['active_periods_weekday'])
                else:
                    hour_ranges = map(tuple,
                                      active_periods['active_periods_weekend'])

                for hourrange in hour_ranges:
                    indices = []
                    for hour in range(hourrange[0], hourrange[1] + 1):
                        index = timedelta_in_hours(date_to_datetime(day) +
                            timedelta(hours=hour)
                            - date_to_datetime(start))
                        indices.append(index)

                    energy_today = aggregation_function(
                            timeseries[i] for i in indices)

                    if aggregate_value is None:
                        aggregate_value = float(energy_today)
                    else:
                        aggregate_value = aggregation_function(
                                [aggregate_value, float(energy_today)])
            return aggregate_value

        register = utilbill.get_register_by_binding(reading.register_binding)
        return get_renewable_energy_for_register(
                register, utilbill.period_start, utilbill.period_end)

