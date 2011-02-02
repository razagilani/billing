#!/usr/bin/python
"""
File: Registers.py
Description: Register valid time logic and usage accumulation
Usage: See command line synopsis
"""

#
# runtime support
#
import sys
import os  
from pprint import pprint, pformat
from types import NoneType
from datetime import date, datetime,timedelta, time
import random
from optparse import OptionParser

from skyliner import xml_utils

# for xml processing
import amara
from amara import bindery
from amara import xml_print

#
from skyliner import sky_install
from skyliner import splinter
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from skyliner.xml_utils import XMLUtils

#
# Globals
#



#
# Register
#


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
    
    def __init__(self, identifier, description, total, service, priorreaddate, presentreaddate, node):
        self.__accumulatedEnergy = 0

        # name of the register -  matches meter register #
        self.identifier = identifier
        self.description = description

        # lists of the time periods that the register is either on or off
        # each list element is in the form of (from hour, to hour, day of week, holiday date)
        self.inclusions = []
        self.exclusions = []

        # utility service name
        self.service = service

        # total amount of skyline energy
        self.total = total

        # the beginning and end of the period for which this register would accumulate energy
        self.priorreaddate = priorreaddate
        self.presentreaddate = presentreaddate

        # this holds the xml node that defines this register so that the node may be updated with total accumulated energy
        # total should be empty or zero. if not, that is an exception
        self.node = node

    def __str__(self):
        return self.identifier + " " + self.service + " " + self.description + " " + self.priorreaddate + " to " + self.presentreaddate + " inclusions " + str(self.inclusions) + " exclusions " + str(self.exclusions)
    
    def validHours(self, theDate):
        """
        For a given date, return a list of tuples that describe the ranges of hours 
        this register should accumulate energy
        e.g. [(8,12), (15,19)] == 8:00:00AM to 11:59:59, and 3:00:00pm to 6:59:59
        """
        hour_tups = []
        for inclusion in self.inclusions:

            # if theDate matches a holiday listed as an inclusion, meter is on the entire day.
            # Full day in inclusion (holiday) override weekday rules
            if ((theDate in inclusion[3])):
                return [(0, 23)]

            if (theDate.isoweekday() in inclusion[2]):
                # weekday matches, make sure it is not excluded due to full day in exclusion (holiday)
                for exclusion in self.exclusions:
                    if (theDate in exclusion[3]):
                        return []
                hour_tups.append((inclusion[0], inclusion[1]))

        return hour_tups

    def accumulate(self, energy):
        """Accumulate energy in this register.  Field usage data is repeatedly accumulated for a billing period total."""
        self.__accumulatedEnergy += energy
        
    def accumulatedEnergy(self):
        """Return the amount of energy accumulated in this register."""
        return self.__accumulatedEnergy
        
    # need good service/fuel name constant through all code.  Map it for now.  Bill model uses human name, abbrevs used in the data files.
    def serviceType(self):
        """Map the human readable service names found in the bill model to fuel type abbreviations used in the data files."""
        if self.service == u'Electric':
            return 'elec'
        if self.service == u'Gas':
            return 'gas'


"""Yield dates based on from_date up to and excluding to_date.  The reason for the exclusion of to_date is that utility billing periods do not include the whole day for the end date specified for the period.  That is, the utility billing period range of 2/15 to 3/4, for example, is for the usage at 0:00 2/15 to 0:00 3/4.  0:00 3/4 is before the 3/4 begins."""
def dateGenerator(from_date, to_date):
    if (from_date > to_date):
        return
    while from_date < to_date:
        yield from_date
        from_date = from_date + timedelta(days = 1)
    return


