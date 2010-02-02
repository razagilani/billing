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


# for xml processing
import amara
from amara import bindery
from amara import xml_print


#
# Globals
#





#
# Register
#


class Register():
    """"""

    def validHours(self, date):
        pass


def go():
    '''docstring goes here?'''
    # Bind to XML bill
    dom = bindery.parse('../sample/RegTest.xml')

    for measuredUsage in dom.utilitybill.measuredusage: 
        for meter in measuredUsage.meter:
            for register in meter.register:
                if (register.shadow == u'true'):
                    r = Register()
                    #print str(register.identifier)
                    r.identifier = str(register.identifier)
                    r.service = str(measuredUsage.service)
                    r.inclusions = []
                    r.exclusions = []
                    for inclusion in register.xml_select(u'ub:effective/ub:inclusions'):
                        weekdays = []
                        monthdays = []
                        for weekday in inclusion.xml_select(u'ub:weekday'):
                            weekdays.append(str(weekday))
                        for monthday in inclusion.xml_select(u'ub:monthday'):
                            monthdays.append(str(monthday))
                        r.inclusions.append((str(inclusion.fromhour), str(inclusion.tohour) , weekdays, monthdays))
                    for exclusion in register.xml_select('ub:effective/ub:exclusions'):
                        weekdays = []
                        monthdays = []
                        for weekday in exclusion.xml_select(u'ub:weekday'):
                            weekdays.append(str(weekday))
                        for monthday in exclusion.xml_select(u'ub:monthday'):
                            monthdays.append(str(monthday))
                        r.exclusions.append((str(exclusion.fromhour), str(exclusion.tohour), weekdays, monthdays))
                    print vars(r)
                    




     
if __name__ == "__main__":  
    go()
