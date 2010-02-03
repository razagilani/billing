#!/usr/bin/python
'''
File: Registers.py
Author: Rich Andrews
Description: Register valid time logic and usage accumulation
Usage:  
'''

#
# runtime environment
#
import sys
import os  
from pprint import pprint
from types import NoneType
from datetime import date

# for xml processing
import amara
from amara import bindery
from amara import xml_print


#
# Register
#


class Register():
    """"""
    def validHours(self, theDate):
        validHours = []
        for inclusion in self.inclusions:
            print self.identifier
            print inclusion
            # if holiday, meter is on the entire day
            if ((theDate in inclusion[3])):
                print "Matched Holidays"
                return validHours.append((0, 23))

            if (theDate.isoweekday() in inclusion[2]):
                print ("Matched Weekdays")
                validHours.append((inclusion[0], inclusion[1]))

        return validHours

    def accumulate(self, energy):
        self.totalEnergy += energy
        


def go():
    '''docstring goes here?'''

    # Bind to XML bill
    dom = bindery.parse('../sample/RegTest.xml')

    registers = []
    for measuredUsage in dom.utilitybill.measuredusage: 
        for meter in measuredUsage.meter:
            for register in meter.register:
                if (register.shadow == u'true'):

                    r = Register()
                    registers.append(r)
                    r.identifier = str(register.identifier)
                    r.service = str(measuredUsage.service)
                    r.inclusions = []
                    r.exclusions = []

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

    print "----"
    theDate = date(2010, 5, 27)
    print registers[3].validHours(theDate)




     
if __name__ == "__main__":  
    go()
