


from billing import config
import os
import boto
from boto.s3.connection import S3Connection
from billing.processing.state import UtilBill
import hashlib, logging
from processing.billupload import BillUpload

# connection = S3Connection('AKIAJVT5YEOCCNGKKE3Q',
#                           'DFXNb7yeG3toqb9OFMs2wMwJ/76CVSyJz2ICl5Hc')
#
# bucket = connection.get_bucket('reebill-dev')
#
# bucket_directory = 'utilbill'
#
# file_to_upload = 'requirements.txt'
#
#
# keyname = 'somekeyname'
# full_key_name = os.path.join(bucket_directory, keyname)
# k = bucket.new_key(full_key_name)
# k.set_contents_from_filename(file_to_upload)
# print 'all done'



def get_hash(file_name):
    with open(file_name) as f:
        m = hashlib.sha256()
        m.update(f.read())
        res = m.hexdigest()
    return res


# def upload_utilbill_bill_to_aws(local_file_path, type, bucket):
#     """
#     :param local_file_path: the path to the utilbill or reebille
#     :param type: string either 'utilbill' or 'reebill'
#     :param bucket: a :class:`boto.s3.bucket.Bucket`
#     """
#     pass

log = logging.getLogger(__name__)

def upload_utilbills_to_aws(session):

    # connection = S3Connection(config.get('aws_s3', 'access_key_id'),
    #                           config.get('aws_s3', 'access_key_secret'))
    # bucket = connection.get_bucket('reebill-dev')
    # utilbill_path = config.get('billdb', 'utilitybillpath')

    #for utilbill in os.path.walk(utilbill_path)
    #Upload Utilbills
    bu = BillUpload(config, log)
    for utilbill in session.query(UtilBill).all():
        try:
            local_file_path = bu.get_utilbill_file_path(utilbill)
        except IOError:
            continue
        #upload_bill_to_aws(local_file_path)


