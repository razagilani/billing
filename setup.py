from setuptools import setup, find_packages

install_requires = [
    # "#" symbols after some package names below cause the package to be
    # installed from a URL in "dependency_links", not PyPI. apparently it's not
    # necessary to specify a version number or "egg" name after the "#".

    'boto==2.32.1',
    'billiard==3.3.0.20', # not sure what this is but may have to do with Flask/Bill Entry'
    'aniso8601', # not sure what this is but may have to do with Flask/Bill Entry'
    'CherryPy==3.8.0',
    'Jinja2==2.6',
    'PyYAML==3.11', # upgraded from 3.10 because "mq" uses this version
    'SQLAlchemy==1.0.5',
    'alembic==0.6.5',
    'argparse==1.2.1',
    'celery==3.1.18',
    'chardet==1.1',
    'click', # argument parsing for command-line scripts
    'ecdsa==0.11', # upgraded from 0.10 to match some other dependency that also uses it
    'formencode==1.3.0a1',
    'Flask==0.10.1',
    'Flask-RESTful==0.3.1',
    'flask-admin#',
    'Flask-Login==0.2.11',
    'Flask-Bcrypt==0.6.2',
    'Flask-OAuth==0.12',
    'Flask-Principal==0.4.0',
    'Flask-KVSession==0.6.2',
    'flower==0.8.2',
    'mongoengine#',
    'kombu-sqlalchemy==1.1.0',
    'pdfminer==20140328',
    'pika==0.9.14',
    # pillow is a replacement for PIL, a dependency of reportlab that is not
    # maintained anymore. we used to install a copy of it that was available at
    # http://effbot.org/media/downloads/Imaging-1.1.7.tar.gz, but that can't be
    # compiled due to an issue described here:
    # https://stackoverflow.com/questions/20325473/error-installing-python-image-library-using-pip-on-mac-os-x-10-9
    'Pillow==2.9.0',
    'psycopg2==2.6',
    'py-bcrypt==0.4',
    'pyPdf==1.13',
    'pycrypto==2.6.1',
    'pymongo==2.7.2',
    'pymssql#',
    'python-dateutil==2.2', # upgraded from 2.1 because "mq" uses this version
    'python-statsd',
    'pytz==2013.8',
    'regex==2015.7.19',
    'requests==0.14.0',
    'simplejson==2.6.0',
    'tablib==0.10.0',
    'tsort==0.0.1',
    'wsgiref==0.1.2',
    'xkcdpass==1.2.5',
    'xlwt==0.7.4',
    'testfixtures',
    'voluptuous==0.8.6',
    'Pint==0.6',
    'reportlab==2.5',

    'postal#'

    # exclusively for "skyliner" library--move to skyliner/setup.py
    # all version numbers must be the same as previous occurrences above
    'eventlet==0.9.17',
    'gevent==0.13.8',
    'mongokit==0.9.0',
    'pymongo==2.7.2',
    'PyYAML==3.11',
    'requests==0.14.0',
    'numpy',
    'pandas',

    # exclusively for "mq"--delete when "mq" goes away.
    # all version numbers must be the same as previous occurrences above
    'pika==0.9.14',
    'python-dateutil==2.2',
    'PyYAML==3.11',
    'voluptuous==0.8.6',
]
tests_require=[
    # actually for tests
    'mock',
    'nose',
    'nose-progressive',
    'coverage',

    # general development tools
    'ipdb',

    # for deployment
    'fabric',
    'awscli', # command-line tool from Amazon for working with AWS
]

setup(
    name="billing",
    version="33",
    packages=find_packages(),
    scripts=[
        'bin/check_matrix_file.py',
        'bin/export_accounts_to_xls.py',
        'bin/export_pg_data_altitude.py',
        'bin/receive_matrix_email.py',
        'bin/run_billentry.py',
        'bin/run_billentry_amqp_consumer.py',
        'bin/run_reebill.py',
        'bin/run_reports.py',
        'bin/run_utilbill_amqp_consumer.py',
    ],
    # TODO: this can only be installed using
    # "pip install --process-dependency-links".
    # use of dependency_links seems to be deprecated or at least considered bad.
    dependency_links=[
        # Our forked repo of Flask-Admin
        'git+https://github.com/nextilityinc/flask-admin.git@3ba9b936410d97839c99604dab25ba388e19cf1d',

        # this is actually MongoEngine 0.9 from GitHub (we were previously using 0.8.4) but appears as version "8.7"
        'git+https://github.com/MongoEngine/mongoengine.git@d77b13efcb9f096bd20f9116cebedeae8d83749f',

        'git+https://github.com/klothe/pymssql.git@ba8c5f45f52ef3602a29604428dc831fab7f3af3',

        # for Bitbucket repositories,
        # replace ":" with "/" Bitbucket SSH URL, append modulename-version.
        # modulename must match the one used in install_requires.
        'git+ssh://git@bitbucket.org/skylineitops/postal.git#egg=postal-0',
    ],
    # install_requires includes test requirements. suggested by
    # https://stackoverflow.com/questions/4734292/specifying-where-to-install
    # -tests-require-dependencies-of-a-distribute-setupto
    install_requires=install_requires + tests_require,
    tests_require=tests_require,
    test_suite="nose.collector",
    entry_points={
        'console_scripts': [
            # 'acquisitor-exchange = messenger.acquisitor_exchange:main',
            # 'acquisitor = acquisitor:main',

            # TODO: probably everything in bin/ goes here.
            # but how to include things that are not python module paths
            # starting from the root directory? bin is not and shouldn't be a
            # python package.
            # this only works if bin/__init__.py exists, making "bin" a module
            'check_matrix_file = bin.check_matrix_file:main',
            'export_accounts_to_xls = export_accounts_to_xls:main',
            'export_pg_data_altitude = export_pg_data_altitude:main',
            'receive_matrix_email = receive_matrix_email:main',
            'run_billentry = run_billentry:main',
            'run_billentry_amqp_consumer = run_billentry_amqp_consumer:main',
            'run_reebill = run_reebill:main',
            'run_reports = run_reports:main',
            'run_utilbill_amqp_consumer = run_utilbill_amqp_consumer:main',
        ],
    }
)
