#!/usr/bin/python

#from fabric.api import run, env
import fabric.api as fabapi
import fabric.operations as fabops
import os

fabapi.env.hosts = ['tyrell']
project_name = 'reebill'
root_dir = os.path.dirname(os.path.abspath(__file__))
exclude_from = 'fabexcludes.txt'

def prepare_deploy():
    # grab skyline framework
    fabops.local('tar czvf /tmp/skyliner.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../../skyliner' % (exclude_from))

    # grab the ui and application code
    fabops.local('tar czvf /tmp/%s.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../%s' % (project_name, exclude_from, project_name))

    # grab other billing code
    fabops.local('tar czvf /tmp/bill_framework_code.tar.z ../nexus_util.py ../bill.py ../__init__.py ../processing/process.py ../processing/__init__.py ../processing/state.py ../processing/fetch_bill_data.py ../processing/rate_structure.py ../processing/billupload.py ../processing/db_objects.py ../mutable_named_tuple.py ../nexus_util.py ../json_util.py')

def deploy():
    prepare_deploy()
    fabapi.put('/tmp/%s.tar.z' % (project_name), '/tmp')
    fabapi.put('/tmp/skyliner.tar.z', '/tmp')
    fabapi.put('/tmp/bill_framework_code.tar.z', '/tmp')

    # making billing module if missing
    fabops.sudo('if [ -d /var/local/%s/lib/python2.6/site-packages/billing ]; then echo "Directory exists"; else mkdir /var/local/%s/lib/python2.6/site-packages/billing; fi' % (project_name, project_name)) 

    #  install ui and application code into site-packages
    fabops.sudo('cd /var/local/%s/lib/python2.6/site-packages/billing && tar xvzf /tmp/%s.tar.z' % (project_name, project_name), user='root')
    fabops.sudo('cd /var/local/%s/lib/python2.6/site-packages/billing/%s && mv bill_tool_bridge-prod.cfg bill_tool_bridge.cfg' % (project_name, project_name), user='root')

    # install other billing code into site-packages
    fabops.sudo('cd /var/local/%s/lib/python2.6/site-packages/billing/ && tar xvzf /tmp/bill_framework_code.tar.z' % (project_name), user='root')

    #  install skyline framework into site-packages
    fabops.sudo('cd /var/local/%s/lib/python2.6/site-packages/ && tar xvzf /tmp/skyliner.tar.z' % (project_name), user='root')

    fabops.sudo('chown -R billtool:billtool /var/local/%s' % (project_name), user='root')
    fabops.sudo('service apache2 restart')
