#!/usr/bin/python
'''
File: bill_tool_bridge.py
Description: Allows bill tool to be invoked as a CGI
'''

# CGI support
import cherrypy

# template support
import jinja2, os

from billing.processing.bill_tool import BillTool


class BillToolBridge:
    """ A monolithic class encapsulating the behavior to:  handle an incoming http request """
    """ and invoke bill_tool. """

    src_prefix = dest_prefix = "http://billentry:8080/exist/rest/db/skyline/bills/"

    @cherrypy.expose
    def copyactual(self, src, dest, **args):
        BillTool().copy_actual_charges(self.src_prefix + src, self.dest_prefix + dest,"dev", "dev")


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
    cherrypy.config.update({ #'server.socket_host': "10.0.0.106",
                             'server.socket_port': 8181,
                             })
    cherrypy.quickstart(BillToolBridge(), "/", config = local_conf)
