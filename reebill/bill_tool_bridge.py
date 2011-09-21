#!/usr/bin/python
'''
File: bill_tool_bridge.py
Description: Allows bill tool to be invoked as a CGI
'''
import site
site.addsitedir('/var/local/reebill/lib/python2.6/site-packages')

import sys
sys.stdout = sys.stderr

import traceback
import json

# CGI support
import cherrypy

# template support
import jinja2, os

import string

import ConfigParser

#import MySQLdb

from billing.processing import process
from billing.processing import state
from billing.processing import fetch_bill_data as fbd
from billing.reebill import render
from billing.processing.billupload import BillUpload

# TODO fixme
from billing import nexus_util as nu
from billing.nexus_util import NexusUtil

from billing import bill

from billing import json_util as ju

from billing.xml_utils import XMLUtils

import itertools as it

from billing.reebill import bill_mailer

from billing import mongo

import billing.processing.rate_structure as rs

from datetime import datetime
from datetime import date

import pprint
pp = pprint.PrettyPrinter(indent=4)

# TODO rename to ProcessBridge or something
class BillToolBridge:
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill processing code.  No business logic should reside here."""

    config = None

    # TODO: refactor config and share it between btb and bt 15413411
    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bill_tool_bridge.cfg')
        print config_file_path
        if not self.config.read(config_file_path):
            print "Creating config file"
            self.config.add_section('xmldb')
            self.config.set('xmldb', 'destination_prefix', 'http://[host]:8080/exist/rest/db/skyline/bills')
            self.config.set('xmldb', 'source_prefix', 'http://[host]:8080/exist/rest/db/skyline/bills')
            self.config.set('xmldb', 'password', '[password]')
            self.config.set('xmldb', 'user', 'prod')
            self.config.add_section('http')
            self.config.set('http', 'socket_port', '8185')
            self.config.set('http', 'socket_host', '10.0.0.250')
            self.config.add_section('rsdb')
            self.config.set('rsdb', 'rspath', '[root]db/skyline/ratestructure/')
            self.config.add_section('billdb')
            self.config.set('billdb', 'utilitybillpath', '[root]db/skyline/utilitybills/')
            self.config.set('billdb', 'billpath', '[root]db/skyline/bills/')
            self.config.add_section('statedb')
            self.config.set('statedb', 'host', 'localhost')
            self.config.set('statedb', 'db', 'skyline')
            self.config.set('statedb', 'user', 'devTEST7')
            self.config.set('statedb', 'password', '[password]TEST8')
            self.config.add_section('mailer')
            self.config.set('mailer', 'smtp_host', 'smtp.gmail.com')
            self.config.set('mailer', 'smtp_port', '587')
            self.config.set('mailer', 'originator', 'jwatson@skylineinnovations.com')
            self.config.set('mailer', 'from', '"Jules Watson" <jwatson@skylineinnovations.com>')
            self.config.set('mailer', 'password', 'password')

            # For BillUpload
            # default name of log file (config file can override this)
            DEFAULT_LOG_FILE_NAME = 'billupload.log'

            # default format of log entries (config file can override this)
            DEFAULT_LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

            # log file info
            self.config.add_section('log')
            self.config.set('log', 'log_file_name', DEFAULT_LOG_FILE_NAME)
            self.config.set('log', 'log_format', DEFAULT_LOG_FORMAT)


        # Writing our configuration file to 'example.cfg'
        with open(config_file_path, 'wb') as new_config_file:
            self.config.write(new_config_file)

        self.config.read(config_file_path)

        # create an instance representing the database
        statedb_config_section = self.config.items("statedb")
        self.state_db = state.StateDB(dict(statedb_config_section)) 

        # create one BillUpload object to use for all BillUpload-related methods
        self.billUpload = BillUpload(self.config, self.state_db)

        # create a MongoReeBillDAO
        billdb_config_section = self.config.items("billdb")
        xmldb_config_section = self.config.items("xmldb")
        reebill_dao_configs = dict(billdb_config_section + xmldb_config_section)
        #billdb_config_section.update(xmldb_config_section)
        self.reebill_dao = mongo.ReebillDAO(reebill_dao_configs)

        # create one Process object to use for all related bill processing
        self.process = process.Process(self.config, self.state_db, self.reebill_dao)

        # configure mailer
        bill_mailer.config = self.config

        # create on RateStructureDAO to user for all ratestructure queries
        rsdb_config_section = self.config.items("rsdb")
        self.ratestructure_dao = rs.RateStructureDAO(dict(rsdb_config_section))


    # TODO: do this on a per service basis 18311877
    @cherrypy.expose
    def copyactual(self, account, sequence, **args):

        try:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            self.process.copy_actual_charges(reebill)
            self.reebill_dao.save_reebill(reebill)

            return json.dumps({'success': True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def roll(self, account, sequence, **args):

        try:
            self.process.roll_bill(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def pay(self, account, sequence, **args):

        try:
            self.process.pay_bill(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def bindree(self, account, sequence, **args):

        from billing.processing import fetch_bill_data as fbd
        try:
            # TODO make args to fetch bill data optional
            fbd.fetch_bill_data(
                "http://duino-drop.appspot.com/",
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password"),
                nu.NexusUtil("nexus").olap_id(account),
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                None,
                None,
                True
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def bindrs(self, account, sequence, **args):

        try:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            self.process.bind_rate_structure(reebill, ratestructure_dao)
            return json.dumps({'success': True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def calc_reperiod(self, account, sequence, **args):

        try:
            self.process.calculate_reperiod(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def calcstats(self, account, sequence, **args):

        try:
            self.process.calculate_statistics(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def sum(self, account, sequence, **args):

        try:
            present_reebill = self.reebill_dao.load_reebill(account, sequence)
            prior_reebill = self.reebill_dao.load_reebill(account, int(sequence)-1)
            self.process.sum_bill(prior_reebill, present_reebill)
            self.reebill_dao.save_reebill(present_reebill)

            return json.dumps({'success': True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        
    @cherrypy.expose
    def issue(self, account, sequence, **args):


        try:
            self.process.issue(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})



    @cherrypy.expose
    def render(self, account, sequence, **args):

        try:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            render.render(reebill, 
                self.config.get("billdb", "billpath")+ "%s/%s.pdf" % (account, sequence),
                "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
                None,
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def commit(self, account, sequence, **args):

        try:

            self.process.commit_rebill(account, sequence)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def issueToCustomer(self, account, sequence, **args):

        try:
            self.process.issue_to_customer(account, sequence)
            return json.dumps({'success': True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})



    @cherrypy.expose
    def mail(self, account, sequences, recipients, **args):

        try:

            # sequences will come in as a string if there is one element in post data. 
            # If there are more, it will come in as a list of strings
            if type(sequences) is not list: sequences = [sequences]
            # acquire the most recent reebill from the sequence list and use its values for the merge
            sequences = [sequence for sequence in sequences]
            sequences.sort()

            all_bills = [self.reebill_dao.load_reebill(account, sequence) for sequence in sequences]

            # the last element
            most_recent_bill = all_bills[-1]

            bill_file_names = ["%s.pdf" % sequence for sequence in sequences]
            bill_dates = ["%s" % (b.period_end) for b in all_bills]
            bill_dates = ", ".join(bill_dates)

            merge_fields = {}
            merge_fields["street"] = most_recent_bill.service_address["street"]
            merge_fields["balance_due"] = most_recent_bill.balance_due
            merge_fields["bill_dates"] = bill_dates
            merge_fields["last_bill"] = bill_file_names[-1]

            bill_mailer.mail(recipients, merge_fields, os.path.join(self.config.get("billdb", "billpath"), account), bill_file_names);


        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    #TODO make this generic enough that all other account listing functions can return pretty names
    def prettyify_account_numbers(self, accounts):
        # now get associated names from Nexus and add them to each account dictionary
        rows = []
        for account in accounts:
            row = {'account':account}
            display_name = [account]

            all_names = NexusUtil().all("billing", account)
            if 'codename' in all_names:
                display_name.append(all_names['codename'])
            if 'casualname' in all_names:
                display_name.append(all_names['casualname'])
            if 'primus' in all_names:
                display_name.append(all_names['primus'])
            #account['name'] = string.join(display_name, ' - ')
            row['name'] = ' - '.join(display_name)
            rows += [row]

        return rows

    @cherrypy.expose
    def listAccounts(self, **kwargs):
        accounts = []
        try:
            # eventually, this data will have to support pagination

            accounts = self.state_db.listAccounts()

            rows = self.prettyify_account_numbers(accounts)

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True, 'rows':rows})

    @cherrypy.expose
    def listSequences(self, account, **kwargs):
        sequences = []
        try:
            # eventually, this data will have to support pagination
            sequences = self.state_db.listSequences(account)
            rows = [{'sequence': sequence} for sequence in sequences]
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True, 'rows':rows})

    @cherrypy.expose
    def retrieve_status_days_since(self, start, limit, **args):
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            statuses, totalCount = self.state_db.retrieve_status_days_since(int(start), int(limit))

            # TODO: refactor nexus lookup 
            
            # convert the result into a list of dictionaries for returning as
            # JSON to the browser
            rows = []
            for status in statuses:
                all_names = NexusUtil().all("billing", status.account)
                display_name = [status.account]
                if 'codename' in all_names:
                    display_name.append(all_names['codename'])
                if 'casualname' in all_names:
                    display_name.append(all_names['casualname'])
                if 'primus' in all_names:
                    display_name.append(all_names['primus'])
                rows.append({'account': string.join(display_name, '-'), 'dayssince':status.dayssince})

            return ju.dumps({'success': True, 'rows':rows, 'results':totalCount})
        except Exception as e:
            # TODO: log errors?
            print >> sys.stderr, e
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def retrieve_status_unbilled(self, start, limit, **args):
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            statuses, totalCount = self.state_db.retrieve_status_unbilled(int(start), int(limit))
            
            # convert the result into a list of dictionaries for returning as
            # JSON to the browser
            rows = []
            for status in statuses:
                all_names = NexusUtil().all("billing", status.account)
                display_name = [status.account]
                if 'codename' in all_names:
                    display_name.append(all_names['codename'])
                if 'casualname' in all_names:
                    display_name.append(all_names['casualname'])
                if 'primus' in all_names:
                    display_name.append(all_names['primus'])
                rows.append({'account': string.join(display_name, '-')})

            return ju.dumps({'success': True, 'rows':rows, 'results':totalCount})
        except Exception as e:
            # TODO: log errors?
            print >> sys.stderr, e
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    # TODO see 15415625 about the problem passing in service to get at a set of RSIs
    # TODO make this support new URS, UPRS and CPRS structure
    # experiment to see how using one URL for all operations works
    def rsi(self, xaction, account, sequence, service, **kwargs):

        try:

            reebill = self.reebill_dao.load_reebill(account, sequence)

            rate_structure = self.ratestructure_dao.load_rs(reebill, service)
            rates = rate_structure["rates"]

            if xaction == "read":
                return json.dumps({'success': True, 'rows':rates})

            elif xaction == "update":

                # all grid editor changes must be batched since yaml file cannot be written asynchronously 
                # convert json to python
                rows = json.loads(kwargs["rows"])

                # single edit comes in not in a list
                if type(rows) is dict: rows = [rows]

                # process list of edits
                for row in rows:

                    # identify the RSI descriptor of the posted data
                    descriptor = row["descriptor"]

                    # identify the rsi in the rs_yaml, and update it with posted data
                    # python is totally evil
                    #If there is more than one returned, this is an exception so break the above statement out later
                    matches = [rsi_match for rsi_match in it.ifilter(lambda x: x["descriptor"]==descriptor, rates)]
                    if (len(matches) > 1):
                        raise Exception("matched more than one RSI which should not be possible")
                    rsi = matches[0]

                    # eliminate attributes that have empty strings or None as these mustn't 
                    # be added to the RSI so the RSI knows to compute for those values
                    for k,v in row.items():
                        if v is None or v == "":
                            del row[k]

                    # now take the legitimate values from the posted data and update the RSI
                    # clear it so that the old emptied attributes are removed
                    rsi.clear()
                    rsi.update(row)
                    

                self.ratestructure_dao.save_rs(account, sequence, rsbinding, rate_structure)

                return json.dumps({'success':True})

            elif xaction == "create":
                # create operations require the server to return the initial record, initialized with key

                new_rate = {"descriptor":"NEW"}
                rates.append(new_rate)

                self.ratestructure_dao.save_rs(account, sequence, rsbinding, rate_structure)

                return json.dumps({'success':True, 'rows':new_rate})

            elif xaction == "destroy":

                descriptors = json.loads(kwargs["rows"])

                # single edit comes in not in a list
                # TODO: understand why this is a unicode coming up from browser
                if type(descriptors) is unicode: descriptors = [descriptors]

                # process list of removals
                for descriptor in descriptors:

                    # identify the rsi in the rs_yaml, and update it with posted data
                    # python is totally evil
                    #If there is more than one returned, this is an exception so break the above statement out later
                    rates.remove([result for result in it.ifilter(lambda x: x["descriptor"]==descriptor, rates)][0])
                    #print [result for result in it.ifilter(lambda x: x["descriptor"]==descriptor, rates)]

                self.ratestructure_dao.save_rs(account, sequence, rsbinding, rate_structure)

                return json.dumps({'success':True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def payment(self, xaction, account, sequence, **kwargs):

        try:

            if xaction == "read":

                payments = self.state_db.payments(account)

                payments = [{
                    'id': payment.id, 
                    'date': str(payment.date),
                    'description': payment.description, 
                    'credit': str(payment.credit),
                } for payment in payments]
                
                return json.dumps({'success': True, 'rows':payments})

            elif xaction == "update":

                rows = json.loads(kwargs["rows"])

                # single edit comes in not in a list
                if type(rows) is dict: rows = [rows]

                # process list of edits
                for row in rows:
                    self.state_db.update_payment(
                        row['id'],
                        row['date'],
                        row['description'],
                        row['credit'],
                    )
                         


                return json.dumps({'success':True})

            elif xaction == "create":

                from datetime import date

                new_payment = self.state_db.create_payment(account, date.today(), "New Entry", "0.00")
                # TODO: is there a better way to populate a dictionary from an ORM object dict?
                row = [{
                    'id': new_payment.id, 
                    'date': str(new_payment.date),
                    'description': new_payment.description,
                    'credit': str(new_payment.credit),
                    }]

                return json.dumps({'success':True, 'rows':row})

            elif xaction == "destroy":

                rows = json.loads(kwargs["rows"])

                # single delete comes in not in a list
                if type(rows) is int: rows = [rows]

                for oid in rows:
                    self.state_db.delete_payment(oid)
                         
                return json.dumps({'success':True})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def reebill(self, xaction, start, limit, account, **kwargs):

        try:

            if xaction == "read":

                reebills, totalCount = self.state_db.listReebills(int(start), int(limit), account)
                
                # convert the result into a list of dictionaries for returning as
                # JSON to the browser
                rows = [{'sequence': reebill.sequence} for reebill in reebills]

                return json.dumps({'success': True, 'rows':rows, 'results':totalCount})

            elif xaction == "update":

                return json.dumps({'success':False})

            elif xaction == "create":

                return json.dumps({'success':False})

            elif xaction == "destroy":

                return json.dumps({'success':False})

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    ################
    # Handle ubPeriods

    @cherrypy.expose
    def ubPeriods(self, account, sequence, **args):
        """
        Return all of the utilbill periods on a per service basis so that the forms may be
        dynamically created.
        """

        try:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            
            # TODO: consider re-writing client code to not rely on labels,
            # then the reebill datastructure itself can be shipped to client.
            utilbill_periods = {}
            for service in reebill.services:
                (begin, end) = reebill.utilbill_period_for_service(service)
                utilbill_periods[service] = {
                    'begin': begin,
                    'end': end
                    }

            return ju.dumps(utilbill_periods)

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def setUBPeriod(self, account, sequence, service, begin, end, **args):
        """ 
        Utilbill period forms are dynamically created in browser, and post back to here individual periods.
        """ 

        try:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_utilbill_period_for_service(service, (datetime.strptime(begin, "%Y-%m-%d").date(),datetime.strptime(end, "%Y-%m-%d").date()))
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    #
    ################

    ################
    # handle actual and hypothetical charges 

    @cherrypy.expose
    def actualCharges(self, service, account, sequence, **args):

        try:

            reebill = self.reebill_dao.load_reebill(account, sequence)
            flattened_charges = reebill.actual_chargegroups_flattened(service)
            return ju.dumps({'success': True, 'rows': flattened_charges})

        except Exception as e:

            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def hypotheticalCharges(self, service, account, sequence, **args):

        try:

            reebill = self.reebill_dao.load_reebill(account, sequence)
            flattened_charges = reebill.hypothetical_chargegroups_flattened(service)
            return ju.dumps({'success': True, 'rows': flattened_charges})

        except Exception as e:

            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def saveActualCharges(self, service, account, sequence, rows, **args):
    
        try:
            flattened_charges = ju.loads(rows)

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_actual_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success': True})

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def saveHypotheticalCharges(self, service, account, sequence, rows, **args):
        try:
            flattened_charges = ju.loads(rows)

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_hypothetical_chargegroups_flattened(service, flattened_charges)
            self.reebill_dao.save_reebill(reebill)
        
            return ju.dumps({'success': True})

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    ################
    # Handle measuredUsages

    @cherrypy.expose
    def ubMeasuredUsages(self, account, sequence, **args):
        """
        Return all of the measuredusages on a per service basis so that the forms may be
        dynamically created.
        """

        try:
            reebill = self.reebill_dao.load_reebill(account, sequence)
            meters = reebill.meters
            return ju.dumps(meters)

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def setMeter(self, account, sequence, service, meter_identifier, presentreaddate, priorreaddate):

        try:

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_meter_read_date(service, meter_identifier, presentreaddate, priorreaddate)
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})


    @cherrypy.expose
    def setActualRegister(self, account, sequence, service, register_identifier, meter_identifier, total):

        try:

            reebill = self.reebill_dao.load_reebill(account, sequence)
            reebill.set_meter_actual_register(service, meter_identifier, register_identifier, total)
            self.reebill_dao.save_reebill(reebill)

            return ju.dumps({'success':True})

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})



    #
    ################

    ################
    # Handle utility bill upload

    @cherrypy.expose
    def upload_utility_bill(self, account, begin_date, end_date, file_to_upload, **args):
        try:
            # get Python file object and file name as string from the CherryPy
            # object 'file_to_upload', and pass those to BillUpload so it's
            # independent of CherryPy
            if self.billUpload.upload(account, begin_date, end_date, file_to_upload.file, file_to_upload.filename) is True:
                return ju.dumps({'success':True})
            else:
                return ju.dumps({'success':False, 'errors':{'reason':'file upload failed', 'details':'Returned False'}})
        except Exception as e: 
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    #
    ################

 
    @cherrypy.expose
    def listUtilBills(self, start, limit, **args):
        # call getrows to actually query the database; return the result in
        # JSON format if it succeded or an error if it didn't
        try:
            utilbills, totalCount = self.state_db.list_utilbills(int(start), int(limit))
            
            # convert the result into a list of dictionaries for returning as
            # JSON to the browser
            rows = []
            for utilbill in utilbills:

                # wouldn't it be nice if the db_objects dealt with the lack of relationship better? Not sure.
                sequence = utilbill.reebill.sequence if utilbill.reebill else None
                account = utilbill.customer.account if utilbill.customer else None

                all_names = NexusUtil().all("billing", account)
                display_name = [account]

                if 'codename' in all_names:
                    display_name.append(all_names['codename'])
                if 'casualname' in all_names:
                    display_name.append(all_names['casualname'])
                if 'primus' in all_names:
                    display_name.append(all_names['primus'])

                rows.append({'account':account, 'name': string.join(display_name, '-'), 'period_start': utilbill.period_start,
                'period_end':utilbill.period_end, 'sequence':sequence})

            return ju.dumps({'success': True, 'rows':rows,
                'results':totalCount})
        except Exception as e:
            # TODO: log errors?
            print >> sys.stderr, e
            #return '{success: false}'
            return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})
    
    @cherrypy.expose
    def getUtilBillImage(self, account, begin_date, end_date, **args):
        try:
            # TODO: put url here, instead of in billentry.js?
            result = self.billUpload.getUtilBillImagePath(account, begin_date, end_date)
            return ju.dumps({'success':True, 'imageName':result})
        except Exception as e: 
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

    @cherrypy.expose
    def getReeBillImage(self, account, sequence, **args):
        try:
            result = self.billUpload.getReeBillImagePath(account, sequence)
            return ju.dumps({'success':True, 'imageName':result})
        except Exception as e: 
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

# TODO: place instantiation in main, so this module can be loaded without btb being instantiated
bridge = BillToolBridge()

if __name__ == '__main__':

    # configure CherryPy
    local_conf = {
        '/' : {
            'tools.staticdir.root' :os.path.dirname(os.path.abspath(__file__)), 
            #'tools.staticdir.dir' : '',
            #'tools.staticdir.on' : True,
            'tools.expires.secs': 0,
            'tools.response_headers.on': True,
        },
    }
    cherrypy.config.update({ 'server.socket_host': bridge.config.get("http", "socket_host"),
                             'server.socket_port': int(bridge.config.get("http", "socket_port")),
                             })
    cherrypy.quickstart(bridge, "/", config = local_conf)
else:
    # WSGI Mode
    cherrypy.config.update({'environment': 'embedded'})

    if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
        cherrypy.engine.start(blocking=False)
        atexit.register(cherrypy.engine.stop)

    application = cherrypy.Application(bridge, script_name=None, config=None)

