#!/usr/bin/env python

import deploy.fab_common as common
from fabric.api import task as fabtask
from fabric.api import env
from fabric.api import execute
import getpass
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
    'billingworker-dev': ['billingworker1-dev', 'billingworker2-dev'],
    'billingworker-stage': ['billingworker1-stage', 'billingworker2-stage'],
    'billing-dev': ['billing-dev'],
})

#
# Configurations that are specific to this app
#
common.CommonFabTask.update_deployment_configs({
    "dev": {
        "deploy_version":"4", 
        "app_name":"billing", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"billing", 
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/billing/billing",
            "www": "/var/local/billing/billing/www",
            "skyliner": "/var/local/billing/billing/skyliner",
            "doc": "/home/billing/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-dev-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-dev.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-dev.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-dev-exchange',
            'billentry-dev-exchange'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "extraction-worker-dev": {
        "deploy_version":"3", 
        "app_name":"extraction-worker-dev", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"billing", 
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/billing/billing",
            "www": "/var/local/billing/billing/www",
            "skyliner": "/var/local/billing/billing/skyliner",
            "doc": "/home/billing/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-dev-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-dev.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-dev.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-dev-worker'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "extraction-worker-stage": {
        "deploy_version":"4", 
        "app_name":"extraction-worker-stage", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"billing", 
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/billing/billing",
            "www": "/var/local/billing/billing/www",
            "skyliner": "/var/local/billing/billing/skyliner",
            "doc": "/home/billing/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-stage-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-stage.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-stage.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-stage-worker'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "stage": {
        "deploy_version":"4", 
        "app_name":"billing", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"billing", 
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/billing/billing",
            "www": "/var/local/billing/billing/www",
            "skyliner": "/var/local/billing/billing/skyliner",
            "doc": "/home/billing/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-stage-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-stage.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-stage.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-stage-exchange',
            'billentry-stage-exchange'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
    },
    "prod": {
        "deploy_version":"4", 
        "app_name":"billing", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"billing", 
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/billing/billing",
            "www": "/var/local/billing/billing/www",
            "skyliner": "/var/local/billing/billing/skyliner",
            "doc": "/home/billing/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/configs/settings-prod-template.cfg", "/var/local/billing/billing/settings.cfg"),
            ("conf/configs/alembic-prod.ini", "/var/local/billing/billing/alembic.ini"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/billing/billing/skyliner/config.yaml"),
            ("mq/conf/config-template-prod.yml", "/var/local/billing/billing/mq/config.yml"),
        ],
        "makefiles":[
        ],
        "services":[
            'billing-prod-exchange',
            'billentry-prod-exchange'
        ],
        "puppet_manifest": 'conf/manifests/billing.pp'
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

        return super(CreatePgpassFile, self).run(self.func, *args, **kwargs)

@fabtask(task_class=CreatePgpassFile, alias='create_pgpass_file')
def create_pgpass_file(task_instance, *args, **kwargs):
    pass
