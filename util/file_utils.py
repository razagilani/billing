'''Put filesystem-related utilities here.
'''
from errno import EEXIST
from os.path import isdir, split, sep
from os import access, F_OK, mkdir

def make_directories_if_necessary(absolute_path):
    '''Create all directories in 'absolute_path' (string) if they don't already
    exist.
    '''
    # this will probably only work on Unix because it assumes the root path is
    # the path separator character.
    if not absolute_path.startswith(sep):
        raise ValueError('Invalid path "%s": an absolute path is required' %
                         absolute_path)
    if absolute_path == sep:
        return

    incremental_paths = [absolute_path]
    path = absolute_path
    while True:
        path, dir = split(path)
        if path == sep:
            break
        incremental_paths.insert(0, path)

    for path in incremental_paths:
        try:
            mkdir(path)
        except OSError as e:
            if e.errno != EEXIST:
                raise

    assert access(absolute_path, F_OK)
    assert isdir(absolute_path)

