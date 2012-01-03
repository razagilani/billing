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
from optparse import OptionParser
from skyliner import sky_install
from skyliner import splinter
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from billing import mongo
from billing.dictutils import dict_merge
from billing import dateutils

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

def usage_data_to_virtual_register(install, reebill, server=None):
    '''Gets energy quantities from OLTP and puts them in the total fields of
    the appropriate shadow registers in the MongoReebill object reebill.
    Returns the document so it can be saved in Mongo.'''
    # get identifiers of all shadow registers in reebill from mongo
    registers = get_shadow_register_data(reebill)

    s = splinter.Splinter(server, "tyrell", "dev")
    inst_obj = s.get_install_obj_for(install)

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
                # get energy, using this register's service type
                # (convert numpy types to float)
                try:
                    if service_of_this_register.lower() == 'electric':
                        energy_today = float(inst_obj.\
                                get_energy_consumed_by_service(
                                datetime(day.year, day.month, day.day),
                                "elec", hourrange))
                    elif service_of_this_register.lower() == 'gas':
                        energy_today = float(inst_obj.\
                                get_energy_consumed_by_service(
                                datetime(day.year, day.month, day.day),
                                "gas", hourrange))
                    else:
                        raise Exception('register has unknown service type: %s' \
                                % service_of_this_register)
                except DataHandlerError:
                    print "DataHandler has no energy values for %s %s" \
                            % (day, hourrange)
                    energy_today = 0
                
                # convert units from BTU to kWh (for electric) or therms (for gas)
                if register['quantity_units'].lower() == 'kwh':
                    energy_today /= 3412.14
                elif register['quantity_units'].lower() == 'therms':
                    energy_today /= 100000
                else:
                    raise Exception('unknown energy unit')

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


