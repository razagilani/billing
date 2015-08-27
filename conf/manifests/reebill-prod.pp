# app level
$username = "reebill-prod"
$app = "billing"
$env = "prod"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    dropbox     => 'true',
    username   => $username,
}

host::skyline_dropbox {"$env":
    env    => $env,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}
include mongo::mongo_tools
require httpd::httpd_server

package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}
package { 'mysql-devel':
    ensure  => installed
}
package { 'mysql-server':
    ensure  => installed
}
package { 'html2ps':
    ensure  => installed
}
package { 'libevent-devel':
    ensure  => installed
}
package { 'freetds':
    ensure  => installed
}
package { 'freetds-devel':
    ensure  => installed
}
file { "/var/local/${username}/www":
    ensure      => directory,
    owner       => $username,
    group       => $username,
    require => Host::App_user['appuser']
}
file { "/db-${env}":
    ensure      => directory,
    owner       => $username,
    group       => $username,
}
file { "/home/reebill-${env}/logs":
    ensure      => directory,
    owner       => $username,
    group       => $username,
}
file { "/etc/httpd/conf.d/billing-prod.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/billing-prod.conf"
}
file { "/etc/httpd/conf.d/billentry-prod.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/billentry-prod.conf"
}

file { "/etc/init/billing-${env}-exchange.conf":
ensure => file,
content => template('conf/billing-exchange.conf.erb')
}

file { "/etc/init/billentry-${env}-exchange.conf":
ensure => file,
content => template('conf/billentry-exchange.conf.erb')
}

rabbit_mq::rabbit_mq_server {'rabbit_mq_server':
    cluster => 'rabbit@portal-prod.nextility.net'
}
rabbit_mq::base_resource_configuration {$env:
    env => $env
}
cron { backup:
    command => "source /home/reebill-prod/.bash_profile && cd /var/local/reebill-prod/billing/scripts && python backup.py backup billing-prod-backup --access-key AKIAI46IGKZFBH4ILWFA --secret-key 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 > /home/reebill-prod/backup_stdout.log 2> /home/reebill-prod/backup_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
cron { run_reports:
    command => "source /home/reebill-prod/.bash_profile && cd /var/local/reebill-stage/billing/scripts &&  python run_reports.py > /home/reebill-stage/run_reports_stdout.log 2> /home/reebill-stage/run_reports_stderr.log",
    user => $username,
    hour => 3,
    minute => 0
}
cron { export_pg_data:
    command => "source /home/reebill-prod/.bash_profile && cd /var/local/reebill-prod/billing/bin && python export_pg_data_altitude.py > /home/skyline-etl-prod/Dropbox/skyline-etl/reebill_pg_utility_bills.csv  2> /home/reebill-prod/logs/export_pg_data_altitude_stderr.log",
    user => $username,
    minute => 0
}

cron { export_accounts_data:
    command => "source /home/reebill-prod/.bash_profile && cd /var/local/reebill-prod/billing/bin && python export_accounts_to_xls.py -f /home/skyline-etl-prod/Dropbox/skyline-etl/reebill_accounts_export.xls  2> /home/reebill-prod/logs/export_accounts_to_xls_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
