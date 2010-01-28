#!/usr/bin/python
'''
File: BillTemplate.py
Author: Rich Andrews
Description: A template for our awesome bill engine
Usage:  Rich!  Fill me out!
'''

#
# runtime environment
#
import sys
import os  
from pprint import pprint
from types import NoneType


from reportlab.platypus import BaseDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace

from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
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
import amara
from amara import bindery
from amara import xml_print


#
# for graphics
#
from pychartdir import TopLeft, DataColor, XYChart, PieChart

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
            self.canv.setStrokeColorRGB(0,255,128)
            self.canv.setLineWidth(.2)
            self.canv.setDash(1,3)
            self.canv.line(0,264,612,264)
            self.canv.line(0,528,612,528)
            self.canv.restoreState()
        
        
    def handle_pageBegin(self):
        #print "handle_pageBegin"
        BaseDocTemplate.handle_pageBegin(self)


def progress(type,value):
    sys.stdout.write('.')
     
def go():
    '''docstring goes here?'''

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BillLabel', fontName='VerdanaB', fontSize=10, leading=10))
    styles.add(ParagraphStyle(name='BillLabelRight', fontName='VerdanaB', fontSize=10, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='BillLabelRight1', fontName='VerdanaB', fontSize=10, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='BillLabelSm', fontName='VerdanaB', fontSize=8, leading=8))
    styles.add(ParagraphStyle(name='BillField', fontName='Inconsolata', fontSize=10, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='BillFieldRight', fontName='Inconsolata', fontSize=10, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='BillFieldLeft', fontName='Inconsolata', fontSize=10, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='BillFieldSm', fontName='Inconsolata', fontSize=8, leading=10, alignment=TA_LEFT))
    style = styles['BillLabel']

    _showBoundaries = 0

    # 612w 792h

    #page one frames
    backgroundF1 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background1', showBoundary=_showBoundaries)

    # bill dates block
    billIssueDateF = Frame(78, 680, 120, 12, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billIssueDate', showBoundary=_showBoundaries)
    billDueDateF = Frame(203, 680, 140, 12, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billDueDate', showBoundary=_showBoundaries)
    billPeriodTableF = Frame(78, 627, 265, 38, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=1, id='billPeriod', showBoundary=_showBoundaries)

    # summary charges block
    summaryChargesTableF = Frame(353, 627, 220, 62, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=7, id='summaryCharges', showBoundary=_showBoundaries)

    # balance block
    balanceF = Frame(78, 556, 265, 60, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='balance', showBoundary=_showBoundaries)

    # current charges block
    currentChargesF = Frame(353, 556, 220, 60, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='currentCharges', showBoundary=_showBoundaries)


    # graph one frame
    graphOneF = Frame(30, 400, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphOne', showBoundary=_showBoundaries)
    
    # graph two frame
    graphTwoF = Frame(310, 400, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphTwo', showBoundary=_showBoundaries)
    
    # graph three frame
    graphThreeF = Frame(30, 264, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphThree', showBoundary=_showBoundaries)
    
    # graph four frame
    graphFourF = Frame(310, 264, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphFour', showBoundary=_showBoundaries)

    # Skyline Account number frame
    accountNumberF = Frame(30, 238, 227, 18, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='accountNumber', showBoundary=_showBoundaries)
    
    # Due date and Amount frame
    amountDueF = Frame(353, 200, 227, 56, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)
    
    # Customer service address Frame
    serviceAddressF = Frame(30, 147, 306, 80, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='serviceAddress', showBoundary=_showBoundaries)
    
    # Special instructions frame
    specialInstructionsF = Frame(353, 50, 227, 140, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='specialInstructions', showBoundary=_showBoundaries)
    
    # Customer billing address frame
    billingAddressF = Frame(30, 50, 306, 80, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)


    firstPage = PageTemplate(id=firstPageName,frames=[backgroundF1, billIssueDateF, billDueDateF, billPeriodTableF, summaryChargesTableF, balanceF, currentChargesF, graphOneF, graphTwoF, graphThreeF, graphFourF, accountNumberF, amountDueF, serviceAddressF, specialInstructionsF, billingAddressF])

 
    # page two frames
    backgroundF2 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background2', showBoundary=_showBoundaries)
    chargeDetailsHeaderF = Frame(30,735, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)
    chargeDetailsF = Frame(30,375, 550, 350, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)

    secondPage = PageTemplate(id=secondPageName,frames=[backgroundF2, chargeDetailsHeaderF, chargeDetailsF])



    doc = SIBillDocTemplate('bill.pdf', pagesize=letter, showBoundary=0, allowSplitting=0)
    doc.addPageTemplates([firstPage, secondPage])

    # Bind to XML bill
    dom = bindery.parse('../bills/Skyline-1-10001.xml')

    Elements = []

    #
    # First Page
    #

    # populate backgroundF1
    pageOneBackground = Image('images/EmeraldCityBackground.png',letter[0], letter[1])
    Elements.append(pageOneBackground)


    # populate billIssueDateF
    Elements.append(Paragraph("Issued  <font name='Inconsolata'> " + str(dom.utilitybill.skylinebill.issued) + "</font>", styles['BillLabelRight']))
    Elements.append(UseUpSpace())

    # populate billDueDateF
    Elements.append(Paragraph("Due Date  <font name='Inconsolata'> " + str(dom.utilitybill.skylinebill.duedate) + "</font>", styles['BillLabelRight']))
    Elements.append(UseUpSpace())


    # populate billPeriodTableF
    serviceperiod = [
        [
            Paragraph(str(summary.service) + u' service period',styles['BillLabelSm']), 
            Paragraph(str(summary.billperiodbegin), styles['BillField']), 
            Paragraph(str(summary.billperiodend), styles['BillField'])
        ] 
        for summary in iter(dom.utilitybill.summary)
    ]

    t = Table(serviceperiod, [115,75,75])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'CENTER'), ('ALIGN',(2,0),(2,-1),'CENTER'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black) ]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate summaryChargesTableF
    utilitycharges = [
        [Paragraph("Before Skyline", styles['BillLabelRight']),Paragraph("After Skyline", styles['BillLabelRight'])]
    ]+[
        [Paragraph(str(summary.hypotheticalcharges),styles['BillFieldRight']), Paragraph(str(summary.currentcharges),styles['BillFieldRight'])]
        for summary in iter(dom.utilitybill.summary)
    ]

    t = Table(utilitycharges, [125,95])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,1), (-1,-1), 0.25, colors.black), ('BOX', (0,1), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate balances
    balances = [
        [Paragraph("Prior Balance", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.priorbalance),styles['BillFieldRight'])],
        [Paragraph("Payment Received", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.paymentreceived), styles['BillFieldRight'])],
        [Paragraph("Balance Forward", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.balanceforward), styles['BillFieldRight'])]
    ]

    t = Table(balances, [180,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate current charges
    currentCharges = [
        [Paragraph("Your Savings", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.customersavings), styles['BillFieldRight'])],
        [Paragraph("Renewable Energy", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.energycharges), styles['BillFieldRight'])], 
        [Paragraph("Current Charges", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.currentcharges), styles['BillFieldRight'])]
    ]

    t = Table(currentCharges, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate graph one

    # Construct period consumption/production ratio graph
    data = [40, 60]
    labels = ["Renewable", "Grid"]
    c = PieChart(10*270, 10*127)
    c.addTitle2(TopLeft, "<*underline=8*>Utilization This Period", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)

    c.setColors2(DataColor, [0x007437,0x5a8f47]) 
    c.setPieSize((10*270)/1.9, (10*127)/1.9, ((10*127)/2.5))
    c.setData(data, labels)
    c.setLabelStyle('verdana.ttf', 64)
    c.makeChart("images/SampleGraph1.png")
   
    Elements.append(Image('images/SampleGraph1.png', 270*.9, 127*.9))
    Elements.append(UseUpSpace())


    # populate graph two 
    
    # construct period environmental benefit

    environmentalBenefit = [
        [Paragraph("<u>Environmental Benefit This Period</u>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
        [Paragraph("Pounds Carbon Offset", styles['BillLabelSm']), Paragraph("0.0", styles['BillFieldSm'])]
    ]

    t = Table(environmentalBenefit, [180,90])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate graph three 
    
    # construct system life cumulative numbers table

    systemLife = [
        [Paragraph("<u>Total System Life</u>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
        [Paragraph("Pounds Carbon Offset", styles['BillLabelSm']), Paragraph("0.0", styles['BillFieldSm'])],
        [Paragraph("Cars Removed from Road", styles['BillLabelSm']), Paragraph("5", styles['BillFieldSm'])]
    ]

    t = Table(systemLife, [180,90])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate graph four 
    
    # construct annual production graph
    data = [30, 28, 40, 55, 75, 68, 54, 60, 50, 62, 75, 65]
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    c = XYChart(10*270, 10*127)
    c.setPlotArea((10*270)/12, (10*127)/6.5, (10*270)*.9, (10*127)*.70)
    c.setColors2(DataColor, [0x9bbb59]) 
    c.addBarLayer(data)
    c.addTitle2(TopLeft, "<*underline=8*>Annual Production", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)
    c.yAxis().setLabelStyle('verdana.ttf', 64)
    c.yAxis().setTickDensity(100)
    c.xAxis().setLabels(labels)
    c.xAxis().setLabelStyle('verdana.ttf', 64)
    c.makeChart("images/SampleGraph4.png")    

    Elements.append(Image('images/SampleGraph4.png', 270*.9, 127*.9))
    Elements.append(UseUpSpace())

    # populate account number

    accountNumber = [
        [Paragraph("Account Number", styles['BillLabel']), Paragraph(str(dom.utilitybill.account), styles['BillField'])], 
    ]
    
    t = Table(accountNumber, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    #fits perfectly
    #Elements.append(UseUpSpace())

    # populate due date and amount
    dueDateAndAmount = [
        [Paragraph("Due Date", styles['BillLabel']), Paragraph(str(dom.utilitybill.skylinebill.duedate), styles['BillFieldRight'])], 
        [Paragraph("Total Amount", styles['BillLabel']), Paragraph(str(dom.utilitybill.skylinebill.totaldue), styles['BillFieldRight'])]
    ]
    
    t = Table(dueDateAndAmount, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())
    
    # populate service address
    Elements.append(Spacer(100,20))
    Elements.append(Paragraph(str(dom.utilitybill.car.serviceaddress.addressee), styles['BillField']))
    Elements.append(Paragraph(str(dom.utilitybill.car.serviceaddress.street), styles['BillField']))
    Elements.append(Paragraph(str(dom.utilitybill.car.serviceaddress.city) + " " + str(dom.utilitybill.car.serviceaddress.state) + " " + str(dom.utilitybill.car.serviceaddress.postalcode), styles['BillField']))
    Elements.append(UseUpSpace())

    # populate special instructions
    Elements.append(Paragraph("There are no special instructions", styles['BillField']))
    Elements.append(UseUpSpace())
    
    # populate billing address
    Elements.append(Spacer(100,20))
    Elements.append(Paragraph(str(dom.utilitybill.car.billingaddress.addressee), styles['BillField']))
    Elements.append(Paragraph(str(dom.utilitybill.car.billingaddress.street), styles['BillField']))
    Elements.append(Paragraph(str(dom.utilitybill.car.billingaddress.city) + " " + str(dom.utilitybill.car.billingaddress.state) + " " + str(dom.utilitybill.car.billingaddress.postalcode), styles['BillField']))
    Elements.append(UseUpSpace())
    
    
    

    #
    # Second Page
    #
    Elements.append(NextPageTemplate("SecondPage"));
    Elements.append(PageBreak());


    pageTwoBackground = Image('images/EmeraldCityBackground2.png',letter[0], letter[1])
    Elements.append(pageTwoBackground)

    Elements.append(Paragraph("Your utility bill without Skyline.  Consult actual utility bill to see savings.", styles['BillLabel']))
    Elements.append(UseUpSpace())

    # list of the rows
    chargeDetails = [
        ["Service", "Charge Description", "Quantity","", "Rate","", "Total"],
        [None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None]
    ]
    # sentinal for not printing service string each iteration
    service = None

    for details in (dom.utilitybill.details):
        for chargegroup in (details.chargegroup):
            for charges in (chargegroup.charges):
                if charges.type == u'hypothetical':
                    for charge in (charges.charge):
                        # populate service cell once for each group of services
                        if(service != details.service):
                            serviceStr = str(details.service)
                            service = details.service
                        description = charge.description if (charge.description is not None) else ""
                        quantity = charge.quantity if (charge.quantity is not None) else ""
                        quantityUnits = charge.quantity.units if (charge.quantity is not None) else ""
                        rate = charge.rate  if (charge.rate is not None) else ""
                        rateUnits = charge.rate.units if (charge.rate is not None) else ""
                        total = charge.total
                        chargeDetails.append([serviceStr, str(description), str(quantity), str(quantityUnits), str(rate), str(rateUnits), str(total)])
                        # clear string so that it gets set on next service type
                        serviceStr = None
        for total in iter(details.total):
            if(total.type == u'hypothetical'):
                chargeDetails.append([None, None, None, None, None, None, str(total)])
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

     
if __name__ == "__main__":  
    go()
