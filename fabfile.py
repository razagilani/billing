#!/usr/bin/env python

import deploy.fab_common as common
from fabric.api import task as fabtask
from fabric.api import env
from fabric.api import execute
import getpass
import fabric.operations as fabops
import os

from core import init_config, get_db_params

# Target deployment roles, each role can contain 1 or more hosts,
# each host will have the same commands from Fabric run on them.
env.roledefs.update({
    'billing-prod': ['billing-prod'],
    'billing-stage': ['billing-stage'],
    'billing-dev': ['billing-dev'],
    'billingworker-dev': ['billingworker1-dev'],
    'billingworker-stage': ['billingworker1-stage', 'billingworker2-stage'],
})

# Target environments, each environment specifies where code is deployed, the os user, config files, and more.
# Each environment should have all the key specified in the example fabfile (deploy/fabfile_example.py)
common.deployment_params['configs'] = {
    "dev": {
        "deploy_version":"4", 
        "os_user":"billing", 
        "os_group":"billing",
        "deployment_dirs": {
            "app": "/var/local/billing/billing"
        },
        # ("relative/path/to/local/file", "full/path/to/remote/file")
        "config_files": [
            ("conf/configs/settings-dev-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-dev.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-dev.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "services":[
            'billing-dev-exchange',
            'billentry-dev-exchange'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "extraction-worker-dev": {
        "deploy_version":"4", 
        "os_user":"billing", 
        "os_group":"billing",
        "deployment_dirs": {
            "app": "/var/local/billing/billing"
        },
        "config_files": [
            ("conf/configs/settings-dev-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-dev.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-dev.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "services":[
            'billing-worker'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "extraction-worker-stage": {
        "deploy_version":"4", 
        "os_user":"billing", 
        "os_group":"billing",
        "deployment_dirs": {
            "app": "/var/local/billing/billing"
        },
        "config_files": [
            ("conf/configs/settings-stage-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-stage.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-stage.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "services":[
            'billing-stage-worker'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "stage": {
        "deploy_version":"4", 
        "os_user":"billing", 
        "os_group":"billing",
        "deployment_dirs": {
            "app": "/var/local/billing/billing"
        },
        "config_files": [
            ("conf/configs/settings-stage-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-stage.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-stage.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "services":[
            'billing-stage-exchange',
            'billentry-stage-exchange'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "prod": {
        "deploy_version":"4", 
        "os_user":"billing", 
        "os_group":"billing",
        "deployment_dirs": {
            "app": "/var/local/billing/billing"
        },
        "config_files": [
            ("conf/configs/settings-prod-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-prod.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-prod.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "services":[
            'billing-prod-exchange',
            'billentry-prod-exchange'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
}

@fabtask
def create_pgpass_file():
    execute(common.prompt_config)
    env_cfg = common.deployment_params['configs'][common.deployment_params['selected_env']]
    env_name = common.deployment_params['selected_env']
    config_path = os.path.join('conf','configs','settings-%s-template.cfg' % env_name)
    
    init_config(filepath=config_path, fp=None)
    from core import config
    params = get_db_params()
    params.setdefault('port', '*')

    print("Enter Postgres Superuser password:")
    superuser_pass = getpass.getpass()

    path = os.path.join('/home',env_cfg['os_user'], '.pgpass')
    params['path'] = path
    params['superusername'] = config.get('db', 'superuser_name')
    params['superuserpass'] = superuser_pass

    fabops.sudo("echo %(host)s:%(port)s:*:%(user)s:%(password)s > %(path)s" % params, user=env_cfg["os_user"])
    fabops.sudo("echo %(host)s:%(port)s:*:%(superusername)s:%(superuserpass)s >> %(path)s" % params, user=env_cfg["os_user"])
    fabops.sudo("chmod 600 %(path)s" % params, user=env_cfg["os_user"])
