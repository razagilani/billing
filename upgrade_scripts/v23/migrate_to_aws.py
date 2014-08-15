


from billing import config
import os
import boto
from boto.s3.connection import S3Connection
from billing.processing.state import UtilBill

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



def upload_bill_to_aws(local_filename, type, bucket):
    """
    :param filename: the path to the utilbill or reebille
    :param type: string either 'utilbill' or 'reebill'
    :param bucket: a :class:`boto.s3.bucket.Bucket`
    """
    pass


def upload_utilbills_to_aws(session):

    connection = S3Connection(config.get('access_key_id'),
                              config.get('access_key_secret'))
    bucket = connection.get_bucket('reebill-dev')


    utilbill_path = config.get('billdb', 'utilitybillpath')

    #Upload Utilbills
    #for utilbill in os.path.walk(utilbill_path)
    for utilbill in session.query(UtilBill).all():
        print utilbill.id
