#!/usr/bin/env python
'''
Back up/restore ReeBill databases to/from S3.
'''
from boto.s3.connection import S3Connection
from os.path import basename
import os
from boto.s3.key import Key
from subprocess import call, Popen, PIPE, CalledProcessError
from datetime import datetime
import argparse
import os
import shutil
from billing import init_config
init_config()
from billing import config
import re
import sys
import shlex
from StringIO import StringIO
from gzip import GzipFile
import zlib

# TODO set from command line argument? or from config file?
BUCKET_NAME = 'skyline-test'

MYSQLDUMP_COMMAND = 'mysqldump -u%(user)s -p%(password)s %(db)s'
MYSQL_COMMAND = 'mysql -u%(user)s -p%(password)s -D%(db)s'

MONGODUMP_COMMAND = 'mongodump -d %(db)s -h %(host)s -c %(collection)s -o -'
MONGO_COLLECTIONS = ['users', 'journal']
# TODO mongorestore

# extract MySQL connection parameters from connection string in config file
# eg mysql://root:root@localhost:3306/skyline_dev
db_uri = config.get('statedb', 'uri')
m = re.match(r'^mysql://(\w+):(\w+)+@(\w+):([0-9]+)/(\w+)$', db_uri)
db_params = dict(zip(['user', 'password', 'host', 'port', 'db'], m.groups()))

# only root can restore a MySQL database, but root's credentials are not
# stored in the config file.
# TODO: the root password should be made into an argument, or we can ignore
# this problem until we switch to Postgres.
root_db_params = dict(db_params, user='root', password='root')

# amount of data to send to S3 at one time in bytes
S3_MULTIPART_CHUNK_SIZE_BYTES = 5 * 1024**2

# amount of data to read and compress at one time in bytes
GZIP_CHUNK_SIZE_BYTES = 128 * 1024


def _write_gzipped_chunk(in_file, out_file, chunk_size):
    '''Write gzipped data from 'in_file' to 'out_file' until 'out_file'
    contains 'chunk_size' of gzipped data (or until reaching the end of
    'in_file'). Note that more than 'chunk_size' may be read from 'in_file' to
    get 'chunk_size' bytes of data after compression.
    Return True if the end of 'in_file' has been reached, False otherwise.
    '''
    out_file.seek(0)
    out_file.truncate()

    # A GzipFile wraps another file object (its 'fileobj') and implements the
    # same interface as a regular file. when you write to the GzipFile, it
    # writes a compressed version of what you wrote to its 'fileobj'.
    gzipper = GzipFile(fileobj=out_file, mode='w')

    while True:
        data = in_file.read(GZIP_CHUNK_SIZE_BYTES)
        if data == '':
            return True
        if out_file.tell() >= chunk_size:
            return False
        gzipper.write(data)

class UnGzipFile(object):
    '''File object wrapper that un-gzips data written to it--like the built-in
    'GzipFile' class, but for un-compressing data. GzipFile's "read" mode
    won't work here because boto doesn't provide a file object to read from.
    '''
    def __init__(self, fileobj):
        '''fileobj: file object to receive uncompressed data when 'write' is
        called with compressed data.
        '''
        # see http://stackoverflow.com/a/22310760
        self._decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        self._fileobj = fileobj

    def write(self, data):
        '''Decompress 'data' and write the result to 'fileobj'.
        '''
        uncompressed_data = self._decompressor.decompress(data)
        self._fileobj.write(uncompressed_data)

