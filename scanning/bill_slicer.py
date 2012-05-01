#!/usr/bin/python
import cherrypy
import os
from PIL import Image
import subprocess
import json

class BillSlicer:
    def __init__(self):
        self.mytest = "foo" + str(self.index.exposed)

    @cherrypy.expose
    def index(self):
        return open(u"index.html")

    @cherrypy.expose
    def crop(self, imgId, ulX, ulY, lrX, lrY):
        im = Image.open(os.path.join("static","workingimages","test0.png"))
        # PIL doc: The region is defined by a 4-tuple, where coordinates are (left, upper, right, lower)
        # x0, y0, x1, y1
        cim = im.crop((int(ulX), int(ulY), int(lrX), int(lrY)))

        cimFileName = os.path.join("static", "workingimages", imgId)
        cim.save(cimFileName)
        cimFileName  = cimFileName + ".tif"
        cim.save(cimFileName)
        # ToDo: externalize this in conf file
        subprocess.call(["tesseract", cimFileName, cimFileName])
	text = open(cimFileName + ".txt").read()
        return json.dumps({"imgId":imgId, "text":text})

cherrypy.quickstart(BillSlicer(),"/", "cp_config.txt")
