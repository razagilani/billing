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


# these 'roles' are specified on the fab command line using '-R [rolename]'
common.CommonFabTask.update_fabenv_roles({
    'skyline': ['ec2-user@skyline-internal-prod.skylineinnovations.net'],
    'foo': ['bar', 'baz']
})


# keyed to hosts in roledefs, these are the host OS level
# configurations that need to be treated
#common.host_configs.update({
#    "tyrell": {"httpd":"apache2"},
#    "ec2-50-16-73-74.compute-1.amazonaws.com": {"httpd":"httpd"},
#    "ec2-23-21-137-54.compute-1.amazonaws.com": {"httpd":"httpd"},
#})

# configurations that are global to an instance of the app
# TODO: project should be from proj_configs because it is the name of the project, not the path to the project on the remote host
common.CommonFabTask.update_deployment_configs({
    "dev": {
        "app_name":"reebill-dev", 
        "os_user":"reebill-dev", 
        "os_group":"reebill-dev",
        "config":"reebill-dev-template.cfg",
        "config_files": {
            "reebill-dev-template.cfg",
        },
        "default_deployment_dir":"/var/local/reebill-dev/billing",
        "deployment_dirs": {
            # package name:destination path
            # package names are specified in tasks wrapper decorators
            "app": "/var/local/reebill-dev/billing",
            "www": "/var/local/reebill-dev/billing/www",
            "skyliner": "/var/local/reebill-dev/billing/skyliner",
            "doc": "/home/reebill-dev/doc",
            "mydoc": "/tmp",
        },
    },
    "stage": {
        "app_name":"reebill-stage", 
        "os_user":"reebill-stage", 
        "os_group":"reebill-stage",
        "config":"reebill-stage-template.cfg",
        "dir":"lib/python2.6/site-packages",
    },
    "stage27": {
        "app_name":"reebill-stage", 
        "os_user":"reebill-stage", 
        "os_group":"reebill-stage",
        "config":"reebill-stage-template.cfg",
        "dir":"lib/python2.7/site-packages",
    },
    "prod": {
        "app_name":"reebill-prod", 
        "os_user":"reebill-prod", 
        "os_group":"reebill-prod", 
        "config":"reebill-prod-template.cfg",
        "dir":"lib/python2.6/site-packages",
    },
    "prod27": {
        "app_name":"reebill-prod", 
        "os_user":"reebill-prod", 
        "os_group":"reebill-prod", 
        "config":"reebill-prod-template.cfg",
        "dir":"lib/python2.7/site-packages",
    },
    "dedicated": {
        "app_name":"reebill", 
        "os_user":"reebill", 
        "os_group":"reebill", 
        "config":"reebill-dedicated-template.cfg",
        "dir":"",
    }
})
common.CommonFabTask.set_deployment_config_key("dev")


# various examples of using Tasks and overriding stuff in common

# use a task class from common, but pass in arguments that we prefer.  Here, we change pkg_name
@fabtask(task_class=common.Package, pkg_name='mydoc', tar_dirs=['wiki'], alias='pkg_doc')
def package_doc(task_instance):
    pass


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

