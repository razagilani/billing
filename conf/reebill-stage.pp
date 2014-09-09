# app level
$username = "reebill-stage"
$app = "reebill"
$env = "stage"

deploy::app_user {'appuser':
    app        => $app,
    env        => $env,
}

deploy::aws_standard_packages {'std_packages':}
deploy::wsgi_setup {'wsgi':}

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
    require => Deploy::App_user['appuser']
}
file { "/db-${env}":
    ensure      => directory,
    owner       => $username,
    group       => $username,
}

# apache vhost setup
# full crontab?
