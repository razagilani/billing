#!/usr/bin/python

import fabric.api as fabapi
import fabric.utils as fabutils
import fabric.operations as fabops
import fabric.context_managers as fabcontext
import fabric.contrib as fabcontrib
from fabric.colors import red, green
import os

fabapi.env.hosts = ['tyrell']
root_dir = os.path.dirname(os.path.abspath(__file__))
exclude_from = 'fabexcludes.txt'

configurations = {
    "dev": ["reebill-dev", "reebill-dev", "reebill-dev", "reebill-dev-template.cfg"],
    "stage": ["reebill-stage", "reebill-stage", "reebill-stage", "reebill-stage-template.cfg"],
    "prod": ["reebill-prod", "reebill-prod", "reebill-prod", "reebill-prod-template.cfg"]
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
    fabops.local('tar czvf /tmp/bill_framework_code.tar.z ../*.py ../processing/*.py')

    # try and put back sane values since the software was likely deployed from a development environment
    fabops.local("sed -i 's/SKYLINE_VERSIONINFO=\".*\".*$/SKYLINE_VERSIONINFO=\"UNSPECIFIED\"/g' ui/billedit.js")
    fabops.local("sed -i 's/SKYLINE_DEPLOYENV=\".*\".*$/SKYLINE_DEPLOYENV=\"UNSPECIFIED\"/g' ui/billedit.js")

def deploy():

    environment = fabops.prompt("Environment?", default="stage")
    if environment == "prod":
        clobber = fabops.prompt(red("Clobber production?"), default="No")
        if clobber.lower() != "yes":
            fabutils.abort(green("Not clobbering production"))

    if environment not in configurations:
        fabutils.abort(red("No such configuration"))

    project = configurations[environment][0]
    user = configurations[environment][1]
    group = configurations[environment][2]
    config_file = configurations[environment][3]
            
    prepare_deploy(project, environment)
    if  fabcontrib.files.exists("/tmp/%s_deploy" % (project), use_sudo=True) is False:
        print green("Creating directory /tmp/%s_deploy" % (project))
        fabops.run('mkdir /tmp/%s_deploy/' % (project)) 
    fabapi.put('/tmp/%s.tar.z' % (project), '/tmp/%s_deploy' % (project))
    fabapi.put('/tmp/skyliner.tar.z', '/tmp/%s_deploy' % (project))
    fabapi.put('/tmp/bill_framework_code.tar.z', '/tmp/%s_deploy' % (project))

    # making billing module if missing
    if  fabcontrib.files.exists("/var/local/%s/lib/python2.6/site-packages/billing" % (project), use_sudo=True) is False:
        print green("Creating directory /var/local/%s/lib/python2.6/site-packages/billing" % (project))
        fabops.sudo('mkdir /var/local/%s/lib/python2.6/site-packages/billing' % (project)) 

    #  install ui and application code into site-packages
    with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/lib/python2.6/site-packages/billing' % (project)):
            fabops.sudo('tar xvzf /tmp/%s_deploy/%s.tar.z' % (project, project), user='root')
   
    with (fabcontext.settings(warn_only=True)):
        #with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/lib/python2.6/site-packages/billing/reebill' % (project)):
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

    # install other billing code into site-packages
    with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/lib/python2.6/site-packages/billing/' % (project)):
            fabops.sudo('tar xvzf /tmp/%s_deploy/bill_framework_code.tar.z' % (project), user='root')

    #  install skyline framework into site-packages
    with fabcontext.hide('stdout'):
        with fabcontext.cd('/var/local/%s/lib/python2.6/site-packages/' % (project)):
            fabops.sudo('tar xvzf /tmp/%s_deploy/skyliner.tar.z' % (project), user='root')

    fabops.sudo('chown -R %s:%s /var/local/%s' % (user, group, project), user='root')
    fabops.sudo('service apache2 restart')
