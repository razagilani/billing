#upgrade_cli.py
#TODO 76483490: Move this CLI outside of the /billing package.

"""Command-line interface to run a deployment upgrade script.

Use by calling ``$python upgrade_cli.py version_number``

"""

from argparse import ArgumentParser
parser = ArgumentParser(description='Deploy a software version upgrade.')
parser.add_argument('version', 
                    help='The version we are upgrading to.')
args = parser.parse_args()

from core import init_logging, init_config
init_logging()
init_config()

from upgrade_scripts import run_upgrade
run_upgrade(args.version) 
