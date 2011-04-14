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

from billing import nexus_util as nu


# TODO rename to ProcessBridge or something
# TODO don't require UI to pass in destination.
class BillToolBridge:
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill_tool. """

    src_prefix = dest_prefix = "http://tyrell:8080/exist/rest/db/skyline/bills/"
    config = None

    def __init__(self):
        self.config = ConfigParser.RawConfigParser()
        #print os.path.dirname(os.path.realpath(__file__))
        config_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bill_tool_bridge.cfg')
        if not self.config.read(config_file_path):
            print "Creating config file"
            self.config.add_section('xmldb')
            self.config.set('xmldb', 'destination_prefix', 'http://tyrell:8080/exist/rest/db/skyline/bills/')
            self.config.set('xmldb', 'source_prefix', 'http://tyrell:8080/exist/rest/db/skyline/bills/')
            self.config.set('xmldb', 'password', '[password]')
            self.config.set('xmldb', 'user', 'prod')
            self.config.add_section('http')
            self.config.set('http', 'socket_port', '8185')
            self.config.set('http', 'socket_host', '10.0.0.250')
            self.config.add_section('rsdb')
            self.config.set('rsdb', 'path', '/db/skyline/ratestructure/')
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
    def copyactual(self, src, dest, **args):
        process.Process().copy_actual_charges(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

    @cherrypy.expose
    def roll(self, src, dest, amount, **args):
        process.Process().roll_bill(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            amount,
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

    @cherrypy.expose
    def bindree(self, src, dest, account, **args):


        print " inbind ree"

        #import FBD, then call it.  Figure out how to get the begin/end date if mandatory
        #if (options.fetch):
        #    fbd.fetch_bill_data(options.server, options.user, options.password, options.olap_id, inputbill_xml, options.begin, options.end, options.verbose)
        #    exit()

        from billing.processing import fetch_bill_data as fbd
        # TODO make args to fetch bill data optional
        fbd.fetch_bill_data(
            "http://duino-drop.appspot.com/",
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password"),
            nu.NexusUtil("nexus").olap_id(account),
            self.config.get("xmldb", "source_prefix") + src, 
            None,
            None,
            True
        )


        process.Process().bindrs(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            self.config.get("rsdb", "path"),
            False, 
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

    @cherrypy.expose
    def bindrs(self, src, dest, **args):


        # actual
        process.Process().bindrs(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            self.config.get("rsdb", "path"),
            False, 
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )


        #hypothetical
        process.Process().bindrs(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            self.config.get("rsdb", "path"),
            True, 
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

        process.Process().calculate_reperiod(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

    @cherrypy.expose
    def sum(self, src, dest, account, **args):

        # sum actual
        process.Process().sum_actual_charges(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
        )

        # sum hypothetical
        process.Process().sum_hypothetical_charges(
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
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
            self.config.get("xmldb", "source_prefix") + src, 
            self.config.get("xmldb", "destination_prefix")+dest,
            discount_rate,
            self.config.get("xmldb", "user"),
            self.config.get("xmldb", "password")
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

