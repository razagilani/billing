from sys import argv
from datetime import datetime
import numpy as np
import matplotlib
# this allows the script to save a file without needing X server. must be run before pyplot is imported.
# see http://stackoverflow.com/questions/4706451/how-to-save-a-figure-remotely-with-pylab
matplotlib.use('Agg')
from matplotlib import pyplot as plt

# TODO include accounts in data so all bills from one account can be colored the same
#
rsi_binding = argv[1]
with open('rs_data/' + rsi_binding) as in_file:
    for line in in_file:
        # for each line of the file, make one "line chart" to plot an interval of it
        start, end, rate = line.split()
        start = datetime.strptime(start, '%Y-%m-%d')
        end = datetime.strptime(end, '%Y-%m-%d')
        # plot with x's (markers needed because some bills' lines are overlapping)
        plt.plot([start, end], [rate, rate], 'x')

# save image to file
plt.savefig(rsi_binding + '.pdf')
