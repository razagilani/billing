$username = "xbill-stage"
$app = "xbill"
$env = "stage"

# app level
host::app_user {'appuser':
    app      => $app,
    env      => $env,
    username => $username,
    dropbox  => 'true',
}

host::skyline_dropbox {"$env":
    env    => $env,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}

package { 'httpd':
    ensure  => installed,
    before  => Host::Wsgi_setup['wsgi']
}

rabbit_mq::rabbit_mq_server {'rabbit_mq_server':
    cluster => 'rabbit@acquisitor-stage.nextility.net'
}
rabbit_mq::vhost {'stage':
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}

file { "/etc/init/xbill-${env}-exchange.conf":
    ensure => file,
    content => template('conf/xbill-exchange.conf.erb')
}

rabbit_mq::user_permission {'guest':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]],
}

file { "/etc/httpd/conf.d/${username}.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/xbill-stage.vhost"
}

rabbit_mq::policy {'HA':
    pattern => '.*',
    vhost => $env,
    policy => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}

rabbit_mq::user {'altitude-stage':
    password => 'altitude-stage',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

rabbit_mq::user_permission {'altitude-stage':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env], Rabbit_mq::User['altitude-stage']],
}

rabbit_mq::upstream {'altitude-stage':
    uri => 'amqp://xbill-stage:xbill-stage@altitude-stage.nextility.net',
    vhost => $env,
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

cron { destage_from_production:
    command => "source /var/local/xbill-stage/bin/activate && cd /var/local/xbill-stage/xbill/scripts && python destage_xbill.py --DBName xbill_stage --environment prod --DBhost postgres-stage.nextility.net --access_key AKIAIBQBJBWZPQIHPQXA --secret_key 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 /home/xbill-stage/backup_xbill_stdout.log 2> /home/xbill-stage/backup_xbill_stderr.log",
    user => $username,
    hour => 1,
    minute => 0
}
