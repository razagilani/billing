#!/usr/bin/env python
"""This script is used to run the "Billentry" app. This can be used with apache
to run as a wsgi application, or executed in development to run with the Flask
web server.
"""
from core import initialize
from billentry import application
initialize()

if __name__ == '__main__':
    application.run(debug=True)
