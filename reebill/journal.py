#!/usr/bin/python
import pymongo
import datetime
import uuid
from billing.mongo_utils import bson_convert
from billing.mongo_utils import python_convert

class JournalDAO(object):

    def __init__(self, config):

        self.config = config
        self.connection = None
        self.database = None
        self.collection = None

        try:
            self.connection = pymongo.Connection(self.config['host'], int(self.config['port']))
        except Exception as e: 
            print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            raise e
        
        self.database = self.connection[self.config['database']]
        self.collection = self.database[self.config['collection']]

    def __del__(self):
        # TODO: 17928569 clean up mongo resources here?
        pass

    def journal(self, account, sequence, message):

        journal_entry = {}
        journal_entry['account'] = account
        journal_entry['sequence'] = int(sequence)
        journal_entry['date'] = datetime.datetime.utcnow()
        journal_entry['msg'] = message

        journal_entry_data = bson_convert(journal_entry)

        self.collection.save(journal_entry_data)

    def load_entries(self, account):

        query = {
            "account": account,
        }

        journal_entries = self.collection.find(query)

        # TODO pagination
        return [python_convert(journal_entry) for journal_entry in journal_entries]


