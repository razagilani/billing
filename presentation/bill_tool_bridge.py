#!/usr/bin/python
'''
File: bill_tool_bridge.py
Description: Allows bill tool to be invoked as a CGI
'''
import site
site.addsitedir('/var/local/billtool/lib/python2.6/site-packages')

import sys
sys.stdout = sys.stderr

# CGI support
import cherrypy

# template support
import jinja2, os

import ConfigParser

from billing.processing import process
from billing.processing import state
from billing.processing import fetch_bill_data as fbd
from billing.presentation import render

from billing import nexus_util as nu


# TODO rename to ProcessBridge or something
# TODO don't require UI to pass in destination.
class BillToolBridge:
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill processing code.  No business logic should reside here."""

    src_prefix = dest_prefix = "http://tyrell:8080/exist/rest/db/skyline/bills/"
    config = None

    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        #print os.path.dirname(os.path.realpath(__file__))
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bill_tool_bridge.cfg')
        if not self.config.read(config_file_path):
            print "Creating config file"
            self.config.add_section('xmldb')
            self.config.set('xmldb', 'destination_prefix', 'http://tyrell:8080/exist/rest/db/skyline/bills')
            self.config.set('xmldb', 'source_prefix', 'http://tyrell:8080/exist/rest/db/skyline/bills')
            self.config.set('xmldb', 'password', '[password]')
            self.config.set('xmldb', 'user', 'prod')
            self.config.add_section('http')
            self.config.set('http', 'socket_port', '8185')
            self.config.set('http', 'socket_host', '10.0.0.250')
            self.config.add_section('billdb')
            self.config.set('billdb', 'rspath', '/db/skyline/ratestructure/')
            self.config.set('billdb', 'billpath', '/db/skyline/bills/')
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
        process.Process().copy_actual_charges(
            "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
            "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

    @cherrypy.expose
    def roll(self, account, sequence, amount, **args):
        # TODO: remove this business logic to Process()
        # check to see if this bill can be rolled


        last_sequence = state.last_sequence(
            self.config.get("statedb", "host"),
            self.config.get("statedb", "db"),
            self.config.get("statedb", "user"),
            self.config.get("statedb", "password"),
            account
        )

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
        return '{success: true}'

    @cherrypy.expose
    def bindree(self, account, sequence, **args):

        from billing.processing import fetch_bill_data as fbd
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

    @cherrypy.expose
    def bindrs(self, account, sequence, **args):

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

    @cherrypy.expose
    def calcstats(self, account, sequence, **args):

        process.Process().calculate_statistics(
            "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
            "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

    @cherrypy.expose
    def sum(self, account, sequence, **args):

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
        
    @cherrypy.expose
    def issue(self, account, sequence, **args):

        # only sets the issue date

        process.Process().issue(
            "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
            "%s/%s/%s.xml" % (self.config.get("xmldb", "destination_prefix"), account, sequence),
            None,
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )


    @cherrypy.expose
    def render(self, account, sequence, **args):

        render.render(
            "%s/%s/%s.xml" % (self.config.get("xmldb", "source_prefix"), account, sequence), 
            self.config.get("billdb", "billpath")+ "%s/%s.pdf" % (account, sequence),
            "EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png",
            None,
        )

    @cherrypy.expose
    def commit(self, account, sequence, begin, end, **args):
        
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

    @cherrypy.expose
    def issueToCustomer(self, account, sequence, **args):

        state.issue(
            self.config.get("statedb", "host"),
            self.config.get("statedb", "db"),
            self.config.get("statedb", "user"),
            self.config.get("statedb", "password"),
            account,
            sequence
        )


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