def write_gizpped_to_s3(in_file, s3_key, call_before_complete=lambda: None):
    '''Write the file 'in_file' to 's3_key' (boto.s3.key.Key object). A
    multipart upload is used so that 'in_file' does not have to support seeking
    (meaning it can be a file with indeterminate length, like the stdout of a
    process).

    'call_before_complete': optional callable that can raise an exception to
    cancel the upload instead of completing it. (boto's documentation suggests
    that Amazon may charge for storage of incomplete upload parts.)
    '''
    chunk_buffer = StringIO()
    multipart_upload = s3_key.bucket.initiate_multipart_upload(s3_key)

    count = 1
    done = False
    while not done:
        # write a chunk of gzipped data into 'chunk_buffer'
        done = _write_gzipped_chunk(in_file, chunk_buffer,
                S3_MULTIPART_CHUNK_SIZE_BYTES)

        # upload the contents of 'chunk_buffer' to S3
        chunk_buffer.seek(0)
        multipart_upload.upload_part_from_file(chunk_buffer, count)
        count += 1 

    try:
        call_before_complete()
    except:
        multipart_upload.cancel_upload()
        raise
    multipart_upload.complete_upload()

def run_command(command):
    '''Run 'command' (shell command string) as a subprocess. Return stdin of
    the subprocess (file), stdout of the subprocess (file), and function that
    raises a CalledProcessError if the process exited with non-0 status.
    '''
    process = Popen(shlex.split(command), stdin=PIPE, stdout=PIPE, stderr=sys.stderr)
    def check_status():
        status = process.wait()
        if status != 0:
            raise CalledProcessError('Command exited with status %s: "%s"' % (
                    status, command))
    return process.stdin, process.stdout, check_status
        
def backup_mysql(s3_key):
    command = MYSQLDUMP_COMMAND % db_params
    stdout, check_status = run_command(command)
    write_gizpped_to_s3(stdout, s3_key, check_status)

def backup_mongo_collection(collection_name, s3_key):
    # NOTE "usersdb" section is used to get mongo database parameters for
    # all collections. this is being/has been fixed; see
    # https://www.pivotaltracker.com/story/show/77254458
    command = MONGODUMP_COMMAND % dict(
            db=config.get('mongodb', 'database'),
            host=config.get('mongodb', 'host'),
            collection=collection_name)
    _, stdout, check_status = run_command(command)
    write_gizpped_to_s3(stdout, s3_key, check_status)

def restore_mysql(bucket):
    command = MYSQL_COMMAND % root_db_params
    stdin, _, check_status = run_command(command)
    ungzip_file = UnGzipFile(stdin)

    # TODO: how to figure out which key to use?
    # currently newest key with "mysql" in its name
    key = sorted((x for x in bucket.list() if x.name.find('mysql') != -1),
            key=lambda x: x.last_modified)[0]
    key.get_contents_to_file(ungzip_file)

    # stdin pipe must be closed to make the process exit
    stdin.close()
    check_status()

def parse_args():
    parser = argparse.ArgumentParser(
            description="Backup script for utility bill and reebill databases")
    parser.add_argument(dest='command', help='"backup" or "restore"')
    # TODO implement, or use built-in amazon feature that does this
    #parser.add_argument("--limit", default = 5, type=int,
            #help="The max number of backups to store before deleting the oldest")
    # TODO --access-key and --secret-key should be mandatory; how to get argparse to enforce that?
    parser.add_argument("--access-key", type=str,
            help="The S3 access key for authenticating, generated by AWS IAM")
    parser.add_argument("--secret-key", type=str,
            help="The S3 secret key for authenticating, generated by AWS IAM")
    return parser.parse_args()

if __name__ == '__main__':
    now = datetime.utcnow().isoformat()
    args = parse_args()

    conn = S3Connection(args.access_key, args.secret_key)
    bucket = conn.get_bucket(BUCKET_NAME)

    if args.command == 'backup':
        backup_mysql(Key(bucket, name='%s_reebill_mysql.gz' % now))

        for collection in MONGO_COLLECTIONS:
            backup_mongo_collection(collection,
                    Key(bucket, name='%s_reebill_mongo_%s.gz' % (now, collection)))
    elif args.command == 'restore':
        restore_mysql(bucket)
    else:
        print >> sys.stderr, 'Unknown command "%s"' % args.command
