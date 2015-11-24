$username = "xbill-dev"
$app = "xbill"
$env = "dev"

# app level
host::app_user {'appuser':
    app         => $app,
    env         => $env,
    username    => $username,
    dropbox     => 'false',
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
    cluster => 'rabbit@acquisitor-dev.nextility.net'
}
rabbit_mq::vhost {'dev':
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
    source => "puppet:///modules/conf/vhosts/xbill-shareddev.vhost"
}

rabbit_mq::user {'altitude-dev':
    password => 'altitude-dev',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

rabbit_mq::user_permission {'altitude-dev':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env], Rabbit_mq::User['altitude-dev']],
}

rabbit_mq::policy {'HA':
    pattern => '.*',
    vhost => $env,
    policy => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}

rabbit_mq::upstream {'altitude-dev':
    uri => 'amqp://xbill-dev:xbill-dev@altitude-dev',
    vhost => $env,
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

