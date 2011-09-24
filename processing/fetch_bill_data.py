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

## for xml processing
#import amara
#from amara import bindery
#from amara import xml_print

from skyliner import sky_install
from skyliner import splinter
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
#from billing import xml_utils
#from billing.xml_utils import XMLUtils
from billing import mongo
from scripts.nexus import nexus
from billing.processing import rate_structure

class Register():
    """
    Tracks the times a meter register accumulates usage data and accumulates
    Skyline field usage data accordingly.  This class provides the SI virtual 
    meter data and behavior.

    This class works by tracking inclusions and exclusions of time for each register.

    Each register has inclusions for the time it is recording energy and exclusions for the time it should not record energy.

    A good example are a set of TOU registers where the total kWh register is inclusive of all time and a shoulder register
    is inclusive of two ranges of time during weekdays, except for a holiday.  The ranges of time are inclusions, the holiday
    an exclusion.

    TODO: assert that all registers that do not include all time (non total registers) sum up to all time for the days on which 
    they are effective.  For example, the peak, shoulder, off peak registers are all off on weekends.  But are all on during
    weekdays, typically.  Ensure that for those days where they are effective, on, that all hours of the days are recorded in at
    least one register.  In other words, there shall be no discontinuities in the time intervals covered.
    """
    def __init__(self, identifier, description, total, service, priorreaddate, presentreaddate):
        self.__accumulatedEnergy = 0

        # name of the register -  matches meter register #
        self.identifier = identifier
        self.description = description

        # lists of the time periods that the register is either on or off
        # each list element is in the form of (from hour, to hour, day of week,
        # holiday date)
        self.inclusions = []
        self.exclusions = []

        # utility service name
        self.service = service

        # total amount of skyline energy
        self.total = total

        # the beginning and end of the period for which this register would
        # accumulate energy
        self.priorreaddate = priorreaddate
        self.presentreaddate = presentreaddate

    def __str__(self):
        return self.identifier + " " + self.service + " " + self.description \
                + " " + self.priorreaddate + " to " + self.presentreaddate \
                + "inclusions " + str(self.inclusions) + " exclusions " + \
                str(self.exclusions)
    
    def accumulate(self, energy):
        """Accumulate energy in this register.  Field usage data is repeatedly
        accumulated for a billing period total."""
        self.__accumulatedEnergy += energy
        
    def accumulatedEnergy(self):
        """Return the amount of energy accumulated in this register."""
        return self.__accumulatedEnergy
        
    # need good service/fuel name constant through all code.  Map it for now.  Bill model uses human name, abbrevs used in the data files.
    def serviceType(self):
        """Map the human readable service names found in the bill model to fuel
        type abbreviations used in the data files."""
        if self.service == u'Electric':
            return 'elec'
        if self.service == u'Gas':
            return 'gas'


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

def bindRegisters(reebill, verbose=False):
    result = []
    service_meters_dict = reebill.meters # poorly-named attribute
    for service, meters in service_meters_dict.iteritems():
        for meter in meters:
            for register in meter['registers']:
                if register['shadow'] == True:
                    r = rate_structure.Register(register, 
                            meter['prior_read_date'],
                            meter['present_read_date'])
                    result.append(r)
    return result

def usageDataToVirtualRegister(install, reebill, server=None,
        beginAccumulation=None, endAccumulation=None, verbose=False):
    # TODO rename to 'usage_data_to_shadow_register'?
    '''Gets energy quantities from OLTP and puts them in the total fields of
    the appropriate shadow registers in the MongoReebill object reebill.
    Returns the document so it can be saved in Mongo. 'beginAccumulation' is
    the beginning of the period for which energy consumption data is
    accumulated (inclusive), and 'endAccumulation' is the end (exclusive).
    (Times are 0:00 to 0:00, not 0:00 to 23:59:59)'''
    # get registers from mongo document (instead of xml)
    registers = bindRegisters(reebill, verbose)

    s = splinter.Splinter(server, "tyrell", "dev")
    inst_obj = s.get_install_obj_for(install)
    
    # now that a list of shadow registers are initialized, accumulate energy into them for the specified date range
    for register in registers:
        print 'register:', register
        # service date range
        # set up interval - use meter read dates from xml if command line params not available
        if (beginAccumulation == None):
            #beginAccumulation = (datetime.strptime(register.prior_read_date, "%Y-%m-%d")).date()
            beginAccumulation = register.prior_read_date
        if (endAccumulation == None):
            #endAccumulation = (datetime.strptime(register.present_read_date, "%Y-%m-%d")).date()
            endAccumulation = register.present_read_date

        # get service type of this register (gas or electric)
        # TODO replace this ugly hack with something better
        service_of_this_register = None
        for service in reebill.services:
            for register_dict in reebill.shadow_registers(service):
                if register_dict['identifier'] == register.identifier:
                    service_of_this_register = service
                    break
        assert service_of_this_register is not None
        
        for day in dateGenerator(beginAccumulation, endAccumulation):
            energy = None
            for hourrange in register.valid_hours(day):
                # get energy, using this register's service type
                try:
                    if service_of_this_register.lower() == 'electric':
                        energy = inst_obj.get_energy_consumed_by_service(
                                datetime(day.year, day.month, day.day), "elec", hourrange)
                    elif service_of_this_register.lower() == 'gas':
                        energy = inst_obj.get_energy_consumed_by_service(
                                datetime(day.year, day.month, day.day), "gas", hourrange)
                    else:
                        raise Exception('register has unknown service type: %s' \
                                % service_of_this_register)
                except DataHandlerError:
                    print "DataHandler has no energy values for " + str(day) + " " + str(hourrange)
                    energy = 0
                
                # convert units from BTU to kWh (for electric) or therms (for gas)
                if register.quantity_units.lower() == 'kWh':
                    energy /= 3412.14
                elif register.quantity_units.lower() == 'therms':
                    energy /= 100000
                else:
                    raise Exception('unknown energy unit')

                print 'register %s accumulating energy %s %s' % (register.identifier, energy, register.quantity_units)
                register.quantity += energy

        # update the reebill: put the total skyline energy in the shadow register
        reebill.set_shadow_register_quantity(register.identifier, register.quantity)

    # return the updated reebill
    return reebill


