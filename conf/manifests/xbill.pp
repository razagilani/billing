$app = "billing/xbill"

# The $environment variable is set by fabric at run time to whatever the user specifies
# at the configure_app_env environment prompt
$env = $environment
$username = "billing"

# app level
host::app_user {'appuser':
    app         => $app,
    env         => $env,
    username    => $username,
    dropbox     => 'true',
}

host::skyline_dropbox {"$env":
    env    => $env,
}


host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}
# nobody knows why this was here
# require host::hosts_file

package { 'httpd':
    ensure  => installed,
    before  => Host::Wsgi_setup['wsgi']
}

rabbit_mq::rabbit_mq_server {'rabbit_mq_server':
    cluster => 'rabbit@acquisitor-${env}.nextility.net'
}

rabbit_mq::vhost {"${env}":
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}

# needed to compile pymssql (in billing requirements)
package { 'freetds':
    ensure  => installed
}
package { 'freetds-devel':
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
    source => "puppet:///modules/conf/vhosts/xbill-${env}.vhost"}


rabbit_mq::user {'altitude-${env}':
    password => 'altitude-${env}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

rabbit_mq::user_permission {'altitude-${env}':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env], Rabbit_mq::User['altitude-${env}']],
}

rabbit_mq::policy {'HA':
    pattern => '.*',
    vhost => $env,
    policy => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}

rabbit_mq::upstream {'altitude-${env}':
    uri => 'amqp://xbill-${env}:xbill-${env}@altitude-${env}.nextility.net',
    vhost => $env,
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

cron { add_accounts:
    command => "source /var/local/billing/bin/activate && cd /var/local/billing/billing/xbill/ && python manage.py add_account > /home/billing/add_account_stdout.log 2> /home/billing/add_account_stderr.log",
    user    => $username,
    minute  => '*/2'
}
