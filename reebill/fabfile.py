#!/usr/bin/env python

import fabric.api as fabapi
import fabric.utils as fabutils
import fabric.operations as fabops
import fabric.context_managers as fabcontext
import fabric.contrib as fabcontrib
from fabric.colors import red, green
import os

# these 'roles' are specified on the fab command line using '-R'
fabapi.env.roledefs = {
    'amazon':['ec2-user@skyline-internal-prod.skylineinnovations.net'],
    }

# how do keys get mapped to hosts? Works like magic.
fabapi.env.key_filename = [
    os.path.expanduser('~/Dropbox/IT/ec2keys/skyline-internal-prod.pem')
]

root_dir = os.path.dirname(os.path.abspath(__file__))
exclude_from = 'fabexcludes.txt'


# specify the name of the process serving web requests
# configurations that are global to a host
host_configurations = {
    "tyrell": {"httpd":"apache2"},
    "skyline-internal-prod.skylineinnovations.net": {"httpd":"httpd"}
}

# configurations that are global to an instance of the app
env_configurations = {
    "dev": {
        "project":"reebill-dev", 
        "user":"reebill-dev", 
        "group":"reebill-dev", 
        "config":"reebill-dev-template.cfg",
        "dir":"lib/python2.6/site-packages",
    },
    "stage": {
        "project":"reebill-stage", 
        "user":"reebill-stage", 
        "group":"reebill-stage",
        "config":"reebill-stage-template.cfg",
        "dir":"lib/python2.6/site-packages",
    },
    "stage27": {
        "project":"reebill-stage", 
        "user":"reebill-stage", 
        "group":"reebill-stage",
        "config":"reebill-stage-template.cfg",
        "dir":"lib/python2.7/site-packages",
    },
    "prod": {
        "project":"reebill-prod", 
        "user":"reebill-prod", 
        "group":"reebill-prod", 
        "config":"reebill-prod-template.cfg",
        "dir":"lib/python2.6/site-packages",
    },
    "prod27": {
        "project":"reebill-prod", 
        "user":"reebill-prod", 
        "group":"reebill-prod", 
        "config":"reebill-prod-template.cfg",
        "dir":"lib/python2.7/site-packages",
    },
    "dedicated": {
        "project":"reebill", 
        "user":"reebill", 
        "group":"reebill", 
        "config":"reebill-dedicated-template.cfg",
        "dir":"",
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


def mercurial_tag_version_full():
    return fabops.local("hg log -r tip --template '{latesttag}.{latesttagdistance}-{node|short}", capture=True).split()[0]

def mercurial_actual_tag():

    actual_tag = fabops.local("hg parent --template '{tags}'", capture=True)
    if actual_tag != "" and actual_tag != "tip":
        return actual_tag
    actual_tag = fabops.local("hg log -r tip --template '{latesttag}'", capture=True)
    if actual_tag == "null":
        print red("Uncommited Branch Merge?")
        sys.exit(1)
    return actual_tag
    
def upgrade_scripts_release():
    return int(fabops.local("ls -1 ../upgrade_scripts/ | sort | tail -1", capture=True).split()[0])

def mercurial_release():
    return int(mercurial_actual_tag().split()[1])

def prepare_deploy(project, environment):


    # create version information file
    max_version = upgrade_scripts_release()
    fabops.local("sed -i 's/SKYLINE_VERSIONINFO=\".*\".*$/SKYLINE_VERSIONINFO=\"'\"`date` %s `hg id` `whoami`\"'\"/g' ui/billedit.js" % max_version)
    fabops.local("sed -i 's/SKYLINE_DEPLOYENV=\".*\".*$/SKYLINE_DEPLOYENV=\"%s\"/g' ui/billedit.js" % environment)


    # TODO: use context, and suppress output of tar

    # grab skyline framework
    fabops.local('tar czvf /tmp/skyliner.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../skyliner' % (exclude_from))

    # grab the ui and application code
    fabops.local('tar czvf /tmp/%s.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../reebill ../reebill_templates' % (project, exclude_from))

    # grab other billing code
    # TODO: 40302577 don't deploy test code
    fabops.local('tar czvf /tmp/bill_framework_code.tar.z ../util ../*.py ../processing ../upgrade_scripts ../scripts ../test')

    # try and put back sane values since the software was likely deployed from a development environment
    fabops.local("sed -i 's/SKYLINE_VERSIONINFO=\".*\".*$/SKYLINE_VERSIONINFO=\"UNSPECIFIED\"/g' ui/billedit.js")
    fabops.local("sed -i 's/SKYLINE_DEPLOYENV=\".*\".*$/SKYLINE_DEPLOYENV=\"UNSPECIFIED\"/g' ui/billedit.js")

def deploy():

    mercurial = int(mercurial_release())
    upgrade_scripts = int(upgrade_scripts_release())
    print green("Mercurial Says Release is %s" % (mercurial))
    print green("Upgrade Scripts Says Release is %s" % (upgrade_scripts))

    if mercurial < upgrade_scripts:
        print red("Deploying pre-release")
    elif mercurial > upgrade_scripts:
        print red("Deploying prior release")
    else:
        print green("Deploying current release")


    environment = fabops.prompt("Environment?", default="stage27")
    if environment[0:4] == "prod":
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
    # TODO: make sure new command creates tmp dir with proper perms so multiple people can deploy
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


    # clean up remote deployment files so there are no permission collisions
    fabops.sudo('rm -rf /tmp/%s_deploy/' % (project)) 

    fabops.sudo('chown -R %s:%s /var/local/%s' % (user, group, project), user='root')
    fabops.sudo('service %s restart' % (httpd))
