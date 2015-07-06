from boto.s3.connection import S3Connection
from core.model import UtilBill

def check_s3_files_in_db(session):
    s3_connection = S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                 config.get('aws_s3', 'aws_secret_access_key'),
                                 is_secure=config.get('aws_s3', 'is_secure'),
                                 port=config.get('aws_s3', 'port'),
                                 host=config.get('aws_s3', 'host'),
                                 calling_format=config.get('aws_s3',
                                                           'calling_format'))
    bucket = s3_connection.get_bucket(config.get('aws_s3', 'bucket'))
    rs = bucket.list()
    for key in rs:
        index = key.name.rfind('.')
        file_hash = key.name[0: index]
        utilbills = session.query(UtilBill).filter(UtilBill.sha256_hexdigest==file_hash).all()
        if len(utilbills) != 1:
            print('file %s with key %s has %s utilbills' %(key.name, file_hash, len(utilbills)) )

if __name__ == '__main__':
    # for checking that al files from S3 were processed correctly in production
    # this should be run after upgrade_scripts are run in production for billing release 23
    from core import init_config, init_model, init_logging
    init_config()
    init_model()
    init_logging()
    from core import config
    from core.model import Session
    session = Session()
    check_s3_files_in_db(session)
