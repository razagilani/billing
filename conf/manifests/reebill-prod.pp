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
    require => Host::App_user['appuser']
}
file { '/var/local/${username} directory permission':
    path => "/var/local/${username}/",
    ensure => directory,
    mode => 755
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
