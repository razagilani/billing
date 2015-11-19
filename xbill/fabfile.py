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
        "app_name":"xbill-dev", 
        "os_user":"xbill-dev", 
        "os_group":"xbill-dev",
        "default_deployment_dir":"/var/local/xbill-dev/xbill",
        # set up mappings between names and remote files so that a local file can be 
        # associated and deployed to the value of the name below
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/xbill-dev/xbill",
        },
        "config_files": [
            ("conf/configs/settings_shareddev.py",
             "/var/local/xbill-dev/xbill/xbill/settings.py"),
            ("mq/conf/config-template-dev.yml",
             "/var/local/xbill-dev/xbill/mq/config.yml")
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
        "app_name":"xbill-stage", 
        "os_user":"xbill-stage", 
        "os_group":"xbill-stage",
        "default_deployment_dir":"/var/local/xbill-stage/xbill",
        "deployment_dirs": {
            "app": "/var/local/xbill-stage/xbill",
        },
        "config_files": [
            ("conf/configs/settings_stage.py",
             "/var/local/xbill-stage/xbill/xbill/settings.py"),
            ("mq/conf/config-template-stage.yml",
             "/var/local/xbill-stage/xbill/mq/config.yml")
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
        "app_name":"xbill-prod", 
        "os_user":"xbill-prod", 
        "os_group":"xbill-prod",
        "default_deployment_dir":"/var/local/xbill-prod/xbill",
        "deployment_dirs": {
            "app": "/var/local/xbill-prod/xbill",
        },
        "config_files": [
            ("conf/configs/settings_prod.py",
             "/var/local/xbill-prod/xbill/xbill/settings.py"),
            ("mq/conf/config-template-prod.yml",
             "/var/local/xbill-prod/xbill/mq/config.yml")
        ],
        "makefiles":[
        ],
        "puppet_manifest":"conf/manifests/xbill.pp",
        'services': [
            'xbill-prod-exchange',
        ]
    },
}
