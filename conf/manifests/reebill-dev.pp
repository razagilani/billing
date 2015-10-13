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
host::wsgi_setup {'wsgi':}
require httpd::httpd_server


package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}
package { 'html2ps':
    ensure  => installed
}
package { 'freetds':
    ensure  => installed
}
package { 'freetds-devel':
    ensure  => installed
}
package { 'sendmail':
    ensure => absent,
}
package { 'postfix':
    ensure => installed
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
file { "/etc/httpd/conf.d/billing-dev.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/billing-shareddev.conf"
}
file { "/etc/httpd/conf.d/billentry-dev.conf":
    ensure => file,
    source => "puppet:///modules/conf/vhosts/billentry-shareddev.conf"
}

file { "/etc/init/billing-${env}-exchange.conf":
    ensure => file,
    content => template('conf/billing-exchange.conf.erb')
}

file { "/etc/init/billentry-${env}-exchange.conf":
    ensure => file,
    content => template('conf/billentry-exchange.conf.erb')
}

file { "/etc/postfix/main.cf":
    ensure => file,
    content => template('conf/main.cf.erb'),
    mode => 644,
    owner => 'root',
    require => Package['postfix']
}
# this needs to be executed by postfix, not reebill-${env}.
# consider putting it in a different directory.
$receive_matrix_email_script = "/home/${username}/receive_matrix_email.sh"
file { $receive_matrix_email_script:
    ensure => file,
    content => template('conf/receive_matrix_email.sh'),
    mode => 755,
    owner => $username,
    require => Host::App_user['appuser']
}
# directory containg the shell script must be executable for other users,
# and virtualenv directory must also be executable to activate the virtualenv
file { "/home/${username}":
    ensure => directory,
    mode => 701,
}

# email aliases for receiving matrix quote emails
mailalias { 'matrix-aep':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-amerigreen':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-champion':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-constellation':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-directenergy':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-entrust':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-majorenergy':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-sfe':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
mailalias { 'matrix-usge':
    ensure    => present,
    recipient => "|${receive_matrix_email_script}"
}
# Puppet doesn't rebuild the mail aliases database by default
# (we could use "subscribe" and "refreshonly" but it would
# require listing every mail alias here)
exec { newaliases:
    path => ["/usr/bin", "/usr/sbin"],
    require => Package['postfix']
}

rabbit_mq::rabbit_mq_server {'rabbit_mq_server':
    # TODO: either avoid using a specific host name here or ensure that host gets created and configured along with this one
    cluster => 'rabbit@xbill-dev.nextility.net'
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
