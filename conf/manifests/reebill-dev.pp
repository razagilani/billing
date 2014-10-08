# app level
$username = "reebill-dev"
$app = "reebill"
$env = "dev"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
}

host::aws_standard_packages {'std_packages':}
host::wsgi_setup {'wsgi':}

package { 'httpd':
    ensure  => installed
}
package { 'html2ps':
    ensure  => installed
}
package { 'imageMagick':
    ensure  => installed
}
package { 'poppler-utils':
    ensure  => installed
}
package { 'libevent-dev':
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
#file { "/etc/httpd/conf.d/${username}.conf":
#    ensure => file,
#    source => "puppet:///modules/conf/vhosts/reebill-shareddev.vhost"
#}

# full crontab?
