import os
from boto.s3.connection import S3Connection, OrdinaryCallingFormat

print 'connecting to s3'

# connection = S3Connection('',
#                           '',
#                           host='localhost', port=4567,
#                           is_secure=False,
#                           calling_format=OrdinaryCallingFormat())

from billing import init_logging, init_config
init_logging()
init_config()
from billing import config

connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                          config.get('aws_s3', 'aws_secret_access_key'),
                          is_secure=config.get('aws_s3', 'is_secure'),
                          port=config.get('aws_s3', 'port'),
                          host=config.get('aws_s3', 'host'),
                          calling_format=config.get('aws_s3',
                                                    'calling_format'))

print 'connected'
print 'making bucket'

connection.create_bucket('reebill-dev')
connection.create_bucket('reebill-dev')
connection.create_bucket('reebill-dev')

print 'made bucket'
bucket = connection.get_bucket('reebill-dev')

print 'got bucket'
#exit()

bucket_directory = 'utilbill'

file_to_upload = 'requirements.txt'


keyname = 'otherkeyname2'
full_key_name = os.path.join(bucket_directory, keyname)
k = bucket.new_key(full_key_name)
#k = Key(bucket)
k.set_contents_from_filename(file_to_upload)
#k.set_contents_from_string('whee')
#print 'all done'

print k.get_contents_as_string()