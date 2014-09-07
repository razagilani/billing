import os
import boto
from boto.s3.connection import S3Connection, OrdinaryCallingFormat, ProtocolIndependentOrdinaryCallingFormat
from boto.s3.key import Key

# connection = S3Connection('AKIAJVT5YEOCCNGKKE3Q',
#                           'DFXNb7yeG3toqb9OFMs2wMwJ/76CVSyJz2ICl5Hc')

#print 'calling'
# connection = S3Connection('AKIAJVT5YEOCCNGKKE3Q',
#                           'DFXNb7yeG3toqb9OFMs2wMwJ/76CVSyJz2ICl5Hc',
#                           host='127.0.0.1',
#                           port=4567)

#print 'done'
#b0 = connection.get_bucket('reebill-dev')

print 'connecting to s3'
# connection = S3Connection('AKIAIOSFODNN7EXAMPLE',
#                           'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
#                           host='localhost', port=4567)

# connection = S3Connection('',
#                           '',
#                           host='localhost', port=4567,
#                           is_secure=False,
#                           calling_format=OrdinaryCallingFormat())

connection = S3Connection('',
                          '',
                          host='localhost', port=9444,
                          is_secure=False,
                          calling_format=ProtocolIndependentOrdinaryCallingFormat())

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
k.set_contents_from_string('whee')
print 'all done'