# app level
$username = "reebill-dev"
$app = "billing"
$env = "dev"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    username   => $username,
}

host::aws_standard_packages {'std_packages':}
include mongo::mongo_tools

package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
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
file { "/home/${username}/logs":
    ensure      => directory,
    owner       => $username,
    group       => $username,
}
file { "/etc/init/billing-${env}-worker.conf":
    ensure => file,
    content => template('conf/billing-worker.conf.erb')
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

rabbit_mq::policy { 'HA':
    pattern => '.*',
    vhost   => $env,
    policy  => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}

cron { run_reports:
  command => "source /home/${username}/.bash_profile && python /var/local/${username}/billing/bin/run_reports.py > /home/${username}/run_reports_stdout.log 2> /home/${username}/run_reports_stderr.log",
  user => $username,
  hour => 3,
  minute => 0
}
cron { export_pg_data:
    command => "source /home/${username}/.bash_profile && python /var/local/${username}/billing/bin/export_pg_data_altitude.py > /home/skyline-etl-dev/Dropbox/skyline-etl/reebill_pg_utility_bills.csv  2> /home/${username}/logs/export_pg_data_altitude_stderr.log",
    user => $username,
    minute => 0
}

