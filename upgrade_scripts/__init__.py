"""Contains scripts to be run at deployment time of new releases. 
"""

import logging

log = logging.getLogger(__name__)

class UpgradeRunner(object):
    """Runs a software version upgrade."""
    
    def __init__(self):
        pass

    def run(self):
        log.info('Running upgrade for version %s' % self.version)
        for upgrade_fnc in self.upgrades:
            log.info('Running upgrade function %s' % upgrade_fnc.__name__)
        log.info('Upgrade to version %s complete' % self.version)