
def init_test_config():
    from billing import init_config
    from os.path import realpath, join, dirname
    init_config(join(dirname(realpath(__file__)), 'tstsettings.cfg'))

