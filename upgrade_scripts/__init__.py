"""Contains scripts to be run at deployment time of new releases.

This module contains a submodule for each software version upgrade. Every 
submodule should define its own `upgrade` function, which will run schema 
migration, data migration etc. for the version upgrade.
"""

import logging
from alembic.config import Config
from alembic.command import upgrade
import importlib
from alembic.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError

log = logging.getLogger(__name__)

def run_upgrade(version):
    """Upgrade to a specified version
    :param version: the version number of the upgrade
    """
    module = importlib.import_module('upgrade_scripts.v%s' % version)
    module.upgrade()

def alembic_upgrade(revision_to):
    config = Config("alembic.ini")
    upgrade(config, revision_to)

