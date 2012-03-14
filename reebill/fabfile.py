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

"""
Ok, tagging for release... this is complex, so read carefully.

The idea here is that when ReeBill is ready to be 'released' a tag
must be applied to the version.  That tag must follow this convention:

"release X"  where X is an ordinal.

The tag has to be named this way, so that hg update -r [tag] can be used.
If the tag name is just "X" you are fucked.  Because that is a number and
hg update -r [tag] runs as hg update -r [rev]  and hg update -r 2 blows 
when you are somewhere around your thousandth change set.  So, please
correct me, or stfu and use "release X". :-)

"release X" is parsed in python to get the "X".

A directory called upgrade_scripts exists.
It contains subdirectories that are numbered.
These numbers match "X" in the release name tag.
The maximum number represents the latest release scripts.

So here is how this works:

As development progresses towards a release, a subdirectory of upgrade_scripts is created.
In this directory is placed scripts relevant to upgrading from the currently deployed release to the release under development.
Fab can now look at upgrade_scripts/ and find the current release under development by finding the greatest ordinal.
As fab is invoked to deploy into test and staging environments, the contents of this directory are deployed.
At some point, everyone is happy that the release is ready. At this point, the release must be made.
The release tag is applied to tip on default after development branches are merged onto default.
Development continues and changesets accumulate as another release is developed.
At any point in time, default can be updated with a prior release, and it can be deployed.
Why is this important?  Because three releases may occur, and an environment may not have been upgraded.
So, each release will have to be deployed to it.  This necessitates updating to the proper release tag and deploying.
This is done until the target environment is brought up to date.

hg log -r tip --template {latesttag} will always return the most recent tag, regardless of what is checked out.
hg parent --template {tags} will always return the tags that apply to the current version that is checked out.

These can be used to identify facts:

If 'hg parent --template {tags}' returns something like "release X" then someone has hg updated to that tag.
Otherwise, it returns nothing (or perhaps tip).
If this returns a tag, then this tag has to be set in the application version variable.

'hg log -r tip --template {latesttag}' will always return the latest tag, in the form of "release X".
 

"""

def upgrade_scripts_max_version():
    return fabops.local("ls -1 ../upgrade_scripts/ | sort | tail -1", capture=True).split()[0]

def mercurial_tag_version_full():
    return fabops.local("hg log -r tip --template '{latesttag}.{latesttagdistance}-{node|short}'").split()[0]

def mercurial_actual_tag():

    actual_tag = fabops.local("hg parent --template {tags}'").split()[0]
    print actual_tag
    if not actual_tag:
        actual_tag = fabops.local("hg log -r tip --template '{latesttag}'").split()[0]
    print actual_tag






def prepare_deploy(project, environment):

    mercurial_actual_tag()

    # create version information file
    max_version = upgrade_scripts_max_version()
    fabops.local("sed -i 's/SKYLINE_VERSIONINFO=\".*\".*$/SKYLINE_VERSIONINFO=\"'\"`date` %s `hg id` `whoami`\"'\"/g' ui/billedit.js" % max_version)
    fabops.local("sed -i 's/SKYLINE_DEPLOYENV=\".*\".*$/SKYLINE_DEPLOYENV=\"%s\"/g' ui/billedit.js" % environment)


    # TODO: use context, and suppress output of tar

    # grab skyline framework
    fabops.local('tar czvf /tmp/skyliner.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../../skyliner' % (exclude_from))

    # grab the ui and application code
    fabops.local('tar czvf /tmp/%s.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../reebill' % (project, exclude_from))

    # grab other billing code
    fabops.local('tar czvf /tmp/bill_framework_code.tar.z ../*.py ../processing/*.py ../upgrade_scripts/%s ../scripts ../db/processing/billdb.sql' % max_version)

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
