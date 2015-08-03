# app level
$username = "reebill-stage"
$app = "billing"
$env = "stage"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    dropbox     => 'true',
    username   => $username,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}
require httpd::httpd_server

host::skyline_dropbox {"$env":
    env    => $env,
}


include mongo::mongo_tools

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
file { "/etc/httpd/conf.d/billing-stage.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/billing-stage.conf"
}
file { "/etc/httpd/conf.d/billentry-stage.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/billentry-stage.conf"
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
    cluster => 'rabbit@portal-stage.nextility.net'
}
rabbit_mq::base_resource_configuration {$env:
    env => $env
}
cron { destage_from_production:
    command => "source /home/reebill-stage/.bash_profile && cd /var/local/reebill-stage/billing/scripts && python backup.py restore --scrub billing-prod-backup --access-key AKIAJUVUCMECRLXFEUMA --secret-key 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 > /home/reebill-stage/destage_stdout.log 2> /home/reebill-stage/destage_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
cron { destage_bills_from_production:
    command => "source /home/reebill-stage/.bash_profile && cd /var/local/reebill-stage/billing/scripts &&  python backup.py restore-files-s3 d6b434b4ac de5cd1b859 --access-key AKIAJH4OHWNBRJVKFIWQ --secret-key 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 > /home/reebill-stage/destage_bills_stdout.log 2> /home/reebill-stage/destage_bills_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
cron { run_reports:
    command => "source /home/reebill-stage/.bash_profile && cd /var/local/reebill-stage/billing/scripts &&  python run_reports.py > /home/reebill-stage/run_reports_stdout.log 2> /home/reebill-stage/run_reports_stderr.log",
    user => $username,
    hour => 3,
    minute => 0
}

#cron { export_pg_data:
#    command => "source /home/reebill-stage/.bash_profile && cd /var/local/reebill-stage/billing/bin && python export_pg_data_altitude.py > /home/skyline-etl-stage/Dropbox/skyline-etl/reebill_pg_utility_bills.csv  2> /home/reebill-stage/logs/export_pg_data_altitude_stderr.log",
#    user => $username,
#    hour => 0,
#    minute => 0
#}
cron { read_quote_files:
    command => "source /home/reebill-stage/.bash_profile && python /var/local/reebill-stage/billing/bin/receive_matrix_files.py",
    user => $username,
    minute => '*/10'
}
