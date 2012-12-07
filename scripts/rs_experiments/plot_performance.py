import csv
from matplotlib import pyplot as plt
from itertools import groupby
from operator import itemgetter

#FILENAME = 'performance-manhattan-gaussian-.01.csv'
FILENAME = 'performance.csv'
THICKNESS = 5

def floatify(s):
    try:
        return float(s)
    except ValueError:
        return s

with open(FILENAME) as in_file:
    data = csv.reader(in_file)
    data = [map(floatify, row) for row in data]

    #threshold, precision, recall, quantity_correctness, rate_correctness = zip(*data)
    #weight_func_name, threshold, precision, recall = zip(*data)[:3]

    for weight_func_name, data_chunk in groupby(data, key=itemgetter(0)):
        print weight_func_name
        _, threshold, precision, recall = zip(*data)[:4]
        print len(threshold), len(precision), len(recall)

        # plot precision, recall vs. threshold
        precision_recall = plt.figure(1)
        plt.tick_params(axis='both', which='major', labelsize=24)
        plt.plot(threshold, precision, linewidth=THICKNESS)
        plt.plot(threshold, recall, linewidth=THICKNESS)
        plt.plot(threshold, [2*p*r/(p + r) for p, r in zip(precision, recall)],
                color='gray')
        precision_recall.savefig('precision_recall.png')

        # plot ROC curve
        roc = plt.figure(2)
        plt.tick_params(axis='both', which='major', labelsize=24)
        plt.plot([1 - p for p in precision], recall, color='r',
                linewidth=THICKNESS)
        roc.savefig('roc.png')

        plt.show()
