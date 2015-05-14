# app level
$username = "reebill-stage"
$app = "billing"
$env = "stage"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    username   => $username,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}
require host::hosts_file

include mongo::mongo_tools
package { 'httpd':
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
    cluster => 'rabbit@ip-10-0-1-220'
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

cron { destage_from_production:
    command => "source /var/local/reebill-stage/bin/activate && cd /var/local/reebill-stage/billing/scripts && python backup.py restore --scrub --root-password root billing-prod-backup --access-key AKIAJUVUCMECRLXFEUMA --secret-key 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 > /home/reebill-stage/destage_stdout.log 2> /home/reebill-stage/destage_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
cron { destage_bills_from_production:
    command => "source /var/local/reebill-stage/bin/activate && cd /var/local/reebill-stage/billing/scripts &&  python backup.py restore-files-s3 d6b434b4ac de5cd1b859 --access-key AKIAJH4OHWNBRJVKFIWQ --secret-key 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 > /home/reebill-stage/destage_bills_stdout.log 2> /home/reebill-stage/destage_bills_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
