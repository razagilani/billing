#!/usr/bin/python
'''
File: BillTemplate.py
Author: Rich Andrews
Description: A template for our bill engine
'''

#
# runtime environment
#
import sys
import os  
from pprint import pprint
from types import NoneType
import math
from decimal import *

# handle command line options
from optparse import OptionParser

#
# Types for ReportLab
#
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


# for font management
import reportlab  
from reportlab.pdfbase import pdfmetrics  
from reportlab.pdfbase.ttfonts import TTFont  
from reportlab.pdfgen.canvas import Canvas  
from reportlab.pdfbase.pdfmetrics import registerFontFamily


# for xml processing
#import amara
#from amara import bindery
#from amara import xml_print
from lxml import etree

#
# for chart graphics
#
import pychartdir
#  Activate ChartDirector License
pychartdir.setLicenseCode('DEVP-2HYW-CAU5-4YTR-6EA6-57AC')

from pychartdir import Center, Left, TopLeft, DataColor, XYChart, PieChart


#
#  Load Fonts
#
# add your font directories to the T1SearchPath in reportlab/rl_config.py as an alternative.
rptlab_folder = os.path.join(os.path.dirname(reportlab.__file__), 'fonts')

our_fonts = os.path.join(os.path.dirname(__file__), 'fonts/')

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
pdfmetrics.registerFont(TTFont("Inconsolata", 'fonts/Inconsolata.ttf'))
registerFontFamily('Inconsolata', 
                    normal = 'Inconsolata', 
                    bold = 'Inconsolata',
                    italic = 'Inconsolata')


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
            self.canv.setStrokeColorRGB(32,32,32)
            self.canv.setLineWidth(.05)
            self.canv.setDash(1,3)
            self.canv.line(0,537,612,537)
            #self.canv.line(0,264,612,264)
            self.canv.restoreState()
        if self.pageTemplate.id == secondPageName:
            self.canv.saveState()
            self.canv.setStrokeColorRGB(0,0,0)
            self.canv.setLineWidth(.05)
            self.canv.setDash(1,3)
            #self.canv.line(0,264,612,264)
            self.canv.restoreState()
        
        
    def handle_pageBegin(self):
        #print "handle_pageBegin"
        BaseDocTemplate.handle_pageBegin(self)


def progress(type,value):
    if (options.verbose):
        sys.stdout.write('.')
     
