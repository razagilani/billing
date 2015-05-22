# app level
$username = "reebill-prod"
$app = "billing"
$env = "prod"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    username   => $username,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}
require host::hosts_file

package { 'httpd':
    ensure  => installed
}
package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}
package { 'html2ps':
    ensure  => installed
}
package { 'libevent-devel':
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
    cluster => 'rabbit@ip-10-0-0-158'
}

rabbit_mq::user_permission {'guest':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]],
}

rabbit_mq::vhost {$env:
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

rabbit_mq::policy {'HA':
    pattern => '.*',
    vhost => $env,
    policy => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}
cron { run_reports:
    command => "source /var/local/reebill-stage/bin/activate && cd /var/local/reebill-stage/billing/scripts &&  python run_reports.py > /home/reebill-stage/run_reports_stdout.log 2> /home/reebill-stage/run_reports_stderr.log",
    user => $username,
    hour => 3,
    minute => 0
}
cron { export_pg_data:
    command => "source /var/local/reebill-prod/bin/activate && cd /var/local/reebill-prod/billing/bin && python export_pg_data_altitude.py > /home/skyline-etl-prod/Dropbox/skyline-etl/reebill_pg_utility_bills.csv  2> /home/reebill-prod/logs/export_pg_data_altitude_stderr.log",
    user => $username,
    hour => 0,
    minute => 0
}
cron { run_reports:
    command => "source /var/local/reebill-stage/bin/activate && cd /var/local/reebill-stage/billing/scripts &&  python run_reports.py > /home/reebill-stage/run_reports_stdout.log 2> /home/reebill-stage/run_reports_stderr.log",
    user => $username,
    hour => 3,
    minute => 0
}
