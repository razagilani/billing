#!/bin/bash
# combined deployment script for billing and xbill.
set -e
set -v

if [ $# -lt 1 -o $# -gt 2 ]; then
    echo "1 or 2 arguments required"
    exit 1
fi

# should be "dev", "stage", or "prod"
env="$1"

# version number used for selecting database upgrade script to run (optional)
version="$2"

# used for deleting temporary files
all_hosts="billing-$env billingworker1-$env billingworker2-$env portal-$env"

function delete_temp_files {
    # delete temporary files created and not deleted by previous deployments,
    # to avoid filling up the disk
    for host in $all_hosts; do
        ssh -t $host "sudo rm -rf /tmp/tmp*"
    done
}


##############################################################################
# billing deployment

# each of the fabric commands has an "environment name" argument and a "host
# type" argument. these names aren't really accurate but they determine which
# host is used, which Puppet manifest is applied, and the values of certain
# variables used in Puppet scripts to do things differently on different hosts.
params=()
params[1]="billing-$env $env"
params[2]="worker-$env worker-$env"

## clone private repositories for dependencies inside the billing repository working
## directory, because remote hosts don't have access to Bitbucket
## (for now, there is only one)
#rm -rf postal
#git clone ssh://git@bitbucket.org/skylineitops/postal.git


# fix problem with old packaves in ReeBill virtualenv by deleting
# existing files. if we could do this for all hosts we would.
ssh -t billing-$env "sudo rm -rf /var/local/*"

# main deployment steps
delete_temp_files
for param in "${params[@]}"; do
    # split "params" into 2 parts
    hosttype=$(echo $param | cut -f1 -d' ')
    envname=$(echo $param | cut -f2 -d' ')

    echo $envname | fab common.configure_app_env -R $hosttype
    echo $envname | fab common.deploy_interactive_console -R $hosttype
    echo $envname | fab common.install_requirements_files -R $hosttype
    # this doesn't work:
    #echo printf "$envname\n$postgres_pw" | fab create_pgpass_file -R $hosttype
    # so type in Postgres database superuser password at the prompt
    echo $envname | fab create_pgpass_file -R $hosttype
    echo $envname | fab common.stop_upstart_services -R $hosttype
done
delete_temp_files

# ReeBill doesn't work unless the right version of MongoEngine is installed
# in the Python virtualenv and the above does not install the right version
# for no reason we can tell. this replaces the version installed above with
# the right one.
ssh -t billing-$env "sudo -u billing -i /bin/bash -c \"source /var/local/billing/bin/activate && pip uninstall mongoengine && pip install https://github.com/MongoEngine/mongoengine/archive/d77b13efcb9f096bd20f9116cebedeae8d83749f.zip\""

# clean up dependency repositories cloned in local working directory
rm -rf postal

# run database upgrade script if there is one
# (this could be done from any host)
if [[ ! -z $version ]]; then
    ssh -t billing-$env "sudo -u billing -i /bin/bash -c \"source /var/local/billing/bin/activate && cd /var/local/billing/billing/ && python scripts/upgrade_cli.py $version\""
else
    echo "no version number provided: no database upgrade script was executed"
fi

# reload web server on main host (not done by fabric script)
ssh billing-$env -t "sudo service httpd reload"

# restart services above
for param in "${params[@]}"; do
    # split "params" into 2 parts
    hosttype=$(echo $param | cut -f1 -d' ')
    envname=$(echo $param | cut -f2 -d' ')

    echo $envname | fab common.start_upstart_services -R $hosttype
done


##############################################################################
# xbill deployment
XBILL_FABFILE_PATH="xbill_fabfile.py"

# delete any existing xbill-env directory, even though
# "fab common.deploy_interactive_console" is supposed to completely replace
# it, because somehow it still exists and that breaks the
# "mange.py collectstatic" step below
ssh -t portal-$env "sudo rm -rf /var/local/billing/"
echo $env | fab -f $XBILL_FABFILE_PATH common.configure_app_env -R "portal-$env"
echo $env | fab -f $XBILL_FABFILE_PATH common.deploy_interactive_console -R "portal-$env"

# xbill requirements installation
# this did not work:
#ssh -t portal-$env "sudo -u xbill-$env -i /bin/bash -c 'cd /var/local/xbill-$env/xbill && for f in \`find . -name '*requirements.txt'\`; do echo $f; pip install -r $f; done'"
# (we couldn't figure out why)
ssh -t portal-$env "sudo -u billing -i /bin/bash -c 'pip install -r /var/local/billing/billing/xbill/requirements.txt'"
ssh -t portal-$env "sudo -u billing -i /bin/bash -c 'pip install -r /var/local/billing/billing/mq/requirements.txt'"
ssh -t portal-$env "sudo -u billing -i /bin/bash -c 'pip install -r /var/local/billing/billing/mq/dev-requirements.txt'"

delete_temp_files

# create a symbolic link in xbill directory that points at billing/mq directory
ssh -t portal-$env "sudo ln -s /var/local/billing/billing/mq /var/local/billing/billing/xbill/mq"

# copy static files for Django Admin into the directory where they get served
# by Apache. this is the standard Django way of doing it.
ssh -t portal-$env "sudo -u billing -i /bin/bash -c 'python /var/local/billing/billing/xbill/manage.py collectstatic --noinput --verbosity=3'"

# restart xbill web server (not done by fabric script)
ssh -t portal-$env "sudo service httpd reload"
## httpd seems not to restart...
#sleep 3
#ssh -t portal-$env "sudo service httpd restart"

echo $env | fab -f $XBILL_FABFILE_PATH common.stop_upstart_services -R "portal-$env"
echo $env | fab -f $XBILL_FABFILE_PATH common.start_upstart_services -R "portal-$env"
