#!/bin/sh
# combined deployment script for billing and xbill.
set -e

if [ $# -ne 1 ]; then
    echo "1 argument required"
    exit 1
fi

# should be "dev", "stage", or "prod"
env=$1

##############################################################################
# billing deployment

for hosttype in "$env" "extraction-worker-$env"; do
    echo $hosttype | fab common.configure_app_env -R "billing-$env"
    echo $hosttype | fab common.deploy_interactive_console -R "billing-$env"
    echo $hosttype | fab common.install_requirements_files -R "billing-$env"
    echo $hosttype | fab create_pgpass_file -R "billing-$env"
    # type in superuser password at the prompt
    echo $hosttype | fab common.stop_upstart_services -R "billing-$env"
done


##############################################################################
# xbill deployment

cd xbill
echo $env | fab common.configure_app_env -R "portal-$env"
echo $env | fab common.deploy_interactive_console -R "portal-$env"

# ############################################################################
# steps that have to be run manually

# run database upgrade script if there is one
#ssh billing-$env
#sudo su - billing
#cd /var/local/billing/billing/
#python scripts/upgrade_cli.py [version number]
#logout
#logout

# can't execute this part through bash:
# reload web server (not done by fabric)
#ssh billing-$env
#sudo service httpd reload
#logout

# restart services above
#for hosttype in "$env" "extraction-worker-$env"; do
    #echo $hosttype | fab common.start_upstart_services -R "billing-$env"
#done


# xbill requirements installation
#ssh portal-[env]
#sudo su - xbill-[env]
##find /var/local/xbill-dev -name '*requirements.txt' | xargs pip install -r
## not sure how to use find and xargs properly but this does it:
#cd /var/local/xbill-dev/xbill && for f in `find . -name '*requirements.txt'`; do pip install -r $f; done
#logout
#sudo service httpd restart

