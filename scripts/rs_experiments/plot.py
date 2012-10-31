from sys import argv
from datetime import datetime
import numpy as np
import matplotlib
# this allows the script to save a file without needing X server. must be run before pyplot is imported.
# see http://stackoverflow.com/questions/4706451/how-to-save-a-figure-remotely-with-pylab
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from glob import glob
from os.path import basename
from hashlib import md5

if len(argv) > 1:
    rsi_bindings = [argv[1]]
else:
    rsi_bindings = [basename(f) for f in glob('rs_data/*')]

matplotlib.rc('font', size=6)

for rsi_binding in rsi_bindings:
    print rsi_binding
    with open('rs_data/' + rsi_binding) as in_file:
        # for each line of the file, make one "line chart" to plot an interval of it
        for line in in_file:
            account, start, end, rate = line.split()
            start = datetime.strptime(start, '%Y-%m-%d')
            end = datetime.strptime(end, '%Y-%m-%d')

            # matplotlib color based on hash of account
            color = '#' + ''.join(['%02x' % ord(byte) for byte in md5(account).digest()[-3:]])

            # plot with start/end bars (markers needed because some bills' lines are overlapping)
            plt.plot([start, end], [rate, rate], '-|', color=color)

    # save image to file
    plt.savefig('graphs/' + rsi_binding + '.pdf')

#for rsi_binding in rsi_bindings:
    #print rsi_binding
    #with open('rs_data/' + rsi_binding) as in_file:
        ## for each line of the file, make one "line chart" to plot an interval of it
        #lines = sorted([l.split() for l in in_file.readlines()], key=lambda l:l[0])
        #for account, periods in groupby(lines, key=lambda l:l[0]):
            ## matplotlib color based on hash of account
            #color = '#' + ''.join(['%02x' % ord(byte) for byte in md5(account).digest()[-3:]])

            #dates, rates = [], []
            #for _, start, end, rate in periods:
                #start = datetime.strptime(start, '%Y-%m-%d')
                #end = datetime.strptime(end, '%Y-%m-%d')
                #dates.extend((start, end))
                #rates.extend((rate, rate))

            ## plot with start/end bars (markers needed because some bills' lines are overlapping)
            #plt.plot(dates, rates, '-|', color=color)

    ## save image to file
    #plt.savefig('graphs/' + rsi_binding + '.pdf')
