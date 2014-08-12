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
    module = importlib.import_module('billing.upgrade_scripts.v%s' % version)
    module.upgrade()

def alembic_upgrade(revision_to):
    config = Config("alembic.ini")
    upgrade(config, revision_to)

# def alembic_upgrade(connection, revision, sql=False, tag=None):
#     """Upgrade to a later version."""
#     config = Config("alembic.ini")
#     script = ScriptDirectory.from_config(config)
#
#     starting_rev = None
#     if ":" in revision:
#         if not sql:
#             raise CommandError("Range revision not allowed")
#         starting_rev, revision = revision.split(':', 2)
#
#     def upgrade(rev, context):
#         return script._upgrade_revs(revision, rev)
#
#     with EnvironmentContext(
#         config,
#         script,
#         fn=upgrade,
#         as_sql=sql,
#         starting_rev=starting_rev,
#         destination_rev=revision,
#         tag=tag
#     ) as ec:
#         ec.configure(connection=connection)
#         script.run_env()