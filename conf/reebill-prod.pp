# app level
$username = "reebill-prod"
$app = "reebill"
$env = "prod"

deploy::app_user {'appuser':
    app        => $app,
    env        => $env,
}

deploy::aws_standard_packages {'std_packages':}
deploy::wsgi_setup {'wsgi':}

package { 'httpd':
    ensure  => installed
}
file { "/var/local/${username}/www":
    ensure      => directory,
    owner       => $username,
    group       => $username,
    require => Deploy::App_user['appuser']
}

# apache vhost setup
# full crontab?