def fetch_bill_data(server, user, password, account, sequence, period_begin, period_end, verbose, config):
    # load reebill from mongo
    dao =  mongo.ReebillDAO(config)
    reebill = dao.load_reebill(account, sequence)

    if (period_begin != None):
        period_begin = datetime(int(period_begin[0:4]), int(period_begin[4:6]),
                int(period_begin[6:8]))
    if (period_end != None):
        period_end = datetime(int(period_end[0:4]),int(period_end[4:6]),
                int(period_end[6:8]))

    # get OLAP id from account number
    olap_id = nexus.NexusQuery().mongo_find({'billing':account})[0]['olap']
    # update values of shadow registers in reebill with skyline generated energy
    reebill = usageDataToVirtualRegister(olap_id, 
                                         reebill,
                                         server=server,
                                         beginAccumulation=period_begin,
                                         endAccumulation=period_end,
                                         verbose=verbose)
    # save reebill in mongo
    dao.save_reebill(reebill)

    # formerly returning dom; this will cause errors until caller is fixed
    return reebill

if __name__ == "__main__":
    '''Command-line interface.'''
    # configure optparse
    parser = OptionParser()
    #parser.add_option("-B", "--bill", dest="bill",
            #help=("Bind to registers defined in bill FILE. e.g. 10001/4.xml or"
            #"http://tyrell:8080/exist/rest/db/test/skyline/bills/10001/4.xml"),
            #metavar="FILE")
    #parser.add_option("-o", "--olap", dest="install",
            #help="Bind to data from olap NAME. e.g. daves",
            #metavar="NAME")
    parser.add_option('-a', '--account', dest='account',
            help=('Account number for identifying the reebill in which usage'
            'data will be bound to shadow registers.'))
    parser.add_option('-q', '--sequence', dest='sequence',
            help=('Sequence number for identifying the reebill in which usage'
            'data will be bound to shadow registers.'))
    # ToDo: bind to fuel type and begin period in bill 
    parser.add_option("-b", "--begin", dest="begin", default=None,
            help="Begin date in YYYYMMDD format.", metavar="YYYYMMDD")
    parser.add_option("-e", "--end", dest="end", default=None,
            help="End date in YYYYMMDD format.", metavar="YYYYMMDD")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
            default=False, help="Print accumulation messages to stdout.")
    parser.add_option("-u", "--user", dest="user", default='prod',
            help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password",
            help="Bill database user account name.")
    parser.add_option("-s", "--server", dest="server",
            default='http://duino-drop.appspot.com/',
            help="Location of a server that OLAP class Splinter() can use.")
    parser.add_option("-r", "--readonly", action="store_true", dest="readonly",
            default=False, help="Do not update the bill.")
    options, args = parser.parse_args()

    if options.account is None:
        print "account must be specified."
        exit()
    if options.sequence is None:
        print "sequence must be specified."
        exit()
    if options.begin is None:
        print "Depending on meter priorreaddate."
    else:
        print "Meter priorreaddate overridden."
    if options.end is None:
        print "Depending on meter currentreaddate."
    else:
        print "Meter currentreaddate overridden."

    fetch_bill_data(options.server,
            options.user,
            options.password,
            options.account,
            options.sequence,
            options.begin,
            options.end,
            options.verbose,
            # TODO use real config info instead of debug_config
            mongo.debug_config)
    
