#!/usr/bin/python
"""
File: Registers.py
Description: Register valid time logic and usage accumulation
Usage: See command line synopsis
"""
import sys
import os  
from pprint import pprint, pformat
from types import NoneType
from datetime import date, datetime,timedelta, time
import random
from optparse import OptionParser

from skyliner import sky_install
from skyliner import splinter
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from billing import mongo
from billing.mongo import dict_merge # TODO move this function out of mongo.py

#class Register():
    #"""
    #Tracks the times a meter register accumulates usage data and accumulates
    #Skyline field usage data accordingly.  This class provides the SI virtual 
    #meter data and behavior.

    #This class works by tracking inclusions and exclusions of time for each register.

    #Each register has inclusions for the time it is recording energy and
    #exclusions for the time it should not record energy.

    #A good example are a set of TOU registers where the total kWh register is
    #inclusive of all time and a shoulder register is inclusive of two ranges of
    #time during weekdays, except for a holiday.  The ranges of time are
    #inclusions, the holiday an exclusion.

    #TODO: assert that all registers that do not include all time (non total
    #registers) sum up to all time for the days on which they are effective.
    #For example, the peak, shoulder, off peak registers are all off on
    #weekends.  But are all on during weekdays, typically.  Ensure that for
    #those days where they are effective, on, that all hours of the days are
    #recorded in at least one register.  In other words, there shall be no
    #discontinuities in the time intervals covered.
    #"""
    #def __init__(self, identifier, description, total, service, priorreaddate, presentreaddate):
        #self.__accumulatedEnergy = 0

        ## name of the register -  matches meter register #
        #self.identifier = identifier
        #self.description = description

        ## lists of the time periods that the register is either on or off
        ## each list element is in the form of (from hour, to hour, day of week,
        ## holiday date)
        #self.inclusions = []
        #self.exclusions = []

        ## utility service name
        #self.service = service

        ## total amount of skyline energy
        #self.total = total

        ## the beginning and end of the period for which this register would
        ## accumulate energy
        #self.priorreaddate = priorreaddate
        #self.presentreaddate = presentreaddate

    #def __str__(self):
        #return self.identifier + " " + self.service + " " + self.description \
                #+ " " + self.priorreaddate + " to " + self.presentreaddate \
                #+ "inclusions " + str(self.inclusions) + " exclusions " + \
                #str(self.exclusions)
    
    #def accumulate(self, energy):
        #"""Accumulate energy in this register.  Field usage data is repeatedly
        #accumulated for a billing period total."""
        #self.__accumulatedEnergy += energy
        
    #def accumulatedEnergy(self):
        #"""Return the amount of energy accumulated in this register."""
        #return self.__accumulatedEnergy
        
    ## need good service/fuel name constant through all code.  Map it for now.  Bill model uses human name, abbrevs used in the data files.
    #def serviceType(self):
        #"""Map the human readable service names found in the bill model to fuel
        #type abbreviations used in the data files."""
        #if self.service == u'Electric':
            #return 'elec'
        #if self.service == u'Gas':
            #return 'gas'

def dateGenerator(from_date, to_date):
    """Yield dates based on from_date up to and excluding to_date.  The reason
    for the exclusion of to_date is that utility billing periods do not include
    the whole day for the end date specified for the period.  That is, the
    utility billing period range of 2/15 to 3/4, for example, is for the usage
    at 0:00 2/15 to 0:00 3/4.  0:00 3/4 is before the 3/4 begins."""
    if (from_date > to_date):
        return
    while from_date < to_date:
        yield from_date
        from_date = from_date + timedelta(days = 1)
    return

def get_day_type(day):
    '''Returns 'weekday', 'weekend', or 'holiday' to classify the given date.'''
    # TODO add holidays
    if day.weekday() == 0 or day.weekday() == 6:
        return 'weekend'
    return 'weekday'
    
#def bindRegisters(reebill):
    #result = []
    #service_meters_dict = reebill.meters # poorly-named attribute
    #for service, meters in service_meters_dict.iteritems():
        #for meter in meters:
            #for register in meter['registers']:
                #if register['shadow'] == True:
                    #r = rate_structure.Register(register, 
                            #meter['prior_read_date'],
                            #meter['present_read_date'])
                    #result.append(r)
    #return result
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

    print '********** registers:', registers
    
    # now that a list of shadow registers are initialized, accumulate energy
    # into them for the specified date range
    for register in registers:
        print 'register:', register
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

        for day in dateGenerator(begin_date, end_date):
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
                        register['active_periods_'+get_day_type(day)])
            else:
                hour_ranges = [(0,23)]

            energy_today = None
            for hourrange in hour_ranges:
                # get energy, using this register's service type
                # (convert numpy types to float)
                try:
                    if service_of_this_register.lower() == 'electric':
                        energy_today = float(inst_obj.get_energy_consumed_by_service(
                                datetime(day.year, day.month, day.day),
                                "elec", hourrange))
                    elif service_of_this_register.lower() == 'gas':
                        energy_today = float(inst_obj.get_energy_consumed_by_service(
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

                print 'register %s accumulating energy %s %s' % \
                        (register['identifier'], energy_today, register['quantity_units'])
                register['quantity'] += energy_today

        # update the reebill: put the total skyline energy in the shadow register
        reebill.set_shadow_register_quantity(register['identifier'], register['quantity'])

    # return the updated reebill
    return reebill

# TODO: kill this function
def fetch_bill_data(server, olap_id, reebill):
    
    # update values of shadow registers in reebill with skyline generated energy
    reebill = usage_data_to_virtual_register(olap_id, reebill, server=server)

