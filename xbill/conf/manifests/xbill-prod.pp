$username = "xbill-prod"
$app = "xbill"
$env = "prod"

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
    cluster => 'rabbit@acquisitor-prod.nextility.net'
}
rabbit_mq::vhost {'prod':
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
    source => "puppet:///modules/conf/vhosts/xbill-prod.vhost"
}

rabbit_mq::user {'altitude-prod':
    password => 'altitude-prod',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

rabbit_mq::user_permission {'altitude-prod':
    vhost => $env,
    conf  => '.*',
    write  => '.*',
    read  => '.*',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env], Rabbit_mq::User['altitude-prod']],
}

rabbit_mq::policy {'HA':
    pattern => '.*',
    vhost => $env,
    policy => '{"ha-sync-mode":"automatic", "ha-mode":"all", "federation-upstream-set":"all"}',
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server'], Rabbit_mq::Vhost[$env]]
}

rabbit_mq::upstream {'altitude-prod':
    uri => 'amqp://xbill-prod:xbill-prod@altitude-prod.nextility.net',
    vhost => $env,
    require => [Rabbit_mq::Rabbit_mq_server['rabbit_mq_server']]
}

cron { backup:
    command => "source /var/local/xbill-prod/bin/activate && cd /var/local/xbill-prod/xbill/scripts && python backup_xbill.py --limit 30 xbill_prod postgres-prod.nextility.net --access_key AKIAIBQBJBWZPQIHPQXA --secret_key 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 >> /home/xbill-prod/backup_xbill_stdout.log 2>> /home/xbill-prod/backup_xbill_stderr.log",
    user    => $username,
    hour    => 0,
    minute  => 0
}

cron { add_accounts:
    command => "source /var/local/xbill-prod/bin/activate && cd /var/local/xbill-prod/xbill/ && python manage.py add_account > /home/xbill-prod/add_account_stdout.log 2> /home/xbill-prod/add_account_stderr.log",
    user    => $username,
    minute  => '*/2'
}

cron { tandc_export:
    command => "source /var/local/xbill-prod/bin/activate && cd /var/local/xbill-prod/xbill/ && python manage.py accounts_tandc_export > /home/xbill-prod/accounts_tandc_export_stdout.log 2> /home/xbill-prod/accounts_tandc_export_stderr.log",
    user    => $username,
    minute  => 0,
    hour    => 0
}
