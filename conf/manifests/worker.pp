$username = "billing"
$app = "billing"

host::app_user {'appuser':
    app        => $app,
    env        => $env,
    username   => $username,
}

host::aws_standard_packages {'std_packages':}
include mongo::mongo_tools

package { 'postgresql93':
    ensure  => installed
}
package { 'postgresql93-devel':
    ensure  => installed
}
package { 'libevent-devel':
    ensure  => installed
}
package { 'freetds':
    ensure  => installed
}
package { 'freetds-devel':
    ensure  => installed
}
file { "/home/${username}/logs":
    ensure      => directory,
    owner       => $username,
    group       => $username,
}
file { "/etc/init/billing-worker.conf":
    ensure => file,
    content => template('conf/billing-worker.conf.erb')
}

