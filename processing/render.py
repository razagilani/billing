#!/usr/bin/python
import sys
import os  
from pprint import pprint
from types import NoneType
import math
from decimal import *
from itertools import groupby
from datetime import datetime
import subprocess
import reportlab  
from pyPdf import PdfFileWriter, PdfFileReader
from reportlab.platypus import BaseDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib import colors
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfgen.pathobject import PDFPathObject 
from reportlab.pdfbase import pdfmetrics  
from reportlab.pdfbase.ttfonts import TTFont  
from reportlab.pdfgen.canvas import Canvas  
from reportlab.pdfbase.pdfmetrics import registerFontFamily


#
# for chart graphics
#
import pychartdir
#  Activate ChartDirector License
pychartdir.setLicenseCode('DEVP-2HYW-CAU5-4YTR-6EA6-57AC')

from pychartdir import Center, Left, TopLeft, DataColor, XYChart, PieChart
from billing.processing import mongo

# Unused
#from billing import graph

# TODO render should not depend on BillUpload--move this function out to its
# own file
from billing.processing.billupload import create_directory_if_necessary

sys.stdout = sys.stderr


#
# Globals
#
defaultPageSize = letter
PAGE_HEIGHT=letter[1]; PAGE_WIDTH=letter[0]
Title = "Skyline Bill"
pageinfo = "Skyline Bill"
firstPageName = 'FirstPage'
secondPageName = 'SecondPage'

class SIBillDocTemplate(BaseDocTemplate):
    """Structure Skyline Innovations Bill. """

    def build(self,flowables, canvasmaker=canvas.Canvas):
        """build the document using the flowables while drawing lines and figureson top of them."""
 
        BaseDocTemplate.build(self,flowables, canvasmaker=canvasmaker)
        
    #def beforePage(self):
        #print "Before Page: ", self.pageTemplate.id
        
    def afterPage(self):
        #print "After Page"
        if self.pageTemplate.id == firstPageName:
            self.canv.saveState()
            #self.canv.setStrokeColorRGB(32,32,32)
            #self.canv.setLineWidth(.05)
            #self.canv.setDash(1,3)
            #self.canv.line(0,537,612,537)
            #self.canv.line(0,264,612,264)
            self.canv.restoreState()
        if self.pageTemplate.id == secondPageName:
            self.canv.saveState()
            #self.canv.setStrokeColorRGB(0,0,0)
            #self.canv.setLineWidth(.05)
            #self.canv.setDash(1,3)
            #self.canv.line(0,264,612,264)
            self.canv.restoreState()
        
        
    def handle_pageBegin(self):
        #print "handle_pageBegin"
        BaseDocTemplate.handle_pageBegin(self)


def progress(type,value):
    # TODO fix module to support verbose flag passed in from cmd arg parser 
    #if (options.verbose):
    # TODO 37460179: log to logger
    # print "%s %s" %(type, value)
    pass
    


def stringify(d):
    """ convert dictionary values that are None to empty string. """
    d.update(dict([(k,'') for k,v in d.items() if v is None ]))
    return d

def concat_pdfs(in_paths, out_path):
    '''Concatenates all PDF files given in 'in_paths', writing the output file
    at 'out_path'.'''
    # pyPdf requires all input files to remain open when the output file is
    # written, so "with" can't be used. stackoverflow also says that pyPdf uses
    # file() instead of open(), even though file() is supposed to be bad and
    # will be removed from python.
    in_files = [file(path) for path in in_paths]

    # concatenate all input files into the writer object
    writer = PdfFileWriter()
    for in_file in in_files:
        reader = PdfFileReader(in_file)
        for i in range(reader.numPages):
            writer.addPage(reader.getPage(i))

    # write output file
    with open(out_path, 'wb') as out_file:
        writer.write(out_file)

    # close all the input files
    for in_file in in_files:
        in_file.close()

