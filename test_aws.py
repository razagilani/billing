import os
import boto
from boto.s3.connection import S3Connection

connection = S3Connection('AKIAJVT5YEOCCNGKKE3Q',
                          'DFXNb7yeG3toqb9OFMs2wMwJ/76CVSyJz2ICl5Hc')

bucket = connection.get_bucket('reebill-dev')

bucket_directory = 'utilbill'

file_to_upload = 'requirements.txt'


keyname = 'somekeyname'
full_key_name = os.path.join(bucket_directory, keyname)
k = bucket.new_key(full_key_name)
k.set_contents_from_filename(file_to_upload)

print 'all done'