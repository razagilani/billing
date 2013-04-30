# from Celery example code; see PEP 238
# http://docs.python.org/release/2.5/whatsnew/pep-328.html
from __future__ import absolute_import
import celery
from celery import Celery, Task
from datetime import datetime

# a test
@celery.task
def log_current_date():
    with open('/tmp/thedate', 'w') as f:
        f.write(str(datetime.utcnow())+'\n')

@celery.task
def render_reebill_image(bill_upload, account, sequence, resolution):
    result = bill_upload.getReeBillImagePath(account, sequence, resolution)
    return result

## example of a class-style task definition
#class RenderReeBillImage(Task):
    #def __init__(self, bill_upload):
        #super(RenderReeBillImage, self).__init__()
        #self.bill_upload = bill_upload

    #def run(self, account, sequence, resolution):
        #result = self.bill_upload.getReeBillImagePath(account, sequence, resolution)
        #return result
