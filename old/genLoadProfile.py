#!/usr/bin/python
"""
File: Registers.py
Author: Rich Andrews
Description: Register valid time logic and usage accumulation
Usage:  
"""

#
# runtime support
#
import sys
import os  
from pprint import pprint
from types import NoneType
from datetime import date, datetime,timedelta, time
import random
import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt





def main():
    minutesInDay = 24 * 60

    events = []
    for event in range(0,100):
        start = random.randint(0,minutesInDay)
        stop = start + (random.randint(0,180))
        power = random.random()*5000
        events.append((start, stop, power))
        
        
    events.sort(compareEvents)

    i = 0;
    orderedEvents = []
    for event in events:
        orderedEvents.append((i, event[0], event[1], event[2]))
        i = i + 1
        
    #for orderedEvent in orderedEvents:
    #    for eventMinutes in range(orderedEvent[1], orderedEvent[2]):
    #       print str(eventMinutes) + "," + '%.2f' % round(orderedEvent[3], 2)  + "," + str(orderedEvent[0])

    plot()

def plot():
    mu, sigma = 100, 15
    x = mu + sigma*np.random.randn(10,2)
    print x
    print type(x)
    x = np.array([[2,5],[61,30]])
    print x
    print type(x)

    # the histogram of the data
    n, bins, patches = plt.hist(x, 50, normed=1, facecolor='green', alpha=0.75, histtype='barstacked', cumulative=False)

    # add a 'best fit' line
    #y = mlab.normpdf( bins, mu, sigma)
    #l = plt.plot(bins, y, 'r--', linewidth=1)

    plt.xlabel('')
    plt.ylabel('')
    plt.title('')
    #plt.axis([40, 160, 0, 0.03])
    plt.grid(True)

    plt.show()

# sort start times
def compareEvents(ev1, ev2):
    if ev1[0:1] > ev2[0:1]:
        return 1
    if ev1[0:1] == ev2[0:1]:
        return 0
    if ev1[0:1] < ev2[0:1]:
        return -1





if __name__ == "__main__":
    main()