def main(options):

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
    currentChargesF = Frame(360, 100, 220, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='currentCharges', showBoundary=_showBoundaries)

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
    measuredUsageF = Frame(30, 400, 550, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billabeUsage', showBoundary=_showBoundaries)

    # Charge details header frame
    chargeDetailsHeaderF = Frame(30, 350, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetailsHeader', showBoundary=_showBoundaries)

    # charge details frame
    chargeDetailsF = Frame(30, 1, 550, 350, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)

    # build page container for flowables to populate
    secondPage = PageTemplate(id=secondPageName,frames=[backgroundF2, measuredUsageHeaderF, measuredUsageF, chargeDetailsHeaderF, chargeDetailsF])
    #

    doc = SIBillDocTemplate(options.output, pagesize=letter, showBoundary=0, allowSplitting=0)
    doc.addPageTemplates([firstPage, secondPage])

    # Bind to XML bill
    #dom = bindery.parse(options.snob)
    bt = etree.parse(options.snob)

    # instantiate a bill which will be bound to reportlab
    from billing import bill
    bill = bill.Bill(options.snob)

    Elements = []

    # grab the backgrounds that were passed in
    backgrounds = options.background.split(",")


    #
    # First Page
    #

    # populate backgroundF1
    pageOneBackground = Image('images/' + backgrounds.pop(0),letter[0], letter[1])
    Elements.append(pageOneBackground)

    # populate account number, bill id & issue date
    accountNumber = [
        [Paragraph("Account Number", styles['BillLabelRight']),Paragraph(bill.get_account() + " " + bill.get_id(),styles['BillField'])], 
        [Paragraph("Issue Date", styles['BillLabelRight']), Paragraph(get_elem(bt, "/ub:bill/ub:rebill/ub:issued")[0].text, styles['BillField'])]
    ]
    t = Table(accountNumber, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    #fits perfectly
    #Elements.append(UseUpSpace())

    # populate due date and amount
    dueDateAndAmount = [
        [Paragraph("Due Date", styles['BillLabelRight']), Paragraph(str(bill.get_due_date()), styles['BillFieldRight'])], 
        [Paragraph("Balance Due", styles['BillLabelRight']), Paragraph(str(bill.get_total_due()), styles['BillFieldRight'])]
    ]
    
    t = Table(dueDateAndAmount, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())
    
    # populate service address
    Elements.append(Spacer(100,10))
    Elements.append(Paragraph("Service Location", styles['BillLabel']))
    Elements.append(Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:addressee")[0].text), styles['BillField']))
    Elements.append(Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:street")[0].text), styles['BillField']))
    Elements.append(Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:city")[0].text) + " " 
        + str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:state")[0].text) + " " 
        + str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:serviceaddress/ub:postalcode")[0].text), styles['BillField']))
    Elements.append(UseUpSpace())

    # populate special instructions
    #Elements.append(Spacer(50,50))
    #Elements.append(UseUpSpace())
    
    # populate billing address
    Elements.append(Spacer(100,20))
    Elements.append(Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:addressee")[0].text), styles['BillFieldLg']))
    Elements.append(Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:street")[0].text), styles['BillFieldLg']))
    Elements.append(Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:city")[0].text) + " " 
        + str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:state")[0].text) + " " 
        + str(get_elem(bt, "/ub:bill/ub:rebill/ub:car/ub:billingaddress/ub:postalcode")[0].text), styles['BillFieldLg']))
    Elements.append(UseUpSpace())


    # populate graph one

    # Construct period consumption/production ratio graph
    renewableUtilization = str(get_elem(bt, "/ub:bill/ub:statistics/ub:renewableutilization")[0].text)
    conventionalUtilization = str(get_elem(bt, "/ub:bill/ub:statistics/ub:conventionalutilization")[0].text)
    data = [renewableUtilization, conventionalUtilization]
    labels = ["Renewable", "Conventional"]
    c = PieChart(10*270, 10*127)
    c.addTitle2(TopLeft, "<*underline=8*>Energy Utilization This Period", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)

    # Configure the labels using CDML to include the icon images
    c.setLabelFormat("{label} {percent|1}%")


    c.setColors2(DataColor, [0x007437,0x5a8f47]) 
    c.setPieSize((10*270)/2.2, (10*127)/1.65, ((10*127)/3.5))
    c.setData(data, labels)
    c.setLabelStyle('Inconsolata.ttf', 64)
    c.makeChart("images/utilization.png")
   
    Elements.append(Image('images/utilization.png', 270*.9, 127*.9))
    Elements.append(UseUpSpace())


    # populate graph two 
    
    # construct period environmental benefit

    periodRenewableConsumed = str(get_elem(bt, "/ub:bill/ub:statistics/ub:renewableconsumed")[0].text)
    periodPoundsCO2Offset = str(get_elem(bt, "/ub:bill/ub:statistics/ub:co2offset")[0].text)
    
    environmentalBenefit = [
        [Paragraph("<u>Environmental Benefit This Period</u>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
        [Paragraph("Renewable Energy Consumed", styles['BillLabelSm']), Paragraph(periodRenewableConsumed + " BTUs", styles['BillFieldSm'])],
        [Paragraph("Pounds Carbon Dioxide Offset", styles['BillLabelSm']), Paragraph(periodPoundsCO2Offset, styles['BillFieldSm'])],
    ]

    t = Table(environmentalBenefit, [180,90])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate graph three 
    
    # construct system life cumulative numbers table

    totalDollarSavings = str(get_elem(bt, "/ub:bill/ub:statistics/ub:totalsavings")[0].text)
    totalRenewableEnergyConsumed = str(get_elem(bt, "/ub:bill/ub:statistics/ub:totalrenewableconsumed")[0].text)
    totalco2offset = str(get_elem(bt, "/ub:bill/ub:statistics/ub:totalco2offset")[0].text)
    totalTrees = str(get_elem(bt, "/ub:bill/ub:statistics/ub:totaltrees")[0].text)

    systemLife = [
        [Paragraph("<u>System Life To Date</u>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
        [Paragraph("Total Dollar Savings", styles['BillLabelSm']), Paragraph(totalDollarSavings, styles['BillFieldSm'])],
        [Paragraph("Total Renewable Energy Consumed", styles['BillLabelSm']), Paragraph(totalRenewableEnergyConsumed + " BTUs", styles['BillFieldSm'])],
        # for next bill period
        #[Paragraph("Total Renewable Energy Produced", styles['BillLabelSm']), Paragraph("0.0", styles['BillFieldSm'])],
        [Paragraph("Total Pounds Carbon Dioxide Offset", styles['BillLabelSm']), Paragraph(totalco2offset, styles['BillFieldSm'])],
        [Paragraph("Tens of Trees to Date", styles['BillLabelSm']), Paragraph(totalTrees, styles['BillFieldSm'])]
    ]

    t = Table(systemLife, [180,90])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

    Elements.append(t)
    Elements.append(Spacer(100,20))
    
    # build string for trees
    numTrees = math.modf(float(totalTrees))[1]
    fracTree = str(math.modf(float(totalTrees))[0])[2:3]
    
    treeString = ""
    while (numTrees) > 0:
        treeString += "<img width=\"20\" height=\"25\" src=\"images/tree3.png\"/>"
        numTrees -= 1

    if (fracTree != 0): treeString += "<img width=\"20\" height=\"25\" src=\"images/tree3-" + fracTree + ".png\"/>"

    Elements.append(Paragraph("<para leftIndent=\"6\">"+treeString+"</para>", styles['BillLabel']))
    Elements.append(Spacer(100,5))
    Elements.append(Paragraph("<para leftIndent=\"50\">Ten's of Trees</para>", styles['GraphLabel']))

    Elements.append(UseUpSpace())


    # populate graph four 
    
    # construct annual production graph
    data = []
    labels = []
    for period in (get_elem(bt, "/ub:bill/ub:statistics/ub:consumptiontrend/ub:period")):
        labels.append(str(period.get("month")))
        data.append(float(period.get("quantity")))

    c = XYChart(10*270, 10*127)
    c.setPlotArea((10*270)/6, (10*127)/6.5, (10*270)*.8, (10*127)*.70)
    c.setColors2(DataColor, [0x9bbb59]) 
    c.addBarLayer(data)
    c.addTitle2(TopLeft, "<*underline=8*>Period Consumption", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)
    c.yAxis().setLabelStyle('Inconsolata.ttf', 64)
    c.yAxis().setTickDensity(100)
    c.yAxis().setTitle("100 Thousand BTUs", 'Inconsolata.ttf', 52)
    c.xAxis().setLabels(labels)
    c.xAxis().setLabelStyle('Inconsolata.ttf', 64)
    c.makeChart("images/SampleGraph4.png")    

    Elements.append(Image('images/SampleGraph4.png', 270*.9, 127*.9))
    Elements.append(UseUpSpace())

    # populate summary background
    Elements.append(Image('images/SummaryBackground.png', 443, 151))
    Elements.append(UseUpSpace())

    # populate billPeriodTableF
    # spacer so rows can line up with those in summarChargesTableF rows
    serviceperiod = [
            [Paragraph("spacer", styles['BillLabelFake']), Paragraph("spacer", styles['BillLabelFake']), Paragraph("spacer", styles['BillLabelFake'])],
            [Paragraph("", styles['BillLabelSm']), Paragraph("From", styles['BillLabelSm']), Paragraph("To", styles['BillLabelSm'])]
        ] + [
            [
                Paragraph(str(utilbill.get("service")) + u' service',styles['BillLabelSmRight']), 
                Paragraph(str(get_elem(utilbill, "ub:billperiodbegin")[0].text), styles['BillFieldRight']), 
                Paragraph(str(get_elem(utilbill, "ub:billperiodend")[0].text), styles['BillFieldRight'])
            ] 
            for utilbill in get_elem(bt, "/ub:bill/ub:utilbill")
        ]

    t = Table(serviceperiod, colWidths=[115,63,63])

    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'CENTER'), ('ALIGN',(2,0),(2,-1),'CENTER'), ('RIGHTPADDING', (0,2),(0,-1), 8), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,2), (-1,-1), 0.25, colors.black), ('BOX', (1,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,2),(-1,-1),colors.white)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate summaryChargesTableF
    hypotheticalcharges = str(Decimal(str(get_elem(bt, "/ub:bill/ub:utilbill/ub:hypotheticalecharges")[0].text)).quantize(Decimal('.00')))
    actualcharges = str(Decimal(str(get_elem(bt, "/ub:bill/ub:utilbill/ub:actualecharges")[0].text)).quantize(Decimal('.00')))
    revalue = str(Decimal(str(get_elem(bt, "/ub:bill/ub:utilbill/ub:revalue")[0].text)).quantize(Decimal('.01')))
    utilitycharges = [
        [Paragraph("Your Utility Charges", styles['BillLabelSmCenter']),Paragraph("", styles['BillLabelSm']),Paragraph("Green Energy", styles['BillLabelSmCenter'])],
        [Paragraph("w/o Renewable", styles['BillLabelSmCenter']),Paragraph("w/ Renewable", styles['BillLabelSmCenter']),Paragraph("Value", styles['BillLabelSmCenter'])]
    ]+[
        [Paragraph(hypotheticalcharges,styles['BillFieldRight']), Paragraph(actualcharges,styles['BillFieldRight']), Paragraph(revalue,styles['BillFieldRight'])]
        for utilbill in iter(get_elem(bt, "/ub:bill/ub:utilbill"))
    ]

    t = Table(utilitycharges, colWidths=[84,84,84])

    t.setStyle(TableStyle([('SPAN', (0,0), (1,0)), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,2), (-1,-1), 0.25, colors.black), ('BOX', (0,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,2),(-1,-1),colors.white)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate balances
    priorbalance = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:priorbalance")[0].text)).quantize(Decimal('.00')))
    paymentreceived = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:paymentreceived")[0].text)).quantize(Decimal('.00')))
    totaladjustment = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:totaladjustment")[0].text)).quantize(Decimal('.00')))
    balances = [
        [Paragraph("Prior Balance", styles['BillLabelRight']), Paragraph(priorbalance,styles['BillFieldRight'])],
        [Paragraph("Payment Received", styles['BillLabelRight']), Paragraph(paymentreceived, styles['BillFieldRight'])],
        [Paragraph("Adjustments", styles['BillLabelRight']), Paragraph(totaladjustment, styles['BillFieldRight'])],
    ]

    t = Table(balances, [180,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate current charges
    savings = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:resavings")[0].text)).quantize(Decimal('.00')))
    renewablecharges = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:recharges")[0].text)).quantize(Decimal('.00')))
    currentCharges = [
        [Paragraph("Your Savings", styles['BillLabelRight']), Paragraph(savings, styles['BillFieldRight'])],
        [Paragraph("Renewable Charges", styles['BillLabelRight']), Paragraph(renewablecharges, styles['BillFieldRight'])]
    ]

    t = Table(currentCharges, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate balanceForward
    balanceforward = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:balanceforward")[0].text)).quantize(Decimal('.00')))
    balance = [
        [Paragraph("Balance Forward", styles['BillLabelRight']), Paragraph( balanceforward, styles['BillFieldRight'])]
    ]

    t = Table(balance, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate balanceDueFrame
    totalbalance = str(Decimal(str(get_elem(bt, "/ub:bill/ub:rebill/ub:totaldue")[0].text)).quantize(Decimal('.00'))) 
    balanceDue = [
        [Paragraph("Balance Due", styles['BillLabelLgRight']), Paragraph( totalbalance, styles['BillFieldRight'])]
    ]

    t = Table(balanceDue, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,0),(-1,-1),colors.white)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate motd
    if bool(get_elem(bt, "/ub:bill/ub:rebill/ub:message")[0].text):
        motd = Paragraph(str(get_elem(bt, "/ub:bill/ub:rebill/ub:message")), styles['BillFieldSm'])
        Elements.append(motd)
    Elements.append(UseUpSpace())


    #
    # Second Page
    #
    Elements.append(NextPageTemplate("SecondPage"));
    Elements.append(PageBreak());


    pageTwoBackground = Image('images/' + backgrounds.pop(0),letter[0], letter[1])
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

    for measuredusage in (get_elem(bt, "/ub:bill/ub:measuredusage")):
        for meter in (get_elem(measuredusage, "ub:meter")):
            for register in (get_elem(meter, "ub:register")):
                if (register.get("shadow") == u'true'):
                    # find non-shadow register that matches this one - try and find a better way than linearly searching over and over - maybe xpath?
                    for matchregister in (get_elem(meter, "ub:register")):
                        if (str(get_elem(matchregister, "ub:identifier")[0].text) == str(get_elem(register, "ub:identifier")[0].text) and matchregister.get("shadow") == u'false'):
                            utilityregister = matchregister
                            break
                    # get the total calculation out of here and update bill model to support it.
                    measuredUsage.append([
                        str(get_elem(register, "ub:identifier")[0].text), 
                        str(get_elem(register, "ub:description")[0].text), 
                        Decimal(str(get_elem(register, "ub:total")[0].text)).quantize(Decimal('.01')), 
                        Decimal(str(get_elem(utilityregister, "ub:total")[0].text)).quantize(Decimal('.01')),
                        Decimal(str(get_elem(register, "ub:total")[0].text)).quantize(Decimal('.01')) + Decimal(str(get_elem(utilityregister, "ub:total")[0].text)).quantize(Decimal('.01')),
                        str(get_elem(register, "ub:units")[0].text)])
                    utilityregister = None

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
    # sentinal for not printing service string each iteration
    service = None

    for details in (get_elem(bt, "/ub:bill/ub:details")):
        for chargegroup in (get_elem(details, "ub:chargegroup")):
            for charges in (get_elem(chargegroup, "ub:charges")):
                if charges.get("type") == u'hypothetical':
                    for charge in (get_elem(charges, "ub:charge")):
                        # populate service cell once for each group of services
                        if(service != details.get("service")):
                            serviceStr = str(details.get("service"))
                            service = details.get("service")
                        description = get_elem(charge, "ub:description")[0].text if (len(get_elem(charge, "ub:description")) > 0) else ""
                        quantityUnits = get_elem(charge, "ub:quantity")[0].get("units") if (len(get_elem(charge, "ub:quantity")) > 0) else ""
                        # TODO: better scheme for rounding as a function of units
                        if (quantityUnits is not None and quantityUnits.lower() == 'therms'):
                            quantity = Decimal(str(get_elem(charge, "ub:quantity")[0].text)).quantize(Decimal('.00')) if (len(get_elem(charge, "ub:quantity")) > 0) else ""
                        elif (quantityUnits is not None and quantityUnits.lower() == 'dollars'):
                            quantity = Decimal(str(get_elem(charge, "ub:quantity")[0].text)).quantize(Decimal('.00')) if (len(get_elem(charge, "ub:quantity")) > 0) else ""
                        elif (quantityUnits is not None and quantityUnits.lower() == 'kwh'):
                            quantity = Decimal(str(get_elem(charge, "ub:quantity")[0].text)).quantize(Decimal('.0')) if (len(get_elem(charge, "ub:quantity")) > 0) else ""
                        else:
                            quantity = str(get_elem(charge, "ub:quantity")[0].text) if (len(get_elem(charge, "ub:quantity"))>0) else ""
                        rateUnits = get_elem(charge, "ub:rate")[0].get("units") if (len(get_elem(charge, "ub:rate")) > 0) else ""
                        rate = get_elem(charge, "ub:rate")[0].text if (len(get_elem(charge, "ub:rate")) > 0) else ""
                        total = Decimal(str(get_elem(charge, "ub:total")[0].text)).quantize(Decimal('.00'))
                        #total = charge.total
                        chargeDetails.append([serviceStr, str(description), str(quantity), str(quantityUnits), str(rate), str(rateUnits), str(total)])
                        # clear string so that it gets set on next service type
                        serviceStr = None
        for total in get_elem(details, "ub:total"):
            if(total.get("type") == u'hypothetical'):
                chargeDetails.append([None, None, None, None, None, None, Decimal(str(total.text)).quantize(Decimal('.00'))])
        # spacer
        chargeDetails.append([None, None, None, None, None, None, None])

    t = Table(chargeDetails, [50, 210, 70, 40, 70, 40, 70])

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
    doc.build(Elements)

# TODO refactor to shared utility class
def get_elem(tree, xpath):
    return tree.xpath(xpath, namespaces={"ub":"bill"})

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

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-s", "--snob", dest="snob", help="Convert bill to PDF", metavar="FILE")
    parser.add_option("-o", "--output", dest="output", help="PDF output file", metavar="FILE")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Print progress to stdout.")
    parser.add_option("-b", "--background", dest="background", default="EmeraldCity-FullBleed-1.png,EmeraldCity-FullBleed-2.png", help="Background file names in comma separated page order. E.g. -b foo-page1.png,foo-page2.png")

    (options, args) = parser.parse_args()

    if (options.snob == None):
        print "SNOB must be specified."
        exit()

    if (options.output == None):
        print "Output file must be specified."
        exit()

    main(options)
