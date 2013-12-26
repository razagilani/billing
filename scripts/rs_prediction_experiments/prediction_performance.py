from __future__ import division
from datetime import date, time, timedelta
from billing.processing.mongo import ReebillDAO
from billing.processing.state import StateDB
from billing.processing.rate_structure import RateStructureDAO, exp_weight
from billing.processing.session_contextmanager import DBSession
from sys import stderr
from pymongo import Connection
from numpy import arange
from matplotlib import pyplot as plt
import csv

import pprint
pf = pprint.PrettyPrinter().pformat

state_db = StateDB(
    host='localhost',
    database='skyline_dev',
    user='dev',
    password='dev'
)
bill_dao = ReebillDAO(state_db, database='skyline-dev')
rs_dao = RateStructureDAO(**{
    'database': 'skyline-dev',
    'collection': 'ratestructure',
    'host': 'localhost',
    'port': 27017
})

db = Connection('localhost')['skyline-dev']

THRESHOLD_STEP = 0.01 # slow
#THRESHOLD_STEP = 0.1 # fast

exp_7 = exp_weight(.5, 1/7)
exp_15 = exp_weight(.5, 1/15)
exp_30 = exp_weight(.5, 1/30)
exp_60 = exp_weight(.5, 1/60)
exp_120 = exp_weight(.5, 1/120)

with DBSession(state_db) as session:

    with open('performance.csv', 'w') as data_file:
        writer = csv.writer(data_file)

        # will store threshold, average precision for all RSIs, average recall for
        # all RSIs
        results = []

        for weight_func_name in ('exp_7',):#, 'exp_15', 'exp_30', 'exp_60', 'exp_120'):
            for threshold in arange(0, 1 + THRESHOLD_STEP, THRESHOLD_STEP):
                print weight_func_name, threshold

                precision_sum, precision_count = 0, 0
                recall_sum, recall_count = 0, 0
                for account, sequence, max_version in state_db.reebills(session):
                    reebill = bill_dao.load_reebill(account, sequence, version=max_version)
                    service = reebill.services[0]
                    utility_name = reebill.utility_name_for_service(service)
                    rate_structure_name = reebill.rate_structure_name_for_service(service)
                    period = reebill.utilbill_period_for_service(service)
                    # ignore reebills that don't yet have definite periods
                    if None in period:
                        continue

                    # get actual rate structure for this reebill, and get the set of
                    # RSI bindings in it
                    try:
                        actual_rs = rs_dao._load_combined_rs_dict(reebill,
                                service)
                        #actual_rs = rs_dao.load_uprs(account, sequence, max_version,
                                #utility_name, rate_structure_name)
                    except ValueError as e:
                        # skip if rate structure not found
                        #print >> stderr, account, sequence, max_version, e
                        continue
                    try:
                        actual_bindings = [rsi['rsi_binding'] for rsi in actual_rs['rates']]
                    except KeyError as e:
                        #print >> stderr, account, sequence, max_version, 'malformed rate structure doc: missing key "%s"' % e.message
                        continue
                    
                    uprs_query = {'_id.type':'UPRS', '_id.account': account,
                            '_id.sequence': sequence, '_id.version': max_version}
                    uprs = db.ratestructure.find_one(uprs_query)
                    if uprs['_id']['rate_structure_name'] != 'DC Non Residential Non Heat':
                        continue

                    if uprs is None:
                        #print >> stderr, account, sequence, version 'missing UPRS'
                        raise Exception("missing UPRS")

                    # function to excude UPRSs from same account, current sequence
                    def ignore(x):
                        try:
                            return (x['_id']['account'] == account and
                                    x['_id']['sequence'] >= sequence)
                        except KeyError:
                            return True

                    # guess the set of UPRS bindings, without the real one in the db
                    guessed_rsis = rs_dao._get_probable_rsis(utility_name,
                            rate_structure_name,
                            period=reebill.utilbill_period_for_service(service),
                            weight_func=globals()[weight_func_name],
                            threshold=threshold, ignore=ignore)
                    guessed_bindings = [rsi['rsi_binding'] for rsi in guessed_rsis]

                    # calculate performance of the guess
                    if len(guessed_bindings) == 0:
                        precision = 1
                    else:
                        precision = len([b for b in guessed_bindings if b in
                                actual_bindings]) / len(guessed_bindings)
                    if len(actual_bindings) == 0:
                        recall = 1
                    else:
                        recall = len([b for b in actual_bindings if b in
                                guessed_bindings]) / len(actual_bindings)
                    precision_sum += precision
                    precision_count += 1
                    recall_sum += recall
                    recall_count += 1

                    correct_quantities, correct_rates, total = 0, 0, 0
                    for binding in guessed_bindings:
                        if binding in actual_bindings:
                            actual_rsi = next(r for r in actual_rs['rates'] if
                                    r['rsi_binding'] == binding)
                            guessed_rsi = next(r for r in guessed_rsis if
                                    r['rsi_binding'] == binding)
                            if guessed_rsi['quantity'] == actual_rsi.get('quantity', 1): # NOTE assume quantity is "1" if missing
                                correct_quantities += 1
                            if guessed_rsi['rate'] == actual_rsi.get('rate', "1"): # NOTE assume rate is "1" if missing
                                correct_rates += 1
                            total += 1
                    if total == 0:
                        quantity_correct_fraction = 1
                        rate_correct_fraction = 1
                    else:
                        quantity_correct_fraction = correct_quantities / total
                        rate_correct_fraction = correct_rates / total

                    #print 'actual bindings:', actual_bindings
                    #print 'guessed bindings:', guessed_bindings
                    #print '%s-%s-%s %s %s' % (account, sequence, max_version, precision, recall)

                avg_precision = precision_sum / precision_count 
                avg_recall = recall_sum / recall_count
                #results.append((weight_func_name, threshold, avg_precision,
                    #avg_recall, quantity_correct_fraction, rate_correct_fraction))
                writer.writerow((weight_func_name, threshold, avg_precision,
                    avg_recall, quantity_correct_fraction, rate_correct_fraction))

#print results
## dump data to file
#import csv
#with open('performance.csv', 'w') as out_file:
    #writer = csv.writer(out_file)
    #for row in results:
        #writer.writerow(row)