class ReebillRenderer:
    def __init__(self, config, state_db, reebill_dao, logger):
        '''Config should be a dict of configuration keys and values.'''
        # directory for temporary image file storage
        self.temp_directory = config['temp_directory']
        self.template_directory = config['template_directory']
        self.default_template = config['default_template']

        # set default templates
        #self.default_backgrounds = config['default_backgrounds'].split()
        #if len(self.default_backgrounds) != 2: raise ValueError("default_backgrounds not specified") 

        #self.teva_backgrounds = config['teva_backgrounds'].split()
        self.teva_accounts = config['teva_accounts'].split()


        self.state_db = state_db
        self.reebill_dao = reebill_dao

        # global reebill logger for reporting errors
        self.logger = logger

        # create temp directory if it doesn't exist
        create_directory_if_necessary(self.temp_directory, self.logger)

        #
        #  Load Fonts
        #
        # add your font directories to the T1SearchPath in reportlab/rl_config.py as an alternative.
        # TODO make the font directory relocatable
        rptlab_folder = os.path.join(os.path.dirname(reportlab.__file__), 'fonts')

        our_fonts = os.path.join(os.path.join(self.template_directory, 'fonts/'))

        # register Vera (Included in reportlab)
        pdfmetrics.registerFont(TTFont('Vera', os.path.join(rptlab_folder, 'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('VeraBd', os.path.join(rptlab_folder, 'VeraBd.ttf')))
        pdfmetrics.registerFont(TTFont('VeraIt', os.path.join(rptlab_folder, 'VeraIt.ttf')))
        pdfmetrics.registerFont(TTFont('VeraBI', os.path.join(rptlab_folder, 'VeraBI.ttf')))
        registerFontFamily('Vera',normal='Vera',bold='VeraBd',italic='VeraIt',boldItalic='VeraBI')


        # register Verdana (MS Licensed CoreFonts http://sourceforge.net/projects/corefonts/files/)
        pdfmetrics.registerFont(TTFont("Verdana", os.path.join(our_fonts, 'verdana.ttf')))
        pdfmetrics.registerFont(TTFont("VerdanaB", os.path.join(our_fonts, 'verdanab.ttf')))
        pdfmetrics.registerFont(TTFont("VerdanaI", os.path.join(our_fonts, 'verdanai.ttf')))
        registerFontFamily('Verdana',normal='Verdana',bold='VerdanaB',italic='VerdanaI')

        # register Calibri (MS Licensed CoreFonts http://sourceforge.net/projects/corefonts/files/)
        pdfmetrics.registerFont(TTFont("Courier", os.path.join(our_fonts, 'cour.ttf')))
        pdfmetrics.registerFont(TTFont("CourierB", os.path.join(our_fonts, 'courbd.ttf')))
        pdfmetrics.registerFont(TTFont("CourieI", os.path.join(our_fonts, 'couri.ttf')))
        pdfmetrics.registerFont(TTFont("CourieBI", os.path.join(our_fonts, 'courbi.ttf')))
        registerFontFamily('Courier',normal='Courier',bold='CourierB',italic='CourierBI')


        #register Inconsolata (TODO address here)
        pdfmetrics.registerFont(TTFont("Inconsolata", os.path.join(our_fonts,'Inconsolata.ttf')))
        registerFontFamily('Inconsolata', 
                            normal = 'Inconsolata', 
                            bold = 'Inconsolata',
                            italic = 'Inconsolata')


    # TODO 32204509 Why don't we just pass in a ReeBill(s) here?  Preferable to passing account/sequence/version around?
    def render(self, session, account, sequence, outputdir, outputfile, verbose):

        # Hack for overriding default template
        if (account in self.teva_accounts):
            self.default_template = 'teva'

        # render each version
        max_version = self.state_db.max_version(session, account, sequence)
        for version in range(max_version + 1):
            reebill = self.reebill_dao.load_reebill(account, sequence, version=version)
            self.render_version(reebill, outputdir, outputfile + '-%s' %
                    version, verbose)

        # concatenate version pdfs
        input_paths = ['%s-%s' % (os.path.join(outputdir, outputfile), v)
                for v in range(max_version + 1)]
        output_path = os.path.join(outputdir, outputfile)
        concat_pdfs(input_paths, output_path)
        #command = ['pdftk'] + input_paths + ['cat', 'output', output_path]
        ##print command
        #result = subprocess.Popen(command, stderr=subprocess.PIPE)
        #result.wait()
        #if result.returncode != 0:
            #raise Exception('rendering failed: ' + result.communicate()[1])

        # delete version pdfs, leaving only the combined version
        for input_path in input_paths:
            os.remove(input_path)
 
    def render_max_version(self, session, account, sequence, outputdir, outputfile, verbose):
        max_version = self.state_db.max_version(session, account, sequence)
        reebill = self.reebill_dao.load_reebill(account, sequence, version=max_version)
        self.render_version(reebill, outputdir, outputfile, verbose)

    def render_version(self, reebill, outputdir, outputfile, verbose):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='BillLabel', fontName='VerdanaB', fontSize=10, leading=10))
        styles.add(ParagraphStyle(name='BillLabelRight', fontName='VerdanaB', fontSize=10, leading=10, alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='BillLabelLg', fontName='VerdanaB', fontSize=12, leading=14))
        styles.add(ParagraphStyle(name='BillLabelLgRight', fontName='VerdanaB', fontSize=12, leading=14, alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='BillLabelSm', fontName='VerdanaB', fontSize=8, leading=8))
        styles.add(ParagraphStyle(name='BillLabelSmRight', fontName='VerdanaB', fontSize=8, leading=8, alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='BillLabelSmCenter', fontName='VerdanaB', fontSize=8, leading=8, alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='GraphLabel', fontName='Verdana', fontSize=6, leading=6))
        styles.add(ParagraphStyle(name='BillField', fontName='Inconsolata', fontSize=10, leading=10, alignment=TA_LEFT))
        styles.add(ParagraphStyle(name='BillFieldLg', fontName='Inconsolata', fontSize=12, leading=12, alignment=TA_LEFT))
        styles.add(ParagraphStyle(name='BillFieldRight', fontName='Inconsolata', fontSize=10, leading=10, alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='BillFieldLeft', fontName='Inconsolata', fontSize=10, leading=10, alignment=TA_LEFT))
        styles.add(ParagraphStyle(name='BillFieldSm', fontName='Inconsolata', fontSize=8, leading=8, alignment=TA_LEFT))
        styles.add(ParagraphStyle(name='BillLabelFake', fontName='VerdanaB', fontSize=8, leading=8, textColor=colors.white))
        style = styles['BillLabel']

        _showBoundaries = 0

        # canvas: x,y,612w,792h w/ origin bottom left
        # 72 dpi
        # frame (x,y,w,h)

        #page one frames; divided into three sections:  Summary, graphs, Charge Details

        backgroundF1 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background1', showBoundary=_showBoundaries)

        # 1/3 (612)w x (792pt-279pt=)h (to fit #9 envelope) 

        # Skyline Account number frame
        billIdentificationF = Frame(90, 657, 227, 37, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='accountNumber', showBoundary=_showBoundaries)

        # Due date and Amount frame
        amountDueF = Frame(353, 657, 227, 37, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)

        # Customer service address Frame
        serviceAddressF = Frame(371, 570, 227, 70, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='serviceAddress', showBoundary=_showBoundaries)

        # Staples envelope (for bill send)
        # #10 (4-1/8" (297pt)  x 9-1/2")
        # Left window position fits standard formats
        # Window size: 1-1/8" x 4-1/2" (324pt)
        # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom

        # Customer billing address frame
        #billingAddressF = Frame(78, 600, 250, 60, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)
        billingAddressF = Frame(78, 600, 390, 60, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)

        # 2/3

        # graph one frame
        graphOneF = Frame(30, 400, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphOne', showBoundary=_showBoundaries)

        # graph two frame
        graphTwoF = Frame(310, 400, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphTwo', showBoundary=_showBoundaries)

        # graph three frame
        graphThreeF = Frame(30, 264, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphThree', showBoundary=_showBoundaries)

        # graph four frame
        graphFourF = Frame(310, 264, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphFour', showBoundary=_showBoundaries)

        # 3/3

        # summary background block
        summaryBackgroundF = Frame(141, 75, 443, 152, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryBackground', showBoundary=_showBoundaries)

        billPeriodTableF = Frame(30, 167, 241, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billPeriod', showBoundary=_showBoundaries)

        # summary charges block
        summaryChargesTableF = Frame(328, 167, 252, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryCharges', showBoundary=_showBoundaries)

        # balance block
        balanceF = Frame(78, 100, 265, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balance', showBoundary=_showBoundaries)

        # current charges block
        # your savings and renewable charges
        currentChargesF = Frame(360, 108, 220, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='currentCharges', showBoundary=_showBoundaries)

        # balance forward block
        balanceForwardF = Frame(360, 75, 220, 21, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balance', showBoundary=_showBoundaries)

        # balance due block
        balanceDueF = Frame(360, 41, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balanceDue', showBoundary=_showBoundaries)

        # Special instructions frame
        motdF = Frame(30, 41, 220, 50, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='motd', showBoundary=_showBoundaries)


        # build page container for flowables to populate
        firstPage = PageTemplate(id=firstPageName,frames=[backgroundF1, billIdentificationF, amountDueF, serviceAddressF, billingAddressF, graphOneF, graphTwoF, graphThreeF, graphFourF, summaryBackgroundF, billPeriodTableF, summaryChargesTableF, balanceF, currentChargesF, balanceForwardF, balanceDueF, motdF])
        #

        # page two frames

        # page two background frame
        backgroundF2 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background2', showBoundary=_showBoundaries)

        # Staples envelope (for bill return)
        # #9 standard invoice (3-7/8" (279pt) x 8-7/8" (639pt))
        # Left window position fits standard formats
        # Window size: 1-1/8" (81pt) x 4-1/2" (324pt)
        # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom

        # Measured Usage header frame
        measuredUsageHeaderF = Frame(30, 500, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='measuredUsageHeader', showBoundary=_showBoundaries)

        # measured usage meter summaries
        measuredUsageF = Frame(30, 400, 550, 105, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billableUsage', showBoundary=_showBoundaries)

        # Charge details header frame
        chargeDetailsHeaderF = Frame(30, 350, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetailsHeader', showBoundary=_showBoundaries)

        # charge details frame
        chargeDetailsF = Frame(30, 1, 550, 350, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)

        # build page container for flowables to populate
        secondPage = PageTemplate(id=secondPageName,frames=[backgroundF2, measuredUsageHeaderF, measuredUsageF, chargeDetailsHeaderF, chargeDetailsF])
        #
        # Create the customer account directory if it is absent
        if not os.path.exists(outputdir):
            os.mkdir(outputdir)

        # TODO: 17377331 - find out why the failure is silent
        # for some reasons, if the file path passed in does not exist, SIBillDocTemplate fails silently 
        # print "%s %s" % (outputdir, outputfile)
        doc = SIBillDocTemplate("%s/%s" % (outputdir, outputfile), pagesize=letter, showBoundary=0, allowSplitting=0)
        doc.addPageTemplates([firstPage, secondPage])

        Elements = []

        #
        # First Page
        #

        # populate backgroundF1
        pageOneBackground = Image(os.path.join(os.path.join(self.template_directory, self.default_template), "page_one.png"),letter[0], letter[1])
        Elements.append(pageOneBackground)

        # populate account number, bill id & issue date
        accountNumber = [
            [Paragraph("Account Number", styles['BillLabelRight']),Paragraph(reebill.account + " " + str(reebill.sequence),styles['BillField'])], 
            [Paragraph("Issue Date", styles['BillLabelRight']), Paragraph(str(reebill.issue_date), styles['BillField'])]
        ]

        t = Table(accountNumber, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        Elements.append(t)
        #fits perfectly
        #Elements.append(UseUpSpace())

        # populate due date and amount
        dueDateAndAmount = [
            [Paragraph("Due Date", styles['BillLabelRight']), Paragraph(str(reebill.due_date), styles['BillFieldRight'])], 
            [Paragraph("Balance Due", styles['BillLabelRight']), Paragraph(str(reebill.balance_due.quantize(Decimal("0.00"))), styles['BillFieldRight'])]
        ]
        
        t = Table(dueDateAndAmount, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        Elements.append(t)
        Elements.append(UseUpSpace())
        
        # populate service address
        Elements.append(Spacer(100,10))
        Elements.append(Paragraph("Service Location", styles['BillLabel']))

        sa = stringify(reebill.service_address)
        Elements.append(Paragraph(sa.get('sa_addressee', ""), styles['BillField']))
        Elements.append(Paragraph(sa.get('sa_street1',""), styles['BillField']))
        Elements.append(Paragraph(" ".join((sa.get('sa_city', ""), sa.get('sa_state', ""), sa.get('sa_postal_code', ""))), styles['BillField']))
        Elements.append(UseUpSpace())

        # populate special instructions
        #Elements.append(Spacer(50,50))
        #Elements.append(UseUpSpace())
        
        # populate billing address
        Elements.append(Spacer(100,20))
        ba = stringify(reebill.billing_address)
        Elements.append(Paragraph(ba.get('ba_addressee', ""), styles['BillFieldLg']))
        Elements.append(Paragraph(ba.get('ba_street1', ""), styles['BillFieldLg']))
        Elements.append(Paragraph(" ".join((ba.get('ba_city', ""), ba.get('ba_state', ""), ba.get('ba_postal_code',""))), styles['BillFieldLg']))
        Elements.append(UseUpSpace())


        # statistics

        st = reebill.statistics

        # populate graph one

        # Construct period consumption/production ratio graph
        # TODO: 20846595 17928227 why does render bill have to check for the presence of keys? And then check for the presence of a value?  This sucks.
        renewableUtilization = st.get('renewable_utilization', "n/a")
        conventionalUtilization = st.get('conventional_utilization', "n/a")
        data = [renewableUtilization if renewableUtilization is not None else 0,
            conventionalUtilization if conventionalUtilization is not None else 0]
        labels = ["Renewable", "Conventional"]
        c = PieChart(10*270, 10*127)
        c.addTitle2(TopLeft, "<*underline=8*>Energy Utilization This Period", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)

        # Configure the labels using CDML to include the icon images
        c.setLabelFormat("{label} {percent|1}%")


        c.setColors2(DataColor, [0x007437,0x5a8f47]) 
        c.setPieSize((10*270)/2.2, (10*127)/1.65, ((10*127)/3.5))
        c.setData(data, labels)
        c.setLabelStyle('Inconsolata.ttf', 64)
        image_filename = "utilization-%s.png" % datetime.now()
        image_path = os.path.join(self.temp_directory, image_filename)
        c.makeChart(image_path)
       
        Elements.append(Image(image_path, 270*.9, 127*.9))
        Elements.append(UseUpSpace())



        # populate graph two 
        
        # construct period environmental benefit

        periodRenewableConsumed = st.get('renewable_consumed', 0)
        periodRenewableConsumed = str(Decimal(str(periodRenewableConsumed))) if periodRenewableConsumed is not None else "0"

        periodPoundsCO2Offset = st.get('co2_offset', 0)
        periodPoundsCO2Offset = str(Decimal(str(periodPoundsCO2Offset))) if periodPoundsCO2Offset is not None else "0"
        
        environmentalBenefit = [
            [Paragraph("<u>Environmental Benefit This Period</u>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
            [Paragraph("Renewable Energy Consumed", styles['BillLabelSm']), Paragraph("%s BTUs" % periodRenewableConsumed, styles['BillFieldSm'])],
            [Paragraph("Pounds Carbon Dioxide Offset", styles['BillLabelSm']), Paragraph(periodPoundsCO2Offset, styles['BillFieldSm'])],
        ]

        t = Table(environmentalBenefit, [180,90])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

        Elements.append(t)
        Elements.append(UseUpSpace())


        # populate graph three 
        
        # construct system life cumulative numbers table

        total_renewable_consumed = st.get('total_renewable_consumed', 0)
        total_renewable_consumed = str(Decimal(str(total_renewable_consumed if total_renewable_consumed is not None else "0")).quantize(Decimal("0")))
        total_co2_offset = st.get('total_co2_offset', 0)
        total_co2_offset = str(Decimal(str(total_co2_offset if total_co2_offset is not None else "0")).quantize(Decimal("0")))

        total_trees = st.get('total_trees', 0)
        total_trees = str(Decimal(str(total_trees if total_trees is not None else "0")).quantize(Decimal("0.0")))

        systemLife = [
            [Paragraph("<u>System Life To Date</u>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
            [Paragraph("Total Dollar Savings", styles['BillLabelSm']), Paragraph(str(st.get('total_savings', "n/a")), styles['BillFieldSm'])],
            [Paragraph("Total Renewable Energy Consumed", styles['BillLabelSm']), Paragraph(total_renewable_consumed + " BTUs", styles['BillFieldSm'])],
            [Paragraph("Total Pounds Carbon Dioxide Offset", styles['BillLabelSm']), Paragraph(total_co2_offset, styles['BillFieldSm'])],
            [Paragraph("Equivalent to This Many Trees", styles['BillLabelSm']), Paragraph(total_trees, styles['BillFieldSm'])]
        ]

        t = Table(systemLife, [180,90])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

        Elements.append(t)
        Elements.append(Spacer(100,20))
        
        # build string for trees:
        # each tree image represents either 10 or 100 trees (scale is changed so tree images fit)
        if float(total_trees) <= 10:
            tree_images = float(total_trees)
            tree_label = 'Trees'
        else:
            tree_images = float(total_trees) / 10.0
            tree_label = 'Tens of Trees'
        # number of whole trees to show is the floor of tree_images; the fractional
        # tree image that is shown (if any) is determined by the fractional part of
        # tree_images
        tree_image_fraction, whole_tree_images = math.modf(tree_images)
        whole_tree_images = int(whole_tree_images)
        # round the fractional part to the nearest tenth, and convert it into a string
        # (so it's now one of the digits 0-9)
        tree_image_fraction = str(int(math.floor(10 * tree_image_fraction)))


        treeString = ""
        while (whole_tree_images) > 0:
            treeString += "<img width=\"20\" height=\"25\" src=\"" + os.path.join(self.template_directory, "images", "tree3.png") +"\"/>"
            whole_tree_images -= 1

        if (tree_image_fraction != 0): treeString += "<img width=\"20\" height=\"25\" src=\"" + os.path.join(self.template_directory, "images","tree3-" + tree_image_fraction + ".png") + "\"/>"

        Elements.append(Paragraph("<para leftIndent=\"6\">"+treeString+"</para>", styles['BillLabel']))

        Elements.append(Spacer(100,5))
        Elements.append(Paragraph("<para leftIndent=\"50\">%s</para>" % tree_label, styles['GraphLabel']))

        Elements.append(UseUpSpace())


        # populate graph four 
        
        # construct annual production graph
        data = []
        labels = []
        for period in (st.get('consumption_trend',[])):
            labels.append(str(period.get("month")))
            data.append(float(period.get("quantity")))

        c = XYChart(10*270, 10*127)
        c.setPlotArea((10*270)/6, (10*127)/6.5, (10*270)*.8, (10*127)*.70)
        c.setColors2(DataColor, [0x9bbb59, 0xff0000]) 
        c.addBarLayer(data)
        c.addTitle2(TopLeft, "<*underline=8*>Monthly Renewable Energy Consumption", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)
        c.yAxis().setLabelStyle('Inconsolata.ttf', 64)
        c.yAxis().setTickDensity(100)
        c.yAxis().setTitle("Therms", 'Inconsolata.ttf', 52)
        c.xAxis().setLabels(labels)
        c.xAxis().setLabelStyle('Inconsolata.ttf', 64)
        image_filename = "Graph4-%s.png" % datetime.now()
        c.makeChart(os.path.join(self.temp_directory,image_filename))    

        Elements.append(Image(os.path.join(self.temp_directory,image_filename), 270*.9, 127*.9))
        Elements.append(UseUpSpace())


        # populate summary background
        Elements.append(Image(os.path.join(self.template_directory,'images','SummaryBackground.png'), 443, 151))
        Elements.append(UseUpSpace())

        # populate billPeriodTableF
        # spacer so rows can line up with those in summarChargesTableF rows
        serviceperiod = [
                [Paragraph("spacer", styles['BillLabelFake']), Paragraph("spacer", styles['BillLabelFake']), Paragraph("spacer", styles['BillLabelFake'])],
                [Paragraph("", styles['BillLabelSm']), Paragraph("From", styles['BillLabelSm']), Paragraph("To", styles['BillLabelSm'])]
            ] + [
                [
                    Paragraph(service + u' service',styles['BillLabelSmRight']), 
                    Paragraph(str(reebill.utilbill_period_for_service(service)[0]), styles['BillFieldRight']), 
                    Paragraph(str(reebill.utilbill_period_for_service(service)[1]), styles['BillFieldRight'])
                ] for service in reebill.services
            ]

        t = Table(serviceperiod, colWidths=[115,63,63])

        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'CENTER'), ('ALIGN',(2,0),(2,-1),'CENTER'), ('RIGHTPADDING', (0,2),(0,-1), 8), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,2), (-1,-1), 0.25, colors.black), ('BOX', (1,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,2),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        utilitycharges = [
            [Paragraph("Your Utility Charges", styles['BillLabelSmCenter']),Paragraph("", styles['BillLabelSm']),Paragraph("Green Energy", styles['BillLabelSmCenter'])],
            [Paragraph("w/o Renewable", styles['BillLabelSmCenter']),Paragraph("w/ Renewable", styles['BillLabelSmCenter']),Paragraph("Value", styles['BillLabelSmCenter'])]
        ]+[
            [
                Paragraph(str(reebill.hypothetical_total_for_service(service).quantize(Decimal(".00"))),styles['BillFieldRight']), 
                Paragraph(str(reebill.actual_total_for_service(service).quantize(Decimal(".00"))),styles['BillFieldRight']), 
                Paragraph(str(reebill.ree_value_for_service(service).quantize(Decimal(".00"))),styles['BillFieldRight'])
            ] for service in reebill.services
        ]

        t = Table(utilitycharges, colWidths=[84,84,84])

        t.setStyle(TableStyle([('SPAN', (0,0), (1,0)), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,2), (-1,-1), 0.25, colors.black), ('BOX', (0,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,2),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        # populate balances
        manual_adjustments = reebill.manual_adjustment
        other_adjustments = reebill.total_adjustment - reebill.manual_adjustment

        balances = [
            [Paragraph("Prior Balance", styles['BillLabelRight']), Paragraph(str(reebill.prior_balance.quantize(Decimal(".00"))),styles['BillFieldRight'])],
            [Paragraph("Payment Received", styles['BillLabelRight']), Paragraph(str(reebill.payment_received.quantize(Decimal(".00"))), styles['BillFieldRight'])],
            [Paragraph("Manual Adjustments", styles['BillLabelRight']), Paragraph(str(manual_adjustments.quantize(Decimal(".00"))), styles['BillFieldRight'])],
            [Paragraph("Other Adjustments", styles['BillLabelRight']), Paragraph(str(other_adjustments.quantize(Decimal(".00"))), styles['BillFieldRight'])]
        ]

        t = Table(balances, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())


        try:
            # populate current charges
            late_charges = reebill.late_charges
        except KeyError:
            late_charges = None

        # depiction of conditional template logic based on ReeBill returning None
        # we will want to distinguish between a late charge, a zero dollar late charge and no late charge
        # to allow the template to do fancy formatting
        if late_charges is not None:
            currentCharges = [
                [Paragraph("Your Savings", styles['BillLabelRight']), Paragraph(str(reebill.ree_savings.quantize(Decimal(".00"))), styles['BillFieldRight'])],
                [Paragraph("Renewable Charges", styles['BillLabelRight']), Paragraph(str(reebill.ree_charges.quantize(Decimal(".00"))), styles['BillFieldRight'])],
                [Paragraph("Late Charges", styles['BillLabelRight']), Paragraph(str(late_charges.quantize(Decimal(".00"))), styles['BillFieldRight'])]
            ]
        else:
            currentCharges = [
                [Paragraph("Your Savings", styles['BillLabelRight']), Paragraph(str(reebill.ree_savings.quantize(Decimal(".00"))), styles['BillFieldRight'])],
                [Paragraph("Renewable Charges", styles['BillLabelRight']), Paragraph(str(reebill.ree_charges.quantize(Decimal(".00"))), styles['BillFieldRight'])],
                [Paragraph("Late Charges", styles['BillLabelRight']), Paragraph(str("n/a"), styles['BillFieldRight'])]
            ]

        t = Table(currentCharges, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        # populate balanceForward
        balance = [
            [Paragraph("Balance Forward", styles['BillLabelRight']), Paragraph(str(reebill.balance_forward.quantize(Decimal(".00"))), styles['BillFieldRight'])]
        ]

        t = Table(balance, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())



        # populate balanceDueFrame
        balanceDue = [
            [Paragraph("Balance Due", styles['BillLabelLgRight']), Paragraph(str(reebill.balance_due.quantize(Decimal(".00"))), styles['BillFieldRight'])]
        ]

        t = Table(balanceDue, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        # populate motd
        Elements.append(Paragraph(reebill.motd if reebill.motd is not None else "", styles['BillFieldSm']))
        Elements.append(UseUpSpace())



        #
        # Second Page
        #
        Elements.append(NextPageTemplate("SecondPage"));
        Elements.append(PageBreak());



        pageTwoBackground = Image(os.path.join(self.template_directory, self.default_template, "page_two.png"), letter[0], letter[1])
        Elements.append(pageTwoBackground)

        #populate measured usage header frame
        Elements.append(Paragraph("Measured renewable and conventional energy.", styles['BillLabel']))
        Elements.append(UseUpSpace())


        # list of the rows
        measuredUsage = [
            ["Utility Register", "Description", "Quantity", "", "",""],
            [None, None, "Renewable", "Utility", "Total", None],
            [None, None, None, None,  None, None,]
        ]

        # make a dictionary like Bill.measured_usage() using data from MongoReeBill:
        mongo_measured_usage = dict((service,reebill.meters_for_service(service)) for service in reebill.services)

        # TODO: show both the utilty and shadow register as separate line items such that both their descriptions and rules could be shown
        for service, meters in mongo_measured_usage.items():
            for meter in meters:
                keyfunc = lambda register:register['identifier']
                # sort the registers by identifier to ensure similar identifiers are adjacent
                registers = sorted(meter['registers'], key=keyfunc )

                # group by the identifier attribute of each register
                for identifier, register_group in groupby(registers, key=keyfunc):

                    shadow_total = None
                    utility_total = None
                    total = 0

                    # TODO validate that there is only a utility and shadow register
                    for register in register_group:
                        if register['shadow'] is True:
                            shadow_total = register['quantity']
                            total += register['quantity']
                        if register['shadow'] is False:
                            utility_total = register['quantity']
                            total += register['quantity']

                    measuredUsage.append([
                        # TODO unless some wrapper class exists (pivotal 13643807) check for errors
                        register['identifier'],
                        register['description'],
                        # as in the case of a second meter that doesn't have a shadow register (see family laundry)
                        # TODO 21314105 shadow_total is an int if RE was bound and its value was zero (non communicating site)? 
                        shadow_total.quantize(Decimal("0.00")) if shadow_total is not None else "",
                        utility_total,
                        total.quantize(Decimal("0.00")),
                        register['quantity_units'],
                    ])

        measuredUsage.append([None, None, None, None, None, None])

        # total width 550
        t = Table(measuredUsage, [100, 250, 55, 55, 55, 35])

        t.setStyle(TableStyle([
            ('SPAN',(2,0),(5,0)),
            ('SPAN',(4,1),(5,1)),
            ('BOX', (0,0), (-1,-1), 0.25, colors.black),
            ('BOX', (0,2), (0,-1), 0.25, colors.black),
            ('BOX', (1,2), (1,-1), 0.25, colors.black),
            ('BOX', (2,2), (2,-1), 0.25, colors.black),
            ('BOX', (3,2), (3,-1), 0.25, colors.black),
            ('BOX', (4,2), (5,-1), 0.25, colors.black),
            ('TOPPADDING', (0,0), (-1,-1), 0), 
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (4,2), (4,-1), 2), 
            ('LEFTPADDING', (5,2), (5,-1), 1), 
            ('FONT', (0,0),(-1,0), 'VerdanaB'), # Bill Label Style
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('FONT', (0,1),(-1,-1), 'Inconsolata'),
            ('FONTSIZE', (0,1), (-1,-1), 7),
            ('LEADING', (0,1), (-1,-1), 9),
            ('ALIGN',(0,0),(0,0),'LEFT'),
            ('ALIGN',(1,0),(5,0),'CENTER'),
            ('ALIGN',(2,1),(3,1),'CENTER'),
            ('ALIGN',(4,1),(5,1),'CENTER'),
            ('ALIGN',(2,2),(2,-1),'RIGHT'),
            ('ALIGN',(3,2),(3,-1),'RIGHT'),
            ('ALIGN',(4,2),(4,-1),'RIGHT'),
            ('ALIGN',(4,2),(4,-1),'RIGHT'),
            ('ALIGN',(5,2),(5,-1),'LEFT'),
        ]))

        Elements.append(t)
        Elements.append(UseUpSpace())


        Elements.append(Paragraph("Original utility charges prior to renewable energy.", styles['BillLabel']))
        Elements.append(UseUpSpace())

        # list of the rows
        chargeDetails = [
            ["Service", "Charge Description", "Quantity","", "Rate","", "Total"],
            [None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None]
        ]

        for service in reebill.services:
            # MongoReebill.hypothetical_chargegroups_for_service() returns a dict
            # mapping charge types (e.g. "All Charges") to lists of chargegroups.
            chargegroups_dict = reebill.hypothetical_chargegroups_for_service(service)
            for charge_type in chargegroups_dict.keys():
                chargeDetails.append([service, None, None, None, None, None, None])
                for i, charge in enumerate(chargegroups_dict[charge_type]):
                    chargeDetails.append([
                        charge_type if i == 0 else "",
                        charge.get('description', "No description"),
                        charge['quantity'].quantize(Decimal(".000")) if 'quantity' in charge else Decimal("1"),
                        charge.get('quantity_units', ""),
                        charge['rate'].quantize(Decimal(".00000")) if 'rate' in charge else "",
                        charge.get('rate_units', ""), 
                        charge['total'].quantize(Decimal(".00")) if 'total' in charge else "",
                    ])
            # spacer
            chargeDetails.append([None, None, None, None, None, None, None])
            chargeDetails.append([None, None, None, None, None, None, reebill.hypothetical_total_for_service(service).quantize(Decimal(".00"))])

        t = Table(chargeDetails, [80, 180, 70, 40, 70, 40, 70])

        #('BOX', (0,0), (-1,-1), 0.25, colors.black), 
        t.setStyle(TableStyle([
            #('INNERGRID', (1,0), (-1,1), 0.25, colors.black), 
            ('BOX', (0,2), (0,-1), 0.25, colors.black),
            ('BOX', (1,2), (1,-1), 0.25, colors.black),
            ('BOX', (2,2), (3,-1), 0.25, colors.black),
            ('BOX', (4,2), (5,-1), 0.25, colors.black),
            ('BOX', (6,2), (6,-1), 0.25, colors.black),
            ('TOPPADDING', (0,0), (-1,-1), 0), 
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (2,2), (2,-1), 2), 
            ('LEFTPADDING', (3,2), (3,-1), 1), 
            ('RIGHTPADDING', (4,2), (4,-1), 2), 
            ('LEFTPADDING', (5,2), (5,-1), 1), 
            ('FONT', (0,0),(-1,0), 'VerdanaB'), # Bill Label Style
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('FONT', (0,1),(-1,-1), 'Inconsolata'),
            ('FONTSIZE', (0,1), (-1,-1), 7),
            ('LEADING', (0,1), (-1,-1), 9),
            ('ALIGN',(0,0),(0,0),'LEFT'),
            ('ALIGN',(1,0),(1,0),'CENTER'),
            ('ALIGN',(2,0),(2,-1),'RIGHT'),
            ('ALIGN',(4,0),(4,-1),'RIGHT'),
            ('ALIGN',(6,0),(6,-1),'RIGHT'),
        ]))

        Elements.append(t)
        Elements.append(UseUpSpace())

        # render the document    
        doc.setProgressCallBack(progress)
        try:
            doc.build(Elements)
        except Exception as e:
            print str(e)

# remove all calculations to helpers
def poundsCarbonFromGas(therms = 0):
    """http://www.carbonfund.org/site/pages/carbon_calculators/category/Assumptions
    There are 12.0593 pounds CO2 per CCF of natural gas. We multiply 12.0593 by the number of CCF consumed annually and divide by 2,205 to get metric tons of CO2.
    13.46lbs per therm
    In the United States and Canada[2] however a ton is defined to be 2000 pounds [about 907 kg] (wikipedia)"""
    return int(therms) * 13.46

def poundsCarbonFromElectric(kWh = 0):
    """http://www.carbonfund.org/site/pages/carbon_calculators/category/Assumptions
    On average, electricity sources emit 1.297 lbs CO2 per kWh (0.0005883 metric tons CO2 per kWh)
    In the United States and Canada[2] however a ton is defined to be 2000 pounds [about 907 kg] (wikipedia)"""
    return int(kWh) * 1.297

def equivalentTrees(poundsCarbonAvoided = 0):
    """One ton per tree over the lifetime, ~13 lbs a year.
    Assume 1.08 pounds per bill period"""
    return int(poundsCarbon) * 1.08

if __name__ == '__main__':
    from billing.mongo import ReebillDAO
    from billing.processing.state import StateDB
    from billing.processing.session_contextmanager import DBSession
    from billing.processing.process import Process
    sdb = StateDB(**{
        'host': 'localhost',
        'database': 'skyline_dev',
        'user': 'dev',
        'password': 'dev'
    })
    reebill_dao = ReebillDAO(sdb, **{
        'host': 'localhost',
        'database': 'skyline',
        'user': 'dev',
        'password': 'dev'
    })
    renderer = ReebillRenderer(
            {'temp_directory': '/tmp/rendering/'},
            sdb, reebill_dao, None)
    with DBSession(sdb) as s:
        renderer.render(
            s,
            '10023', 
            8,
            '/tmp/rendering/10023/',
            "10023-8.pdf",
            "EmeraldCity-FullBleed-1v2.png,EmeraldCity-FullBleed-2v2.png",
            False
        )
