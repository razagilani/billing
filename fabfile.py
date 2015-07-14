#!/usr/bin/env python

import deploy.fab_common as common
from fabric.api import task as fabtask
from fabric.api import env
from fabric.api import execute
import fabric.operations as fabops
import os

from core import init_config, get_db_params

#
# fab create_reebill_revision common.deploy_interactive -R skyline_internal_prod
#
env.roledefs.update({
    'skyline-internal-prod': ['skyline-internal-prod'],
    'skyline-internal-stage': ['skyline-internal-stage'],
    'billing-stage': ['billing-stage'],
    'billing-prod-01': ['billing-prod-01'],
    'billing-prod': ['billing-prod'],
    'billingworker-dev': ['billingworker1-dev', 'billingworker2-dev', 'billingworker3-dev'],
    'billing-dev': ['billing-dev'],
})

#
# Configurations that are specific to this app
#
common.CommonFabTask.update_deployment_configs({
    "dev": {
        "deploy_version":"3", 
        "app_name":"reebill-dev", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"reebill-dev", 
        "os_group":"reebill-dev",
        "default_deployment_dir":"/var/local/reebill-dev/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-dev/billing",
            "www": "/var/local/reebill-dev/billing/www",
            "skyliner": "/var/local/reebill-dev/billing/skyliner",
            "doc": "/home/reebill-dev/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-dev-template.cfg", "/var/local/reebill-dev/billing/settings.cfg"),
            ("conf/configs/alembic-dev.ini", "/var/local/reebill-dev/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-dev/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-dev.yml", "/var/local/reebill-dev/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-dev-exchange',
            'billentry-dev-exchange'
        ],
    },
    "extraction-worker-dev": {
        "deploy_version":"3", 
        "app_name":"extraction-worker-dev", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"reebill-dev", 
        "os_group":"reebill-dev",
        "default_deployment_dir":"/var/local/reebill-dev/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-dev/billing",
            "www": "/var/local/reebill-dev/billing/www",
            "skyliner": "/var/local/reebill-dev/billing/skyliner",
            "doc": "/home/reebill-dev/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-dev-template.cfg", "/var/local/reebill-dev/billing/settings.cfg"),
            ("conf/configs/alembic-dev.ini", "/var/local/reebill-dev/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-dev/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-dev.yml", "/var/local/reebill-dev/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-dev-worker'
        ],
    },
    "stage": {
        "deploy_version":"3", 
        "app_name":"reebill-stage", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"reebill-stage", 
        "os_group":"reebill-stage",
        "default_deployment_dir":"/var/local/reebill-stage/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-stage/billing",
            "www": "/var/local/reebill-stage/billing/www",
            "skyliner": "/var/local/reebill-stage/billing/skyliner",
            "doc": "/home/reebill-stage/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-stage-template.cfg", "/var/local/reebill-stage/billing/settings.cfg"),
            ("conf/configs/alembic-stage.ini", "/var/local/reebill-stage/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-stage/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-stage.yml", "/var/local/reebill-stage/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-stage-exchange',
            'billentry-stage-exchange'
        ],
    },
    "prod": {
        "deploy_version":"3", 
        "app_name":"reebill-prod", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"reebill-prod", 
        "os_group":"reebill-prod",
        "default_deployment_dir":"/var/local/reebill-prod/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-prod/billing",
            "www": "/var/local/reebill-prod/billing/www",
            "skyliner": "/var/local/reebill-prod/billing/skyliner",
            "doc": "/home/reebill-prod/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-prod-template.cfg", "/var/local/reebill-prod/billing/settings.cfg"),
            ("conf/configs/alembic-prod.ini", "/var/local/reebill-prod/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-prod/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-prod.yml", "/var/local/reebill-prod/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-prod-exchange',
            'billentry-prod-exchange'
        ],
    },
})
common.CommonFabTask.set_default_deployment_config_key("dev")

class CreatePgpassFile(common.CommonFabTask):

    def run(self, *args, **kwargs):
        execute(common.prompt_config)
        env_name = common.SelectDeploymentConfig.get_deployment_config_key()
        env_cfg = common.SelectDeploymentConfig.get_deployment_config(env_name)
        config_path = os.path.join('conf','configs','settings-%s-template.cfg' % env_name)
        
        init_config(filepath=config_path, fp=None)
        params = get_db_params()
        params.setdefault('port', '*')

        path = os.path.join('/home',env_cfg['os_user'], '.pgpass')
        params['path'] = path

        print params
        fabops.sudo("echo %(host)s:%(port)s:*:%(user)s:%(password)s > %(path)s" % params, user=env_cfg["os_user"])
        fabops.sudo("chmod 600 %(path)s" % params, user=env_cfg["os_user"])

        return super(CreatePgpassFile, self).run(self.func, *args, **kwargs)

@fabtask(task_class=CreatePgpassFile, alias='create_pgpass_file')
def create_pgpass_file(task_instance, *args, **kwargs):
    pass
