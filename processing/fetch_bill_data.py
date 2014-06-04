#!/usr/bin/python
'''
Code for accumulating Skyline-generated energy into "shadow" registers in
meters of reebills.
'''
import sys
from datetime import date, datetime,timedelta
import csv
from bisect import bisect_left
import skyliner
from skyliner.sky_handlers import cross_range
from billing.processing import mongo
from billing.util import dateutils, holidays
from billing.util.dateutils import date_to_datetime, timedelta_in_hours
from billing.processing.exceptions import MissingDataError, RegisterError


class RenewableEnergyGetter(object):

    def __init__(self, splinter, reebill_dao, logger):
        self._splinter = splinter
        self._reebill_dao = reebill_dao
        self._logger = logger

    def get_billable_energy_timeseries(self, install, start, end,
            measure, ignore_missing=True, verbose=False, ):
        '''Returns a list of hourly billable-energy values from OLAP during the
        datetime range [start, end) (endpoints must whole hours). Values during
        unbillable annotations are removed. If 'skip_missing' is True, missing OLAP
        documents or documents without the "energy_sold" measure are treated as
        0s.'''
        unbillable_annotations = [a for a in install.get_annotations() if
                a.unbillable]
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
                        cube_doc = monguru.get_data_for_hour(install, day, hour_number)
                    except ValueError:
                        raise MissingDataError(("Couldn't get renewable energy data "
                                "for %s: OLAP document missing at %s") % (
                                install.name, hour))
                    try:
                        attr_name = measure.lower().replace(' ', '_')
                        data = getattr(cube_doc, attr_name)
                        # NOTE CubeDocument returns None if the measure doesn't
                        # exist, but this should be changed:
                        # https://www.pivotaltracker.com/story/show/35857625
                        if data == None:
                            raise AttributeError('%s' %measure)
                    except AttributeError:
                        raise MissingDataError(("Couldn't get %s "
                            "data for %s: OLAP document lacks energy_sold "
                            "measure at %s") % (measure, install.name, hour))
                except MissingDataError as e:
                    if ignore_missing:
                        print >> sys.stderr, 'WARNING: ignoring missing data: %s' % e
                        result.append(0)
                    else:
                        raise
                else:
                    if verbose:
                        print >> sys.stderr, "%s's OLAP %s for %s: %s" % (
                                install.name, measure, hour, data)
                    result.append(data)
        return result

    def update_renewable_readings(self, olap_id, reebill, use_olap=True,
                verbose=False):
        '''Update hypothetical register quantities in 'reebill' with
        Skyline-generated energy. The OLAP database is the default source of
        energy-sold values; use use_olap=False to get them directly from OLTP.
        '''
        install_obj = self._splinter.get_install_obj_for(olap_id)
        reebill_doc = self._reebill_dao.load_reebill(reebill.customer.account,
                                                     reebill.sequence, reebill.version)
        utilbill = reebill.utilbill
        start, end = utilbill.period_start, utilbill.period_end

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

            # this function takes an hour and returns energy sold during that hour
            def energy_function(day, hourrange):
                total = 0
                for hour in range(hourrange[0], hourrange[1] + 1):
                    index = timedelta_in_hours(date_to_datetime(day) +
                        timedelta(hours=hour)
                        - date_to_datetime(start))
                    total += timeseries[index]
                return total

            results = self._usage_data_to_virtual_register(reebill_doc,
                utilbill, energy_function)

            for binding, quantity in results:
                assert isinstance(binding, basestring)
                assert isinstance(quantity, (float, int))
                try:
                    reebill.set_renewable_energy_reading(binding, quantity)
                except RegisterError:
                    # ignore any registers that exist in the utility bill
                    # but don't have corresponding readings in the reebill
                    self._logger.info(('In update_renewable_readings: skipped '
                            'register "%s" in %s') % (binding, reebill))

    def fetch_interval_meter_data(self, reebill, csv_file,
            meter_identifier=None, timestamp_column=0, energy_column=1,
            energy_unit='btu', timestamp_format=dateutils.ISO_8601_DATETIME):
        '''Update hypothetical quantities of registers in reebill with
        interval-meter energy values from csv_file. If meter_identifier is given,
        energy will only go in shadow registers of meters with that identifier.
        '''
        energy_function = self.get_interval_meter_data_source(csv_file,
                timestamp_column=timestamp_column, energy_column=energy_column,
                timestamp_format=timestamp_format, energy_unit=energy_unit)
        reebill_doc = self._reebill_dao.load_reebill(reebill.customer.account,
                reebill.sequence, reebill.version)
        utilbill_doc = self._reebill_dao.load_doc_for_utilbill(
                reebill.utilbills[0])

        results = self._usage_data_to_virtual_register(reebill_doc,
                utilbill_doc, energy_function)
        for binding, quantity in results:
            reebill.set_renewable_energy_reading(binding, quantity)

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


    def aggregate_total(self, energy_function, start, end, verbose=False):
        '''Returns all energy given by 'energy_function' in the date range [start,
        end), in BTU. 'energy_function' should be a function mapping a date and an
        hour range (2-tuple of integers in [0,23]) to a float representing energy
        used during that time in BTU.'''
        result = 0
        for day in dateutils.date_generator(start, end):
            print 'getting energy for %s' % day
            result += energy_function(day, (0, 23))
        return result

    def aggregate_tou(self, day_type, hour_range, energy_function, start, end,
                      verbose=False):
        '''Returns the sum of energy given by 'energy_function' during the hours
        'hour_range' (a 2-tuple of integers in [0,24)) on days of type 'day_type'
        ("weekday", "weekend", or "holiday"). 'energy_function' should be a
        function mapping a date and an hour range (2-tuple of integers in [0,23])
        to a float representing energy used during that time in BTU.'''
        result = 0
        for day in dateutils.date_generator(start, end):
            if holidays.get_day_type(day) != day_type:
                print 'getting energy for %s %s' % (day, hour_range)
                result += energy_function(day, hour_range)
        return result

    # def _usage_data_to_virtual_register(reebill, energy_function,
    #         verbose=False):
    #     '''Gets energy quantities from 'energy_function' and puts them in the
    #     "quantity" fields of the register subdocuments in the 'MongoReebill' object
    #     'reebill'.
    #
    #     'energy_function' should be a function mapping a date and an hour
    #     range (pair of integers in [0,23]) to a float representing energy used
    #     during that time. (Energy is measured in therms, even if it's gas.)
    #
    #     If meter_identifier is given, accumulate energy only into the shadow
    #     registers of meters with that identifier.
    #     '''
    #     # NOTE multiple services not supported
    #     assert len(reebill.services) == 1
    #     service = reebill.services[0]
    #     registers = reebill.shadow_registers(service)
    #     prior_read_date, present_read_date = reebill.meter_read_dates_for_service(
    #             service)
    #     # accumulate energy into the shadow registers for the specified date range
    #     for register in registers:
    #         # TODO 28304031 : register wants a float
    #         total_energy = 0.0
    #
    #         for day in dateutils.date_generator(prior_read_date, present_read_date):
    #             # the hour ranges during which we want to accumulate energy in this
    #             # shadow register is the entire day for normal registers, or
    #             # periods given by 'active_periods_weekday/weekend/holiday' for
    #             # time-of-use registers
    #             # TODO make this a method of MongoReebill
    #             hour_ranges = None
    #             if 'active_periods_weekday' in register:
    #                 # a tou register should have all 3 active_periods_... keys
    #                 assert 'active_periods_weekend' in register
    #                 assert 'active_periods_holiday' in register
    #                 hour_ranges = map(tuple,
    #                         register['active_periods_' + holidays.get_day_type(day)])
    #             elif register.get('type') == 'total':
    #                 # For non-TOU registers, only insert renewable energy if the
    #                 # register dictionary has the key "type" and its value is
    #                 # "total". Every non-TOU utility bill should have exactly one
    #                 # such register (and every TOU bill should have at most one).
    #                 # If they don't, renewable energy will be double-counted and
    #                 # the bill will be wrong. # For explanation see
    #                 # https://www.pivotaltracker.com/story/show/46469597
    #                 hour_ranges = [(0,23)]
    #             else:
    #                 if 'type' in register:
    #                     print 'register %s skipped because its "type" is "%s"' % (register['identifier'], register['type'])
    #                 else:
    #                     print 'register %s skipped because its "type" key is missing' % (register['identifier'],)
    #                 continue
    #
    #             energy_today = None
    #             for hourrange in hour_ranges:
    #                 # 5 digits after the decimal points is an arbitrary decision
    #                 # TODO decide what our precision actually is: see
    #                 # https://www.pivotaltracker.com/story/show/24088787
    #                 energy_today = energy_function(day, hourrange)
    #                 if verbose:
    #                     print 'register %s accumulating energy %s %s for %s %s' % (
    #                             register['identifier'], energy_today,
    #                             register['quantity_units'],
    #                             day, hourrange)
    #                 total_energy += float(energy_today)
    #
    #         # update the reebill: put the total skyline energy in the shadow register
    #         reebill.set_hypothetical(register['identifier'], total_energy)


    def _usage_data_to_virtual_register(self, reebill_doc,
            utilbill, energy_function, verbose=False):
        '''Gets energy quantities from 'energy_function' and returns new
        renewable energy register readings as a list of (register binding,
        quantity) pairs. The caller should put these values in the
        appropriate place.

        'energy_function' should be a function mapping a date and an hour
        range (pair of integers in [0,23]) to a float representing energy used
        during that time. (Energy is measured in therms, even if it's gas.)
        '''
        # TODO move this helper function somewhere else, e.g. utility bill
        # document class
        def get_renewable_energy_for_register(register, start, end):
            total_energy = 0.0

            for day in dateutils.date_generator(start, end):
                # the hour ranges during which we want to accumulate energy in this
                # shadow register is the entire day for normal registers, or
                # periods given by 'active_periods_weekday/weekend/holiday' for
                # time-of-use registers
                # TODO make this a method of MongoReebill
                hour_ranges = None
                if register.active_periods not in [None, []]:
                    # a tou register should have all 3 active_periods_... keys
                    for k in ['active_periods_weekday',
                              'active_periods_weekend',
                              'active_periods_holiday']:
                        assert k in register.active_periods
                    hour_ranges = map(tuple,
                        register.active_periods['active_periods_%s' %\
                                                holidays.get_day_type(day)])
                elif register.reg_type == 'total':
                    # For non-TOU registers, only insert renewable energy if the
                    # register dictionary has the key "type" and its value is
                    # "total". Every non-TOU utility bill should have exactly one
                    # such register (and every TOU bill should have at most one).
                    # If they don't, renewable energy will be double-counted and
                    # the bill will be wrong. # For explanation see
                    # https://www.pivotaltracker.com/story/show/46469597
                    hour_ranges = [(0,23)]
                else:
                    if 'type' in register:
                        print 'register %s skipped because its "type" is "%s"' % (register['identifier'], register['type'])
                    else:
                        print 'register %s skipped because its "type" key is missing' % (register['identifier'],)
                    continue

                energy_today = None
                for hourrange in hour_ranges:
                    # 5 digits after the decimal points is an arbitrary decision
                    # TODO decide what our precision actually is: see
                    # https://www.pivotaltracker.com/story/show/24088787
                    energy_today = energy_function(day, hourrange)
                    if verbose:
                        print 'register %s accumulating energy %s %s for %s %s' % (
                            register['identifier'], energy_today,
                            register['quantity_units'],
                            day, hourrange)
                    total_energy += float(energy_today)
            return total_energy

        result = []
        for register in utilbill.registers:
            hypothetical_quantity = get_renewable_energy_for_register(register,
                utilbill.period_start, utilbill.period_end)
            result.append((register.register_binding, hypothetical_quantity))

        return result