#begin and end dates come from xml
def usageDataToVirtualRegister(install, dom, server=None, beginAccumulation=None, endAccumulation=None, verbose=False):
    """
    Deprecated in favor of the new cubes.  Bind usage data from OLTP to the registers defined in dom.  BeginAccumulation is inclusive of that days usage.  The binding ends exclusive of the day specified in endAccumulation.  That is, endAccumulation is the end of a utility billing period and is not included.  beginAccumulation m/d/y 0:00 to endAccumulation m/d/y 0:00; not endAccumulation m/d/y 12:59:99...
    """

    # For registers defined in XML bill, build a list of register instances that can accumulate energy
    registers = bindRegisters(dom, verbose)

    # TODO: parameterize guru_root
    s = splinter.Splinter(server, "tyrell")
    inst_obj = s.get_install_obj_for(install)
    
    # now that a list of shadow registers are initialized, accumulate energy into them for the specified date range
    for register in registers:
        # service date range
        # set up interval - use meter read dates from xml if command line params not available
        if (beginAccumulation == None):
            beginAccumulation = (datetime.strptime(register.priorreaddate, "%Y-%m-%d")).date()
        if (endAccumulation == None):
            endAccumulation = (datetime.strptime(register.presentreaddate, "%Y-%m-%d")).date()

        for day in dateGenerator(beginAccumulation, endAccumulation):
            #if (day < inst_obj.monitoring_began):
            #    print str(day) + " precedes monitoring"
            #    continue
            hours = []
            hours = register.validHours(day)

            energy = 0
            for hourrange in hours:
                try:
                    if (register.serviceType() == 'elec'):
                        #BTUs to kWh divide by 3412.14 kWh/therm
                        energy = inst_obj.get_energy_consumed_by_service(datetime(day.year, day.month, day.day), "elec", hourrange)
                        energy /= 3412.14
                    if (register.serviceType() == 'gas'):
                        # BTUs to therm divide by 100,000 BTU/therm
                        energy = inst_obj.get_energy_consumed_by_service(datetime(day.year, day.month, day.day), "gas", hourrange)

                        # BTU to therms
                        energy /= 100000
                        # BTU to Ccf
                        #energy /= 100000

                except DataHandlerError:
                    print "DataHandler has no energy values for " + str(day) + " " + str(hourrange)
       
                register.accumulate(energy)

            if (verbose):
                print str(day) + ", " + register.service +  ", " + str(register.identifier) + ", " + str(register.validHours(day)) + ", " + str(energy) + ", " + str(register.accumulatedEnergy())

        # update the register xml node with the total skyline energy
        # ToDo: remove the node from the register - for each register, get the identifier and xml_select and update the source xml doc vs track the node in register
        if (verbose):
            print "Current Register value " + register.service +  ", " + str(register.identifier) + ", " + str(register.node.total)
        register.node.total.xml_children[0].xml_value = str(register.accumulatedEnergy())

    if (verbose):
        for register in registers:
            print "New Register value " + register.service +  ", " + str(register.identifier) + ", " + str(register.accumulatedEnergy())

    # return the dom with the updated skyline register totals
    return dom

