'''This test ensures that config files for non-development environments
(in billing/conf/configs, which get copied to billing/ during deployment)
don't become invalid as the config file schema changes. Better to
catch this before deployment than after. It only checks conformity to the
schema, so it obviously doesn't guarantee that the contents of the files are
correct.
'''
from unittest import TestCase
from glob import glob
from os.path import dirname, join, realpath

from billing import configuration as config_file_schema
from billing.util.validated_config_parser import ValidatedConfigParser


class TestValidateConfigs(TestCase):
    def setUp(self):
        root_path = dirname(dirname(realpath(__file__)))
        self.file_paths = glob(join(root_path, 'conf', 'configs', '*.cfg'))
        self.config_parser = ValidatedConfigParser(config_file_schema)

    def test_validate_configs(self):
        for path in self.file_paths:
            print path
            with open(path) as fp:
                self.config_parser.readfp(fp)

