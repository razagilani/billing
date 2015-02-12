"""This script should be executed to run the "Billentry" app with the Flask web server
(meant to be used in development).
"""
from core import initialize
from brokerage import billentry

if __name__ == '__main__':
    initialize()
    billentry.application.run(debug=True)