def bindRegisters(dom, verbose=False):
    registers = []
    # bind Register to appropriate XML grove
    # get measured usage for each utility service
    for measuredUsage in dom.bill.measuredusage:
        # for each utility service there are one or many meters
        for meter in measuredUsage.meter:
            # for each meter there are one or many registers
            for register in meter.register:
                # select only shadow registers since we are accumulating only Skyline energy
                if (register.shadow == u'true'):
                    # each register is responsible for accumulating energy according to an internal set of inclusion and exclusion rules
                    # create a register and populate it with data from the bill and add it to a list for later
                    r = Register(str(register.identifier), str(register.description), 
                        str(register.total), str(measuredUsage.service), str(meter.priorreaddate), 
                        str(meter.presentreaddate), register)
                    registers.append(r)

                    for inclusion in register.xml_select(u'ub:effective/ub:inclusions'):
                        weekdays = []
                        holidays = []
                        for weekday in inclusion.xml_select(u'ub:weekday'):
                            weekdays.append(int(str(weekday)))
                        for holiday in inclusion.xml_select(u'ub:holiday'):
                            holidays.append(date(int(str(holiday)[0:4]),int(str(holiday)[5:7]),int(str(holiday)[8:10])))
                            
                        # pain... inclusion.fromhour/tohour evaluates to none w/ str() when there are siblings with fromhours/tohours
                        # when there are no siblings, it seems that inclusion.fromhour/tohour fails with a 'no attribute' error from amara
                        # investigate this - probably a bug in amara
                        if (inclusion.fromhour != None):
                            fromhour = int(str(inclusion.fromhour)[0:2])
                        if (inclusion.tohour != None):
                            tohour = int(str(inclusion.tohour)[0:2])

                        r.inclusions.append((fromhour, tohour, weekdays, holidays))

                    for exclusion in register.xml_select('ub:effective/ub:exclusions'):
                        weekdays = []
                        holidays = []
                        for weekday in exclusion.xml_select(u'ub:weekday'):
                            weekdays.append(str(weekday))
                        for holiday in exclusion.xml_select(u'ub:holiday'):
                            holidays.append(date(int(str(holiday)[0:4]),int(str(holiday)[5:7]),int(str(holiday)[8:10])))

                        # here is the bug:  exclusion.fromhour.  Fails here, not up there.  Why?????
                        r.exclusions.append((None, None, None, holidays))
    if (verbose):
        print "bound registers " + str(map(str,registers))

    return registers

def main(options):
    """
    """

    # Bind to XML bill
    dom = bindery.parse(options.bill)

    if (options.begin != None):
        options.begin = datetime(int(options.begin[0:4]),int(options.begin[4:6]),int(options.begin[6:8]))
        
    if (options.end != None):
        options.end = datetime(int(options.end[0:4]),int(options.end[4:6]),int(options.end[6:8]))

    # ToDo: check option values for correctness
    dom = usageDataToVirtualRegister(options.install, 
                                         dom, 
                                         options.server,
                                         options.begin,
                                         options.end,
                                         options.verbose)
    return dom

if __name__ == "__main__":

    # configure optparse
    parser = OptionParser()
    parser.add_option("-B", "--bill", dest="bill", help="Bind to registers defined in bill FILE. e.g. 10001/4.xml or http://tyrell:8080/exist/rest/db/test/skyline/bills/10001/4.xml", metavar="FILE")
    parser.add_option("-o", "--olap", dest="install", help="Bind to data from olap NAME. e.g. daves ", metavar="NAME")

    # ToDo: bind to fuel type and begin period in bill 
    parser.add_option("-b", "--begin", dest="begin", default=None, help="Begin date in YYYYMMDD format.", metavar="YYYYMMDD")
    parser.add_option("-e", "--end", dest="end", default=None, help="End date in YYYYMMDD format.", metavar="YYYYMMDD")

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Print accumulation messages to stdout.")
    parser.add_option("-u", "--user", dest="user", default='prod', help="Bill database user account name.")
    parser.add_option("-p", "--password", dest="password", help="Bill database user account name.")

    parser.add_option("-s", "--server", dest="server", default='http://duino-drop.appspot.com/', help="Location of a server that OLAP class Splinter() can use.")
    parser.add_option("-r", "--readonly", action="store_true", dest="readonly", default=False, help="Do not update the bill.")


    (options, args) = parser.parse_args()

    if (options.install == None):
        print "OLAP project must be specified."
        exit()

    if (options.bill == None):
        print "bill must be specified."
        exit()

    if (options.begin == None):
        print "Depending on meter priorreaddate."
    else:
        print "Meter priorreaddate overridden."
        
    if (options.end == None):
        print "Depending on meter currentreaddate."
    else:
        print "Meter currentreaddate overridden."

    dom = main(options)
    
    xml = dom.xml_encode()

    if (options.readonly == False):
        if (options.verbose):
            print "Updating bill " + options.bill

        XMLUtils().save_xml_file(xml, options.bill, options.user, options.password)
