from billing.upgrade_scripts.v21.migrate_utilbill_charges_from_mongodb import migrate_utilbill_charges_from_mongodb
from billing.upgrade_scripts import UpgradeRunner

class Upgrade(UpgradeRunner):    
    version = '21'
    upgrades = [upgrade_alembic_schema, 
                migrate_utilbill_charges_from_mongodb]
