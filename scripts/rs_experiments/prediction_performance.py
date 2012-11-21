from __future__ import division
from datetime import date, time, timedelta
from billing.processing.mongo import ReebillDAO
from billing.processing.state import StateDB
from billing.processing.rate_structure import RateStructureDAO
from billing.processing.session_contextmanager import DBSession
from sys import stderr
from pymongo import Connection
from numpy import arange
from matplotlib import pyplot as plt

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

with DBSession(state_db) as session:

    roc = []

    # precision a.k.a. false positive rate = false positives / all predicted positives (precision)
    # recall a.k.a. true positive rate = predicted positives / all real positives

    for threshold in [0.5]:#arange(0, 1, 0.1):

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
                print >> stderr, account, sequence, max_version, e
                continue
            try:
                actual_bindings = [rsi['rsi_binding'] for rsi in actual_rs['rates']]
            except KeyError as e:
                #print >> stderr, 'malformed rate structure doc:', pf(actual_rs)
                print >> stderr, account, sequence, max_version, 'malformed rate structure doc: missing key "%s"' % e.message
                continue

            # temporarily remove real UPRS from database
            uprs_query = {'_id.type':'UPRS', '_id.account': account,
                    '_id.sequence': sequence, '_id.version': max_version}
            uprs = db.ratestructure.find_one(uprs_query)
            if uprs is None:
                #print >> stderr, account, sequence, version 'missing UPRS'
                raise Exception("missing UPRS")
            db.ratestructure.remove(uprs_query)

            # guess the set of UPRS bindings, without the real one in the db
            guessed_rsis = rs_dao._get_probable_rsis(utility_name,
                    rate_structure_name,
                    period=reebill.utilbill_period_for_service(service),
                    threshold=threshold)
            guessed_bindings = [rsi['rsi_binding'] for rsi in guessed_rsis]

            # calculate performance of the guess
            if len(guessed_bindings) == 0:
                precision = 0
            else:
                precision = len([b for b in guessed_bindings if b in
                        actual_bindings]) / len(guessed_bindings)
            if len(actual_bindings) == 0:
                recall = 0
            else:
                recall = len([b for b in actual_bindings if b in
                        guessed_bindings]) / len(actual_bindings)
            roc.append((threshold, 1 - precision, recall))

            print 'actual bindings:', actual_bindings
            print 'guessed bindings:', guessed_bindings
            print '%s-%s-%s %s %s' % (account, sequence, max_version, precision, recall)

            # put real UPRS back in the database
            db.ratestructure.save(uprs)

#print zip(*roc)[1:]
#plt.plot(*zip(*roc)[1:])
#plt.savefig('roc.png')
#plt.show()
