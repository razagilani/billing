#!/bin/bash
# combined deployment script for billing and xbill.
set -e

if [ $# -lt 1 -o $# -gt 2 ]; then
    echo "1 or 2 arguments required"
    exit 1
fi

# should be "dev", "stage", or "prod"
env="$1"
version="$2"

##############################################################################
# billing deployment

# each of the fabric commands has an "environment name" argument and a "host
# type" argument. these names aren't really accurate but they determine which
# host is used, which Puppet manifest is applied, and the values of certain
# variables used in Puppet scripts to do things differently on different hosts.
params=()
params[1]="billing-$env $env"
# temporarily disabled to allow the rest of the process to work
#params[2]="billingworker-$env extraction-worker-$env"

# clone private repositories for dependencies inside the billing repository working
# directory, because remote hosts don't have access to Bitbucket
# (for now, there is only one)
git clone ssh://git@bitbucket.org/skylineitops/postal.git

for param in "${params[@]}"; do
    # split "params" into 2 parts
    hosttype=$(echo $param | cut -f1 -d' ')
    envname=$(echo $param | cut -f2 -d' ')

    echo $envname | fab common.configure_app_env -R $hosttype
    echo $envname | fab common.deploy_interactive_console -R $hosttype
    echo $envname | fab common.install_requirements_files -R $hosttype
    echo $envname | fab create_pgpass_file -R $hosttype
    # type in Postgres datbase superuser password at the prompt
    echo $envname | fab common.stop_upstart_services -R $hosttype
done

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

cd xbill
echo $env | fab common.configure_app_env -R "portal-$env"
echo $env | fab common.deploy_interactive_console -R "portal-$env"

# xbill requirements installation
#ssh -t portal-$env "sudo -u xbill-$env -i /bin/bash -c 'cd /var/local/xbill-$env/xbill && for f in \`find . -name '*requirements.txt'\`; do pip install -r $f; done'"
ssh -t portal-$env "sudo -u xbill-$env -i /bin/bash -c 'pip install -r /var/local/xbill-$env/xbill/requirements.txt'"
ssh -t portal-$env "sudo -u xbill-$env -i /bin/bash -c 'pip install -r /var/local/xbill-$env/xbill/mq/requirements.txt'"
ssh -t portal-$env "sudo -u xbill-$env -i /bin/bash -c 'pip install -r /var/local/xbill-$env/xbill/mq/dev-requirements.txt'"

# restart xbill web server (not done by fabric script)
ssh -t portal-$env "sudo service httpd restart"
