import csv
from matplotlib import pyplot as plt
from itertools import groupby
from operator import itemgetter

def floatify(s):
    try:
        return float(s)
    except ValueError:
        return s

with open('performance.csv') as in_file:
    data = csv.reader(in_file)
    data = [map(floatify, row) for row in data]

    max_f1s = []
    for weight_func_name, data_chunk in groupby(data, key=itemgetter(0)):
        print weight_func_name
        _, _, precision, recall = zip(*data)[:4]
        f1 = [2*p*r/(p + r) for p, r in zip(precision, recall)]
        max_f1s.append((weight_func_name, max(f1)))

    print max(max_f1s, key=itemgetter(1))
