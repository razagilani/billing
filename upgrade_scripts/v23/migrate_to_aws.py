
from billing import config
import os
import boto
from boto.s3.connection import S3Connection
from billing.processing.state import UtilBill
import hashlib, logging
from processing.billupload import BillUpload

log = logging.getLogger(__name__)


def get_hash(file_name):
    with open(file_name) as f:
        m = hashlib.sha256()
        m.update(f.read())
        res = m.hexdigest()
    return res


def upload_utilbills_to_aws(session):
    """
    Uploads utilbills to AWS
    """
    connection = S3Connection(config.get('aws_s3', 'access_key_id'),
                              config.get('aws_s3', 'access_key_secret'))
    bucket = connection.get_bucket('reebill-dev')
    bu = BillUpload(config, log)
    for utilbill in session.query(UtilBill).all():
        try:
            local_file_path = bu.get_utilbill_file_path(utilbill)
            sha256_hexdigest = get_hash(local_file_path)
        except IOError:
            log.error('Local pdf file for utilbill id %s not found' % \
                      utilbill.id)
            continue
        log.debug('Uploading pdf for utilbill id %s file path %s hexdigest %s'
                  % (utilbill.id, local_file_path, sha256_hexdigest))
        full_key_name = os.path.join('utilbill', sha256_hexdigest)
        key = bucket.new_key(full_key_name)
        key.set_contents_from_filename(local_file_path)
