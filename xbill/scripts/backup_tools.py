from boto.s3.connection import S3Connection
from os.path import basename
import os
from boto.s3.key import Key
from subprocess import call
from datetime import datetime

def size_of_bucket(bucket):
    size = 0
    for key in bucket:
        size += 1
    return size

def upload_to_bucket(upload_file, bucket):
    k = Key(bucket)
    k.key = basename(upload_file)
    print k.key
    k.set_contents_from_filename(upload_file)
    #k.set_contents_from_file(upload_file)

def download_from_bucket(key, bucket, download_file):
    k = Key(bucket)
    k.key = key.name
    k.get_contents_to_file(download_file)

def connect_to_bucket(name, access_key, secret_key):
    conn = S3Connection(access_key, secret_key)
    bucket = conn.get_bucket(name)
    print("Using bucket: {0}".format(bucket.name))
    return bucket

def remove_backup(key_name, bucket):
    bucket.delete_key(key_name)

def get_latest_backup(bucket):
    keys = bucket.list()
    keys_list = sorted(keys, key=lambda x: x.last_modified)
    return keys_list[-1]

def remove_oldest_backup(bucket):
    keys = bucket.list()
    keys_list = sorted(keys, key=lambda x: x.last_modified)
    print("Removing {0}".format(keys_list[0].name))
    remove_backup(keys_list[0].name, bucket)

def dump_psql_to_file(database, host, user, dump_file_path):
    val = call(["pg_dump", "--clean", "-h{0}".format(host), "-U{0}".format(user), database], stdout=dump_file_path)
    if val != 0:
        raise Exception

def dump_mysql_to_file(database, host, user, password, dump_file_path):
    val = call(["mysqldump", "-u{0}".format(user), "-h{0}".format(host), "-p{0}".format(password), str(database)], stdout=dump_file_path)
    if val != 0:
        raise Exception

def dump_mongo_to_file(database, host, collection, dump_file_path):
    val = call(["mongodump", "-d{0}".format(database), "-h{0}".format(host), "-c{0}".format(collection), "-o{0}".format(dump_file_path)])
    if val != 0:
        raise Exception

def restore_psql_from_file(database, hostname, user, dump_file_path):
    val = call(["psql", "-v", "-d", "{0}".format(database), "-h",  "{0}".format(
        hostname), "-U",  "{0}".format(user), "-f", "{0}".format(dump_file_path)])
    if val != 0:
        raise Exception

def restore_mysql_from_file(database, user, password, dump_file_path):
    call(["mysql", "-u{0}".format(user), "-p{0}".format(password), '''-e "drop database if exists {0};"'''.format(database)])
    call(["mysql", "-u{0}".format(user), "-p{0}".format(password), '''-e "create database if not exists {0};"'''.format(database)])
    call(["mysql", "-u{0}".format(user), "-p{0}".format(password), "-D{0}".format(database)], stdin=dump_file_path)

def restore_mongo_from_file(database, dump_file_path):
    val = call(["mongorestore", "--drop", "-d{0}".format(database), dump_file_path])
    if val != 0:
        raise Exception

def tar_directory(path):
    val = call(["tar", "-c", "-P", "-f{0}.tar".format(path), path])
    if val != 0:
        raise Exception

def untar_directory(path):
    val = call(["tar", "-x", "-v", "-P", "-f{0}".format(path)])
    if val != 0:
        raise Exception
