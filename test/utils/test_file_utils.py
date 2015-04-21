'''Tests for util/file_utils.py.
'''
from unittest import TestCase
from testfixtures import TempDirectory
from util.file_utils import make_directories_if_necessary
from os.path import sep, join
from os import access, F_OK
from errno import ENOTDIR

class FileUtilsTest(TestCase):
    def setUp(self):
        self.root_dir = TempDirectory()

    def tearDown(self):
        self.root_dir.cleanup()

    def test_make_directories_if_necessary(self):
        # directories that already exist
        make_directories_if_necessary(sep)
        make_directories_if_necessary(self.root_dir.path)

        # directories that don't already exist
        for path in [
            join(self.root_dir.path, 'a'),
            join(self.root_dir.path, 'a', 'b', 'c')
        ]:
            self.assertFalse(access(path, F_OK))
            make_directories_if_necessary(path)
            self.assertTrue(access(path, F_OK))

        # error: relative path
        with self.assertRaises(ValueError):
            make_directories_if_necessary('a/b')

        # error: parent is not a directory
        with self.assertRaises(OSError) as e:
            make_directories_if_necessary('/dev/null/x')
        self.assertEqual(ENOTDIR, e.exception.errno)

        # error: created path is not a directory
        with self.assertRaises(AssertionError):
            make_directories_if_necessary('/dev/null')


