
from billing import config
import os
from boto.s3.connection import S3Connection
from billing.processing.state import UtilBill
import hashlib, logging
from glob import glob
from processing.billupload import BillUpload

log = logging.getLogger(__name__)


def get_hash(file_name):
    with open(file_name) as f:
        m = hashlib.sha256()
        m.update(f.read())
        res = m.hexdigest()
    return res


# extensions of utility bill formats we know we can convert into an image
# (order here determines order of preference for utility bill file lookup)
UTILBILL_EXTENSIONS = ['.pdf', '.html', '.htm', '.tif', '.tiff']

def get_utilbill_file_path(utilbill, extension=None):
    '''Returns the path to the file containing the utility bill for the
    given account and dates.
    If 'extension' is given, the path to a hypothetical file is constructed
    and returned whether or not the file with that name exists.
    If 'extension' is not given, at least one bill file is assumed to exist
    and the one with the first extension found is chosen (extensions in
    'UTILBILL_EXTENSIONS' are chosen first, in order of their appearance
    there).
    An IOError will be raised if the file does not exist.'''

    # path to the bill file (in its original format):
    # [SAVE_DIRECTORY]/[account]/[begin_date]-[end_date].[extension]
    save_directory = config.get('bill', 'utilitybillpath')
    path_without_extension = os.path.join(save_directory,
            str(utilbill.customer.account), str(utilbill.id))

    if extension == None:
        # extension not provided, so look for an actual file that already
        # exists.
        # there could be multiple files with the same name but different
        # extensions. pick the one whose extension comes first in
        # UTILBILL_EXTENSIONS, if there is one. if not, it's an error
        i = 0
        for ext in UTILBILL_EXTENSIONS:
            if os.access(path_without_extension + ext, os.R_OK):
                extension = ext
                break
            i += 1
        if i == len(UTILBILL_EXTENSIONS):
            # pick the first file found with any extension that starts with
            # 'path_without_extension', if any
            choices = glob(path_without_extension + '*')
            if len(choices) > 0:
                extension = os.path.splitext(choices[0])[1]
            else:
                # no files match
                raise IOError(('Could not find a readable bill file '
                        'whose path (without extension) is "%s"') %
                        path_without_extension)

    # if extension is provided, this is the path of a file that may not
    # (yet) exist
    return path_without_extension + extension

def upload_utilbills_to_aws(session):
    """
    Uploads utilbills to AWS
    """
    bu = BillUpload.from_config()
    bucket = bu._get_amazon_bucket()
    upload_count = 0
    for utilbill in session.query(UtilBill).all():
        try:
            local_file_path = get_utilbill_file_path(utilbill)
            sha256_hexdigest = get_hash(local_file_path)
        except IOError:
            log.error('Local pdf file for utilbill id %s not found' % \
                      utilbill.id)
            continue
        log.debug('Uploading pdf for utilbill id %s file path %s hexdigest %s'
                  % (utilbill.id, local_file_path, sha256_hexdigest))
        upload_count += 1
        log.debug('upload count: %s' % upload_count)
        full_key_name = os.path.join('utilbill', sha256_hexdigest)
        key = bucket.new_key(full_key_name)
        key.set_contents_from_filename(local_file_path)
