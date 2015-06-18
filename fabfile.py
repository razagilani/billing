#!/usr/bin/env python

import deploy.fab_common as common
from fabric.api import task as fabtask
from fabric.api import env

#
# fab create_reebill_revision common.deploy_interactive -R skyline_internal_prod
#
env.roledefs.update({
    'skyline-internal-prod': ['skyline-internal-prod'],
    'skyline-internal-stage': ['skyline-internal-stage'],
    'billing-stage': ['billing-stage'],
    'billing-prod-01': ['billing-prod-01'],
    'billing-prod': ['billing-prod'],
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
    },
})
common.CommonFabTask.set_default_deployment_config_key("dev")

# TODO: 64357046 don't set the manifest file this way, pass it into the @fabtask
# TODO: 64357530 this runs before promptconfig, so there is no way to determine the deploy env targeted
class CreateReeBillRevision(common.CreateRevision):

    manifest_file = "reebill/ui/revision.txt"


@fabtask(task_class=CreateReeBillRevision, alias='create_reebill_revision')
def create_reebill_revision(task_instance, *args, **kwargs):
    pass
