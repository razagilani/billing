#!/usr/bin/env python

import deploy.fab_common as common
from fabric.api import *
#from fabric.api import serial
#from fabric.api import runs_once as fabrunonce

env.roledefs.update({
    'skyline-external-prod': ['skyline-external-prod'],
    'skyline-external-stage': ['skyline-external-stage'],
    'portal-dev': ['portal-dev'],
    'portal-stage': ['portal-stage'],
    'portal-prod': ['portal-prod'],
})

common.deployment_params['configs'] = {
    "dev": {
        "deploy_version":"4",
        "app_name":"billing", 
        "os_user":"billing", 
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/billing/billing/",
        },
        "config_files": [
            ("conf/configs/settings_shareddev.py",
             "/var/local/billing/billing/xbill/xbill/settings.py"),
            ("mq/conf/config-template-dev.yml",
             "/var/local/billing/billing/mq/config.yml")
        ],
        # If the project has no makefiles, leave this list empty
        "makefiles":[
        ],
        "puppet_manifest":"conf/manifests/xbill.pp",
        'services': [
            'xbill-dev-exchange',
        ]
    },
    "stage": {
        "deploy_version":"4",
        "app_name":"billing",
        "os_user":"billing",
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing/",
        "deployment_dirs": {
            "app": "/var/local/billing/billing/",
        },
        "config_files": [
            ("conf/configs/settings_stage.py",
             "/var/local/billing/billing/xbill/xbill/settings.py"),
            ("mq/conf/config-template-stage.yml",
             "/var/local/billing/billing/mq/config.yml")
        ],
        "makefiles":[
        ],
        "puppet_manifest":"conf/manifests/xbill.pp",
        'services': [
            'xbill-stage-exchange',
        ]
    },
    "prod": {
        "deploy_version":"4",
        "app_name":"billing",
        "os_user":"billing",
        "os_group":"billing",
        "default_deployment_dir":"/var/local/billing/billing",
        "deployment_dirs": {
            "app": "/var/local/billing/billing/",
        },
        "config_files": [
            ("conf/configs/settings_prod.py",
             "/var/local/billing/billing/xbill/xbill/settings.py"),
            ("mq/conf/config-template-prod.yml",
             "/var/local/billing/billing/mq/config.yml")
        ],
        "makefiles":[
        ],
        "puppet_manifest":"conf/manifests/xbill.pp",
        'services': [
            'xbill-prod-exchange',
        ]
    },
}
