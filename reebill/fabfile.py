#!/usr/bin/python

import fabric.api as fabapi
import fabric.utils as fabutils
import fabric.operations as fabops
import fabric.context_managers as fabcontext
import fabric.contrib as fabcontrib
from fabric.colors import red, green
import os

#fabapi.env.hosts = ['tyrell', 'ec2-107-21-175-174.compute-1.amazonaws.com']
fabapi.env.roledefs = {'atsite': ['ec2-user@ec2-50-16-73-74.compute-1.amazonaws.com'], 'skyline': ['tyrell']}

# how do keys get mapped to hosts? Works like magic.
fabapi.env.key_filename = ['/home/randrews/Dropbox/Skyline-IT/ec2keys/reebill-atsite.pem']

root_dir = os.path.dirname(os.path.abspath(__file__))
exclude_from = 'fabexcludes.txt'


host_configurations = {
    "tyrell": {"httpd":"apache2"},
    "ec2-50-16-73-74.compute-1.amazonaws.com": {"httpd":"httpd"},
}

env_configurations = {
    "dev": {
        "project":"reebill-dev", 
        "user":"reebill-dev", 
        "group":"reebill-dev", 
        "config":"reebill-dev-template.cfg",
        "dir":"lib/python2.6/site-packages",
        "httpd":"Apache2"
    },
    "stage": {
        "project":"reebill-stage", 
        "user":"reebill-stage", 
        "group":"reebill-stage",
        "config":"reebill-stage-template.cfg",
        "dir":"lib/python2.6/site-packages",
        "httpd":"Apache2"
    },
    "prod": {
        "project":"reebill-prod", 
        "user":"reebill-prod", 
        "group":"reebill-prod", 
        "config":"reebill-prod-template.cfg",
        "dir":"lib/python2.6/site-packages",
        "httpd":"Apache2"
    },
    "dedicated": {
        "project":"reebill", 
        "user":"reebill", 
        "group":"reebill", 
        "config":"reebill-dedicated-template.cfg",
        "dir":"",
        "httpd":"httpd"
    }
}

def prepare_deploy(project, environment):


    # create version information file
    fabops.local("sed -i 's/SKYLINE_VERSIONINFO=\".*\".*$/SKYLINE_VERSIONINFO=\"'\"`date` `hg id` `whoami`\"'\"/g' ui/billedit.js")
    fabops.local("sed -i 's/SKYLINE_DEPLOYENV=\".*\".*$/SKYLINE_DEPLOYENV=\"%s\"/g' ui/billedit.js" % environment)


    # TODO: use context, and suppress output of tar

    # grab skyline framework
    fabops.local('tar czvf /tmp/skyliner.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../../skyliner' % (exclude_from))

    # grab the ui and application code
    fabops.local('tar czvf /tmp/%s.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../reebill' % (project, exclude_from))

    # grab other billing code
    fabops.local('tar czvf /tmp/bill_framework_code.tar.z ../*.py ../processing/*.py ../db_upgrade_scripts ../scripts ../db/processing/billdb.sql')

    # try and put back sane values since the software was likely deployed from a development environment
    fabops.local("sed -i 's/SKYLINE_VERSIONINFO=\".*\".*$/SKYLINE_VERSIONINFO=\"UNSPECIFIED\"/g' ui/billedit.js")
    fabops.local("sed -i 's/SKYLINE_DEPLOYENV=\".*\".*$/SKYLINE_DEPLOYENV=\"UNSPECIFIED\"/g' ui/billedit.js")

def deploy():

    environment = fabops.prompt("Environment?", default="stage")
    if environment == "prod":
        clobber = fabops.prompt(red("Clobber production?"), default="No")
        if clobber.lower() != "yes":
            fabutils.abort(green("Not clobbering production"))

    if environment not in env_configurations:
        fabutils.abort(red("No such configuration"))

    project = env_configurations[environment]["project"]
    user = env_configurations[environment]["user"]
    group = env_configurations[environment]["group"]
    config_file = env_configurations[environment]["config"]
    directory = env_configurations[environment]["dir"]
    httpd = host_configurations[fabapi.env.host]["httpd"]
            
    prepare_deploy(project, environment)
    if  fabcontrib.files.exists("/tmp/%s_deploy" % (project), use_sudo=True) is False:
        print green("Creating directory /tmp/%s_deploy" % (project))
        fabops.run('mkdir /tmp/%s_deploy/' % (project)) 
    fabapi.put('/tmp/%s.tar.z' % (project), '/tmp/%s_deploy' % (project))
    fabapi.put('/tmp/skyliner.tar.z', '/tmp/%s_deploy' % (project))
    fabapi.put('/tmp/bill_framework_code.tar.z', '/tmp/%s_deploy' % (project))

    # making billing module if missing
    if  fabcontrib.files.exists("/var/local/%s/%s/billing" % (project, directory), use_sudo=True) is False:
        print green("Creating directory /var/local/%s/%s/billing" % (project, directory))
        fabops.sudo('mkdir /var/local/%s/%s/billing' % (project, directory)) 

    #  install ui and application code into directory 
    with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/%s/billing' % (project, directory)):
            fabops.sudo('tar xvzf /tmp/%s_deploy/%s.tar.z' % (project, project), user='root')
   
    with (fabcontext.settings(warn_only=True)):
        #with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/%s/billing/reebill' % (project, directory)):
            # does the config file exist?
            exists = fabcontrib.files.exists("reebill.cfg")
            if exists is False:
                print green("Copying deployment template configuration to create new configuration file.")
                fabops.sudo('cp %s reebill.cfg' % (config_file), user='root')
            else:
                print green("Configuration file exists")
                result = fabops.sudo('diff %s reebill.cfg' % (config_file), user='root')
                if result.failed is True:
                    print red("Warning: Configuration file differs from deployment template and was not updated.")
                else:
                    print green("Deployment template configuration file being used")

    # install other billing code into directory 
    with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/%s/billing/' % (project, directory)):
            fabops.sudo('tar xvzf /tmp/%s_deploy/bill_framework_code.tar.z' % (project), user='root')

    #  install skyline framework into directory 
    with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/%s/' % (project, directory)):
            fabops.sudo('tar xvzf /tmp/%s_deploy/skyliner.tar.z' % (project), user='root')

    fabops.sudo('chown -R %s:%s /var/local/%s' % (user, group, project), user='root')
    fabops.sudo('service %s restart' % (httpd))
