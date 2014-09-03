#!/usr/bin/env python
'''
Back up/restore ReeBill databases to/from S3.
TODO: needs a name that reflects what it does (not just backing up).
'''
from boto.s3.connection import S3Connection
from os.path import basename
import os
from boto.s3.key import Key
from subprocess import call, Popen, PIPE, CalledProcessError
from datetime import datetime
import argparse
import os
from billing import init_config
init_config()
from billing import config
import re
import sys
import shlex
from StringIO import StringIO
from gzip import GzipFile
import zlib

# all backups are stored with the same key name. a new version is created every
# time the database is backed up, the latest version is used automatically
# whenever the key is accessed without specifying a version.
MYSQL_BACKUP_KEY_NAME = 'reebill_mysql.gz'
MONGO_BACKUP_KEY_NAME_FORMAT = 'reebill_mongo_%s.gz'

MYSQLDUMP_COMMAND = 'mysqldump -u%(user)s -p%(password)s %(db)s'
MYSQL_COMMAND = 'mysql -u%(user)s -p%(password)s -D%(db)s'
MONGODUMP_COMMAND = 'mongodump -d %(db)s -h %(host)s -c %(collection)s -o -'
MONGORESTORE_COMMAND = ('mongorestore --drop --noIndexRestore --db %(db)s '
                        '--collection %(collection)s %(filepath)s')
MONGO_COLLECTIONS = ['users', 'journal']

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
    stderr of the subprocess is redirected to this script's stderr.
    '''
    process = Popen(shlex.split(command), stdin=PIPE, stdout=PIPE,
                    stderr=sys.stderr)
    def check_exit_status():
        status = process.wait()
        if status != 0:
            raise CalledProcessError(status, command)
    return process.stdin, process.stdout, check_exit_status

def backup_mysql(s3_key):
    command = MYSQLDUMP_COMMAND % db_params
    _, stdout, check_exit_status = run_command(command)
    write_gizpped_to_s3(stdout, s3_key, check_exit_status)

def backup_mongo_collection(collection_name, s3_key):
    # NOTE "usersdb" section is used to get mongo database parameters for
    # all collections. this is being/has been fixed; see
    # https://www.pivotaltracker.com/story/show/77254458
    command = MONGODUMP_COMMAND % dict(
            db=config.get('usersdb', 'database'),
            host=config.get('usersdb', 'host'),
            collection=collection_name)
    _, stdout, check_exit_status = run_command(command)
    write_gizpped_to_s3(stdout, s3_key, check_exit_status)

def restore_mysql(bucket):
    command = MYSQL_COMMAND % root_db_params
    stdin, _, check_exit_status = run_command(command)
    ungzip_file = UnGzipFile(stdin)

    key = bucket.get_key(MYSQL_BACKUP_KEY_NAME)
    if not key or not key.exists():
        raise ValueError('The key "%s" does not exist in the bucket "%s"' % (
                MYSQL_BACKUP_KEY_NAME, bucket.name))
    print 'restoring MySQL from %s/%s version %s (modified %s)' % (
            bucket.name, key.name, key.version_id, key.last_modified)
    key.get_contents_to_file(ungzip_file)

    # stdin pipe must be closed to make the process exit
    stdin.close()
    check_exit_status()

def restore_mongo_collection(bucket, collection_name, bson_file_path):
    '''bson_file_path: local file path to write bson to temporarily so
    mongorestore can read from it. (this is a workaround for mongorestore's
    inability to accept input from stdin; see ticket
    https://jira.mongodb.org/browse/SERVER-4345.)
    '''
    key_name = MONGO_BACKUP_KEY_NAME_FORMAT % collection_name
    key = bucket.get_key(key_name)
    if not key or not key.exists():
        raise ValueError('The key "%s" does not exist in the bucket "%s"' % (
                key_name, bucket.name))
    print ('restoring Mongo collection "%s" from %s/%s version %s '
           '(modified %s)') % (collection_name, bucket.name, key.name,
            key.version_id, key.last_modified)

    # temporarily write bson data to bson_file_path so mongorestore can read
    # it, then restore from that file
    with open(bson_file_path, 'wb') as bson_file:
        ungzip_file = UnGzipFile(bson_file)
        key.get_contents_to_file(ungzip_file)

    command = MONGORESTORE_COMMAND % dict(
            db=config.get('usersdb', 'database'),
            collection=collection_name,
            filepath=bson_file_path)
    _, _, check_exit_status = run_command(command)

    # this may not help because mongorestore seems to exit with status
    # 0 even when it has an error
    check_exit_status()

    os.remove(bson_file_path)

def scrub_dev_data():
    '''Replace some data with placeholder values for development environment.
    Obviously this should not be used in production.
    TODO: the right way to do this is to scrub the data before it even gets
    into a development environment, just in case.
    '''
    command = MYSQL_COMMAND % db_params
    stdin, _, check_exit_status = run_command(command)
    stdin.write("update customer set bill_email_recipient = 'example@example.com';")
    stdin.write("update reebill set email_recipient = 'example@example.com';")
    stdin.close()
    check_exit_status()

def parse_args():
    parser = argparse.ArgumentParser(description=("Backup script for utility "
            "bill and reebill databases. Database credentials are read from the "
            "application config file (settings.cfg)."))
    parser.add_argument(dest='command',
            choices=['backup', 'restore', 'restore-dev'], help=(
            'backup: write database dump files to the given S3 bucket. '
            'restore: restore databases from existing dump files. '
            'restore-dev: restore development database from existing dump'
            'files, with some data replaced by placeholder values. '))
    parser.add_argument("--bucket", required=True, type=str, help="S3 bucket name")
    parser.add_argument("--access-key", required=True, type=str,
            help="The S3 access key for authenticating, generated by AWS IAM")
    parser.add_argument("--secret-key", required=True, type=str,
            help="The S3 secret key for authenticating, generated by AWS IAM")
    return parser.parse_args()

if __name__ == '__main__':
    now = datetime.utcnow().isoformat()
    args = parse_args()

    conn = S3Connection(args.access_key, args.secret_key)
    bucket = conn.get_bucket(args.bucket)

    # make sure this bucket has versioning turned on; if not, it's probably
    # the wrong bucket
    versioning_status = bucket.get_versioning_status()
    if versioning_status != {'Versioning': 'Enabled'}:
        print >> sys.stderr, ("Can't use a bucket without versioning for "
                "backups. The bucket \"%s\" has versioning status: %s") % (
                bucket.name, versioning_status)
        sys.exit(1)

    if args.command == 'backup':
        backup_mysql(Key(bucket, name=MYSQL_BACKUP_KEY_NAME))
        for collection in MONGO_COLLECTIONS:
            backup_mongo_collection(collection, Key(bucket,
                    name=MONGO_BACKUP_KEY_NAME_FORMAT % collection))
    elif args.command in ('restore', 'restore-dev'):
        restore_mysql(bucket)
        for collection in MONGO_COLLECTIONS:
            # NOTE mongorestore cannot restore from a file unless its name
            # ends with ".bson".
            bson_file_path = '/tmp/reebill_mongo_%s_%s.bson' % (collection, now)
            restore_mongo_collection(bucket, collection, bson_file_path)
        if args.command == 'restore-dev':
            scrub_dev_data()
    else:
        print >> sys.stderr, 'Unknown command "%s"' % args.command
