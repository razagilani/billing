#!/usr/bin/python

#from fabric.api import run, env
import fabric.api as fabapi
import fabric.operations as fabops
import os

fabapi.env.hosts = ['tyrell']
project_name = 'billentry'
root_dir = os.path.dirname(os.path.abspath(__file__))
exclude_from = 'fabexcludes.txt'

def prepare_deploy():
    fabops.local('tar cvfz /tmp/%s.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../%s' % (project_name, exclude_from, project_name))

def deploy():
    prepare_deploy()
    fabapi.put('/tmp/%s.tar.z' % (project_name), '/tmp')
    #fabops.sudo('if [ -d /var/local/%s ]; then echo "Directory exists"; else mkdir /var/local/%s; fi' % (project_name, project_name, ), user='root')
    fabops.sudo('cd /var/local/ && tar xvzf /tmp/%s.tar.z' % (project_name, ), user='root')
    fabops.sudo('chown -R billentry:billentry /var/local/%s' % (project_name, ), user='root')

