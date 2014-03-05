from subprocess import call
import os
import csv
from jinja2 import Template, Environment, FileSystemLoader
import subprocess

def slice_area(image_path, utilbill_id, regionID, x, y, width, height):
    call("convert " + "/tmp/billimages/"+image_path + " -crop {0}x{1}+{2}+{3} ".format(width, height, x, y) +
          "/tmp/slices/{0}{1}.png".format(utilbill_id, regionID), shell=True)

def create_turk_input_file(utilbill_id, regionID):
    file_path = "/tmp/slices/"+utilbill_id+str(regionID)
    f = open(file_path+".input", 'w')
    f.write("image_url\n")
    #f.write("http://reebill-localdev/slices/"+utilbill_id+str(regionID)+'.png')
    f.write("http://s3.amazonaws.com/turk-testing/"+utilbill_id+str(regionID)+'.png')
    f.close()

def create_turk_question_file(utilbill_id, regionID, region):
    TEMPLATE_FILE_NAME="billing.question"
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
        'processing', 'dla_templates', TEMPLATE_FILE_NAME)) as template_file:
        template_html = template_file.read()
        output = Template(template_html).render(question=region)

    file_path = "/tmp/slices/"+utilbill_id+str(regionID)
    f = open(file_path+".question", 'w')
    f.write(output)
    f.close()

def create_turk_hit(regionID, utilbill_id):
    subprocess.call(["/home/josh/skyline-workspace/billing/processing/load_mturk_hit.sh",
                     utilbill_id+str(regionID), utilbill_id+str(regionID)])
    
def get_turk_results(utilbill_id, regionID):
    subprocess.call(["/home/josh/skyline-workspace/billing/processing/get_mturk_results.sh", utilbill_id+str(regionID)])
    with open('/tmp/slices/{0}.results'.format(utilbill_id+str(regionID))) as response:
        csv_response = csv.DictReader(response, delimiter="\t")
        output = dict()
        for row in csv_response:
            output = row
    return output
