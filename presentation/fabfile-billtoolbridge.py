#!/usr/bin/python

#from fabric.api import run, env
import fabric.api as fabapi
import fabric.operations as fabops
import os

fabapi.env.hosts = ['tyrell']
project_name = 'presentation'
root_dir = os.path.dirname(os.path.abspath(__file__))
exclude_from = 'fabexcludes.txt'

def prepare_deploy():
    fabops.local('tar czvf /tmp/%s.tar.z --exclude-from=%s --exclude-caches-all --exclude-vcs ../%s' % (project_name, exclude_from, project_name))
    fabops.local('tar czvf /tmp/billing_processing.tar.z ../nexus_util.py ../bill.py ../__init__.py ../processing/process.py ../processing/__init__.py ../processing/state.py ../processing/fetch_bill_data.py ../processing/rate_structure.py')
    fabops.local('tar czvf /tmp/billing_presentation.tar.z ../presentation/__init__.py ../presentation/render.py ../presentation/images ../presentation/fonts')

def deploy():
    prepare_deploy()
    fabapi.put('/tmp/%s.tar.z' % (project_name), '/tmp')
    fabapi.put('/tmp/billing_processing.tar.z', '/tmp')
    fabapi.put('/tmp/billing_presentation.tar.z', '/tmp')
    fabops.sudo('cd /var/local/ && tar xvzf /tmp/%s.tar.z' % (project_name, ), user='root')
    fabops.sudo('if [ -d /var/local/billtool/lib/python2.6/site-packages/billing ]; then echo "Directory exists"; else mkdir /var/local/billtool/lib/python2.6/site-packages/billing; fi') 
    fabops.sudo('cd /var/local/billtool/lib/python2.6/site-packages/billing/ && tar xvzf /tmp/billing_processing.tar.z', user='root')
    fabops.sudo('cd /var/local/billtool/lib/python2.6/site-packages/billing/ && tar xvzf /tmp/billing_presentation.tar.z', user='root')
    # hack until we clean up the presentation directory
    fabops.sudo('cp -r /var/local/%s/* /var/local/billtool' % (project_name, ), user='root')
    fabops.sudo('chown -R billtool:billtool /var/local/billtool', user='root')

