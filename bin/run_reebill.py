#!/usr/bin/env python
"""This script is used to run the "ReeBill" app. This can be used with apache
to run as a wsgi application, or executed in development to run with the
Cherrypy web server.
"""
import sys
from os.path import join, dirname, realpath

import cherrypy
from core import initialize, ROOT_PATH
from reebill.wsgi import ReebillWSGI

# TODO: lots of duplicate code in here
# TODO: no substantive code should go in an executable script like this--move
# to reebill/wsgi.py

if __name__ == '__main__':
    initialize()

    app = ReebillWSGI.set_up()
    ui_root = join(ROOT_PATH, 'reebill', 'ui')
    cherrypy_conf = {
        '/': {
            'tools.sessions.on': True,
            'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
        },
        '/reebill/login.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "login.html")
        },
        '/reebill/index.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "index.html")
        },
        '/reebill/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': join(ui_root, "static")
        },
        '/reebills': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': app.config.get('reebill',
                                                  'reebill_file_path')
        }
    }

    cherrypy.config.update({
        'server.socket_host': app.config.get("reebill", "socket_host"),
        'server.socket_port': app.config.get("reebill", "socket_port")})
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, False)
    cherrypy.log._set_screen_handler(cherrypy.log.access_log, True,
                                     stream=sys.stdout)

    class CherryPyRoot(object):
        reebill = app
    cherrypy.quickstart(CherryPyRoot(), "/", config=cherrypy_conf)
else:
    initialize()

    # WSGI Mode
    ui_root = join(dirname(dirname(realpath(__file__))), 'reebill/ui')
    cherrypy_conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': ui_root,
            'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
        },
        '/login.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "login.html")
        },
        '/index.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "index.html")
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        },
        '/static/revision.txt': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "../../revision.txt")
        }

    }
    cherrypy.config.update({
        'environment': 'embedded',
        'tools.sessions.on': True,
        'tools.sessions.timeout': 240,
        'request.show_tracebacks': True

    })

    if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
        cherrypy.engine.start()
        atexit.register(cherrypy.engine.stop)
    application = cherrypy.Application(
        ReebillWSGI.set_up(),
        script_name=None, config=cherrypy_conf)
