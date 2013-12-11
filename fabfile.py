#!/usr/bin/env python

import fabric.api as fabapi
import deploy.fab_common as common
from fabric.api import task as fabtask
from fabric.api import execute
from fabric.tasks import Task
from fabric.api import runs_once
from fabric.api import roles
from fabric.api import hosts
import os
import pprint
pp = pprint.PrettyPrinter(indent=2)

#
# Add ssh keys and role to host mappings for the Fabric runtime that are specific to this app
# Otherwise, depend on defaults found in deploy/fab_common.py
#
#fabapi.env.key_filename.append(
    # for example, but is in fab_common.py
    #'skyline-internal-prod': ['ec2-user@skyline-internal-prod'],
#)

#
# Define 'roles' specific to this app which are
# specified on the fab command line using '-R [rolename]'
# Otherwise, depend on defaults found in deploy/fab_common.py
# which may also be specified on the command line
#
#fabapi.env.roledefs.update({
    # for example, but is in fab_common.py
    #'skyline-internal-stage': ['ec2-user@skyline-internal-stage'],
#})

#
# Add configuration information about the hosts and deployment configurations specific to this app
#

# TODO Test this and pick the proxied host name or skyline-internal-prod - which one works?
common.CommonFabTask.update_host_os_configs({
    # for example, but this is in fab_common.py
    # this is an ssh proxy expansion of skyline-internal-stage from ~/.ssh/config
    #"10.0.1.218": {"httpd":"httpd"},
})

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
        "config_files": {
            "conf/reebill-dev-template.cfg":"/var/local/reebill-dev/billing/reebill.cfg",
        },
    },
})
common.CommonFabTask.set_default_deployment_config_key("dev")

# TODO mandate a conf file nameing scheme so that they can be deployed all in a consistent manner (below probably works)
#@fabtask(task_class=common.InstallConfig, config_name='wsgi', config_file='conf/reebill-dev-template.cfg', alias='installwsgiconfig')
#def install_config(task_instance):
#    pass

# various examples of using Tasks and overriding stuff in common

# subclass stuff from common

class MyPackageTask(common.Package):
    """
    Example of how to subclass.
    """
    # override a variable defined in super class that will only be use by this class
    package_name_spec = "%s----%s"

    # override global configuration here by modifying class variables that will be used by super
    # beware, all common.Packages get this the moment this class is parsed!
    common.Package.exclude_caches_opt = False

class MyArgPackage(common.Package):
    # note myArg being passed into __init__ by way of specifying it in @fabtask
    # This value is then assigned to an instance variable
    # And, in the override of run(), it is passed into the fabfile functions
    # An example of passing an arg into the custom task
    def __init__(self, func, myArg, *args, **kwargs):
        super(MyArgPackage, self).__init__(func, *args, **kwargs)
        self.myArg = myArg

    def run(self, *args, **kwargs):
        print "MyArgPackage Task run()", dir()
        # could pass self into func() so that the fabfile can have at the fabtask instance
        return self.func(self.myArg, *args, **kwargs)

@fabtask(task_class=MyPackageTask, pkg_name='foo', tar_dirs=['.'], alias='test_mypkg')
def test_package_project(task_instance):
    print fabapi.env[MyPackageTask.fkey]
    pass

@fabtask(task_class=MyPackageTask, pkg_name='bar', tar_dirs=['c', 'd'], alias='test_pkgframework')
def test_package_framework(task_instance):
    print fabapi.env[MyPackageTask.fkey]
    pass

@fabtask(task_class=MyArgPackage, pkg_name='baz', tar_dirs=['e', 'f'], myArg="foobar", alias='argpkg')
def arg_package_project(task_instance, arg):
    print "arg is ", arg
    print fabapi.env
    pass

