import sys
from itertools import chain
from random import randint
from datetime import datetime, timedelta
import pymongo
from pandas import DataFrame
from numpy import ndarray, append
from collections import defaultdict
from billing.processing.state import StateDB, UtilBill
from billing.processing.mongo import ReebillDAO

# TODO: doesn't work
# # set up matplotlib to actually show plots on Ubuntu--requires pygtk to be
# # installed
# import matplotlib
# matplotlib.use('GTKAgg')
from matplotlib import pyplot as plt

sdb = StateDB(**{
    'host': 'localhost',
    'database': 'skyline_dev',
    'user': 'dev',
    'password': 'dev',
})
db = pymongo.Connection(host='localhost')['skyline-dev']
rbd = ReebillDAO(sdb, db)

s = sdb.session()

def get_charges_iterable(utilbill_doc):
    return chain.from_iterable(charges_of_group for group,
            charges_of_group in utilbill_doc['chargegroups'].iteritems())

def print_bindings(args):
    '''Just show which RSI bindings occur for this utility/rate class
    and how many times each one has occurred.
    '''
    query = s.query(UtilBill).filter_by(state=UtilBill.Complete,
            utility=args.utility, rate_class=args.rate_class).order_by(
            UtilBill.period_start).all()
    bindings = defaultdict(lambda: 0)
    for u in query:
        for c in get_charges_iterable(rbd.load_doc_for_utilbill(u)):
            bindings[c['rsi_binding']] += 1

    data = sorted([(count, name) for name, count in bindings.iteritems()],
                  reverse=True)
    for count, name in data:
        print '%2s %s' % (count, name)

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser(description='')
    # parser.add_argument('--host', default='localhost')
    # parser.add_argument('--db', required=True)
    parser.add_argument('utility')
    parser.add_argument('rate_class')
    parser.add_argument('rsi_binding', nargs='?', default=None)
    args = parser.parse_args()

    if args.rsi_binding is None:
        print_bindings(args)
        sys.exit()

    array = ndarray([0,5])
    for utilbill in s.query(UtilBill).filter_by(
            state=UtilBill.Complete, utility=args.utility, \
            rate_class=args.rate_class) \
            .order_by(UtilBill.period_start).all():
        doc = rbd.load_doc_for_utilbill(utilbill)
        for charge in get_charges_iterable(doc):
            if charge.get('rsi_binding') == args.rsi_binding:
                q, r, t = charge['quantity'], charge['rate'], charge['total']
                # TODO: consider using q*r instead of t just in case of errors
                start = utilbill.period_start
                end = utilbill.period_end
                array = append(array, [[start, end, q, r, t]], axis=0)
    frame = DataFrame(data=array, columns=('start', 'end', 'quantity', 'rate', 'total'))
    print '%s occurrences found' % frame.shape[0]

    fig = plt.subplot()
    fig.scatter(frame.start, frame.rate, marker='x',  facecolors='none',
                edgecolors='b')
    fig.scatter(frame.end, frame.rate, marker='x',  facecolors='none',
                edgecolors='r')
    middle = [s + (e - s)/2 for s, e in zip(frame.start, frame.end)]
    fig.scatter(middle, frame.rate, marker='x',
                facecolors='none', edgecolors='g')

    #fig.scatter(frame.end, frame.rate, marker='x', color='red')
    # for i in xrange(frame.shape[0]):
    #     start, end, _, r, _ = frame.values[i]
    #     fig.plot([start, end], [r, r], marker='x')
    fig.tick_params(axis='both', labelsize=8)
    fig.xaxis.grid()
    plt.savefig('plot.png')





