#!/usr/bin/env python

import deploy.fab_common as common
from fabric.api import task as fabtask

#
# fab create_reebill_revision common.deploy_interactive -R skyline_internal_prod
#

#
# Configurations that are specific to this app
#
common.CommonFabTask.update_deployment_configs({
    "dev": {
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
            ("conf/reebill-dev-template.cfg", "/var/local/reebill-dev/billing/reebill/reebill.cfg"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-dev/billing/skyliner/config.yaml"),
        ],
    },
    "stage": {
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
            ("conf/reebill-stage-template.cfg", "/var/local/reebill-stage/billing/reebill/reebill.cfg"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-stage/billing/skyliner/config.yaml"),
        ],
    },
    "prod": {
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
            ("conf/reebill-prod-template.cfg", "/var/local/reebill-prod/billing/reebill/reebill.cfg"),
            ("skyliner/cfg_tmpl.yaml", "/var/local/reebill-prod/billing/skyliner/config.yaml"),
        ],
    },
    "demo": {
        "app_name":"reebill-demo", 
        # TODO rename os_user to app_os_user for clarity and differentiation from host_os_configs
        "os_user":"reebill-demo", 
        "os_group":"reebill-demo",
        "default_deployment_dir":"/var/local/reebill-demo/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-demo/billing",
            "www": "/var/local/reebill-demo/billing/www",
            "skyliner": "/var/local/reebill-demo/billing/skyliner",
            "doc": "/home/reebill-demo/doc",
            "mydoc": "/tmp",
        },
        "config_files": [
            ("conf/reebill-demo-template.cfg", "/var/local/reebill-demo/billing/reebill/reebill.cfg"),
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
