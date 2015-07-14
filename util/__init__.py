import os
import errno
from core import ROOT_PATH

class FixMQ(object):
    """Context manager to avoid having to create a file inside the "mq"
    directory in order to import it.
    """
    path = os.path.join(ROOT_PATH, 'mq', 'config.yml')
    def __enter__(self):
        with open(self.path, 'w') as mq_file:
            mq_file.write('')
        import mq
        mq.init_config = lambda: {'connection_params': {}}

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.remove(self.path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
