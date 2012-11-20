#!/usr/bin/python
'''This script re-renders all the reebill PDFs. Make sure to set the config
parameters with "dev" in them to "prod" before running on tyrell.'''
import traceback
from billing import mongo
from billing.reebill import render
from billing.processing import state
from billing.processing.session_contextmanager import DBSession

billdb_config = {
    'billpath': '/db-dev/skyline/bills/',
    'database': 'skyline',
    'utilitybillpath': '/db-dev/skyline/utilitybills/',
    'collection': 'reebills',
    'host': 'localhost',
    'port': '27017'
}
statedb_config = {
    'host': 'localhost',
    'password': 'dev',
    'database': 'skyline_dev',
    'user': 'dev'
}
renderer_config = {
    'temp_directory': '/tmp/reebill_rendering_files'
}

state_db = state.StateDB(**statedb_config)
reebill_dao = mongo.ReebillDAO(state_db, **billdb_config)

with DBSession(state_db) as session:
    renderer = render.ReebillRenderer(renderer_config, state_db, reebill_dao,
            None)

    accounts = state_db.listAccounts(session)

    for account in accounts:
        sequences = state_db.listSequences(session, account)
        for sequence in sequences:
            print '%s-%s' % (account, sequence)
            try:
                reebill = reebill_dao.load_reebill(account, sequence)
                renderer.render(
                    session,
                    reebill.account, 
                    reebill.sequence,
                    billdb_config["billpath"] + account,
                    "%.4d.pdf" % int(sequence),
                    "EmeraldCity-FullBleed-1v2.png,EmeraldCity-FullBleed-2v2.png",
                    False
                )
            except Exception as e:
                print e, traceback.format_exc()
