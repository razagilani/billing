#!/usr/bin/python
'''
File: bill_tool_bridge.py
Description: Allows bill tool to be invoked as a CGI
'''
import site
site.addsitedir('/var/local/billtool/lib/python2.6/site-packages')

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

from billing.processing import process
from billing.processing import state
from billing.processing import fetch_bill_data as fbd
from billing.presentation import render

from billing import nexus_util as nu

from billing import bill

from billing import json_util as ju

from skyliner.xml_utils import XMLUtils

from billing.nexus_util import NexusUtil




# TODO rename to ProcessBridge or something
class BillToolBridge:
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill processing code.  No business logic should reside here."""

    config = None

    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bill_tool_bridge.cfg')
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
            self.config.add_section('billdb')
            self.config.set('billdb', 'rspath', '[root]db/skyline/ratestructure/')
            self.config.set('billdb', 'billpath', '[root]db/skyline/bills/')
            self.config.add_section('statedb')
            self.config.set('statedb', 'host', 'localhost')
            self.config.set('statedb', 'database', 'skyline')
            self.config.set('statedb', 'user', 'dev')
            self.config.set('statedb', 'password', '[password]')


            # Writing our configuration file to 'example.cfg'
            with open(config_file_path, 'wb') as new_config_file:
                self.config.write(new_config_file)

            self.config.read(config_file_path)



    @cherrypy.expose
    def copyactual(self, account, sequence, **args):

        try:
            process.Process().copy_actual_charges(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def roll(self, account, sequence, amount, **args):
        # TODO: remove this business logic to Process()
        # check to see if this bill can be rolled


        try:

            last_sequence = state.last_sequence(
                self.config.get("statedb", "host"),
                self.config.get("statedb", "db"),
                self.config.get("statedb", "user"),
                self.config.get("statedb", "password"),
                account
            )

            # TODO: Process() should implement this

            # last_sequence is None if no prior bills have been rolled (sequence 0)
            if last_sequence is not None and (int(sequence) < int(last_sequence)):
                return '{success: false, errors: {reason:"Not the last sequence"}}'

                # TODO: Process() should implement this
                if (int(sequence) < int(last_sequence)):
                    return '{success: false, errors: {reason:"Not the last sequence"}}'


            process.Process().roll_bill(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, int(sequence)+1),
                amount,
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )   

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
            # actual
            process.Process().bindrs(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("billdb", "rspath"),
                False, 
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )


            #hypothetical
            process.Process().bindrs(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("billdb", "rspath"),
                True, 
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

            process.Process().calculate_reperiod(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def calcstats(self, account, sequence, **args):

        try:
            process.Process().calculate_statistics(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def sum(self, account, sequence, **args):

        try:
            # sum actual
            process.Process().sum_actual_charges(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

            # sum hypothetical
            process.Process().sum_hypothetical_charges(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )
        
            # get discount rate
            discount_rate = state.discount_rate(
                self.config.get("statedb", "host"),
                self.config.get("statedb", "db"),
                self.config.get("statedb", "user"),
                self.config.get("statedb", "password"),
                account
            )

            process.Process().sumbill(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                discount_rate,
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})
        
    @cherrypy.expose
    def issue(self, account, sequence, **args):

        # only sets the issue date

        try:
            process.Process().issue(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
                None,
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})



    @cherrypy.expose
    def render(self, account, sequence, **args):

        try:
            render.render(
                "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
                self.config.get("billdb", "billpath")+ "%s/%s.pdf" % (account, sequence),
                "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
                None,
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def commit(self, account, sequence, begin, end, **args):
        
        try:
            state.commit_bill(
                self.config.get("statedb", "host"),
                self.config.get("statedb", "db"),
                self.config.get("statedb", "user"),
                self.config.get("statedb", "password"),
                account,
                sequence,
                begin,
                end
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})

    @cherrypy.expose
    def issueToCustomer(self, account, sequence, **args):

        try:
            state.issue(
                self.config.get("statedb", "host"),
                self.config.get("statedb", "db"),
                self.config.get("statedb", "user"),
                self.config.get("statedb", "password"),
                account,
                sequence
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True})


    @cherrypy.expose
    def listAccounts(self, **kwargs):
        accounts = []
        try:
            # eventually, this data will have to support pagination
            accounts = state.listAccounts(
                self.config.get("statedb", "host"),
                self.config.get("statedb", "db"),
                self.config.get("statedb", "user"),
                self.config.get("statedb", "password"),
            )

            # now get associated names from Nexus and add them to each account dictionary
            nu = NexusUtil()
            for account in accounts:
                all_names = NexusUtil().all("billing", account['account'])
                display_name = [account['account']]
                if 'codename' in all_names:
                    display_name.append(all_names['codename'])
                if 'casualname' in all_names:
                    display_name.append(all_names['casualname'])
                if 'primus' in all_names:
                    display_name.append(all_names['primus'])

                account['name'] = string.join(display_name, ' - ')



        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True, 'rows':accounts})

    @cherrypy.expose
    def listSequences(self, account, **kwargs):
        sequences = []
        try:
            # eventually, this data will have to support pagination
            sequences = state.listSequences(
                self.config.get("statedb", "host"),
                self.config.get("statedb", "db"),
                self.config.get("statedb", "user"),
                self.config.get("statedb", "password"),
                account
            )
        except Exception as e:
                return json.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return json.dumps({'success': True, 'rows':sequences})


    ################
    # Handle ubPeriods

    @cherrypy.expose
    def ubPeriods(self, account, sequence, **args):
        """
        Return all of the utilbill periods on a per service basis so that the forms may be
        dynamically created.
        """
        utilbill_periods = {}

        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubSummary = the_bill.utilbill_summary_charges

            # TODO: just return utilbill summary charges and let extjs render the form
            for service, summary in ubSummary.items():
                utilbill_periods[service] = {
                    'begin':summary.begin,
                    'end':summary.end
                    }

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps(utilbill_periods)

    @cherrypy.expose
    def setUBPeriod(self, account, sequence, service, begin, end, **args):
        """ 
        Utilbill period forms are dynamically created in browser, and post back to here individual periods.
        """ 

        try:
            the_bill = bill.Bill( "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubSummary = the_bill.utilbill_summary_charges

            ubSummary[service].begin = begin
            ubSummary[service].end = end

            the_bill.utilbill_summary_charges = ubSummary

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )


        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success':True})

    #
    ################

    ################
    # Handle measuredUsages

    @cherrypy.expose
    def ubMeasuredUsages(self, account, sequence, **args):
        """
        Return all of the measuredusages on a per service basis so that the forms may be
        dynamically created.
        """

        try:
            the_bill = bill.Bill("%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubMeasuredUsages = the_bill.measured_usage

        except Exception as e:
            return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps(ubMeasuredUsages)


    @cherrypy.expose
    def setMeter(self, account, sequence, service, meter_identifier, presentreaddate, priorreaddate):

        try:

            the_bill = bill.Bill( "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubMeasuredUsages = the_bill.measured_usage

            # TODO: better way to filter for meter? The list comprehension should always be a list of one element
            # TODO: error conditions
            meter = [meter for meter in ubMeasuredUsages[service] if meter.identifier == meter_identifier]
            meter = meter[0] if meter else None
            if meter is None: print "Should have found a single meter"
            meter.presentreaddate = presentreaddate
            meter.priorreaddate = priorreaddate

            the_bill.measured_usage = ubMeasuredUsages

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success':True})

    @cherrypy.expose
    def setActualRegister(self, account, sequence, service, register_identifier, meter_identifier, total):

        try:

            the_bill = bill.Bill( "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence))

            ubMeasuredUsages = the_bill.measured_usage

            # TODO: better way to filter for register and meter? The list comprehension should always be a list of one element
            # TODO: error conditions
            meter = [meter for meter in ubMeasuredUsages[service] if meter.identifier == meter_identifier]
            meter = meter[0] if meter else None
            if meter is None: print "Should have found a single meter"

            register = [register for register in meter.registers if register.identifier == register_identifier and register.shadow is False]
            register = register[0] if register else None
            if register is None: print "Should have found a single register"

            register.total = total

            print "will set %s" % ubMeasuredUsages
            the_bill.measured_usage = ubMeasuredUsages
            print "did set %s" % the_bill.measured_usage

            XMLUtils().save_xml_file(the_bill.xml(), "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence),
                self.config.get("xmldb", "user"),
                self.config.get("xmldb", "password")
            )

        except Exception as e:
             return ju.dumps({'success': False, 'errors':{'reason': str(e), 'details':traceback.format_exc()}})

        return ju.dumps({'success':True})


    #
    ################


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

