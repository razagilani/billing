import os
from boto.s3.connection import S3Connection, OrdinaryCallingFormat, ProtocolIndependentOrdinaryCallingFormat

print 'connecting to s3'

connection = S3Connection('',
                          '',
                          host='localhost', port=4567,
                          is_secure=False,
                          calling_format=OrdinaryCallingFormat())


print 'connected'
print 'making bucket'
connection.create_bucket('reebill')
print 'made bucket'
bucket = connection.get_bucket('reebill')

print 'got bucket'

bucket_directory = 'utilbill'

file_to_upload = 'requirements.txt'


keyname = 'otherkeyname'
full_key_name = os.path.join(bucket_directory, keyname)
k = bucket.new_key(full_key_name)
#k = Key(bucket)
#k.set_contents_from_filename(file_to_upload)
#k.set_contents_from_string('whee')
#print 'all done'

print k.get_contents_as_string()