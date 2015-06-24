#!/usr/bin/env python
import sys
import os  
from decimal import *
from datetime import datetime
from argparse import ArgumentParser
import logging
from collections import deque

from pyPdf import PdfFileWriter, PdfFileReader

import reportlab  
from reportlab.platypus import BaseDocTemplate, Paragraph, Table, LongTable, TableStyle, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace, KeepTogether
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

import csv

# Important for currency formatting
import locale
locale.setlocale(locale.LC_ALL, '')

def round_for_display(x, places=2):
    '''Rounds the float 'x' for display as dollars according to the previous
    behavior in render.py using Decimals, which was to round to the nearest
    cent (.005 up to .01). If 'places' is given, a different number of decimal
    places can be used.
    '''
    return round(x * 10**places) / float(10**places)

def format_for_display(x, places=2):
    '''Formats the float 'x' for display as dollars by rounding it to the given
    number of places (default 2) and displaying as a string right-padded with
    0s to that many places.
    '''
    return ('%%.%sf' % places) % round_for_display(x, places)

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

class BillDoc(BaseDocTemplate):
    """Structure Skyline Innovations Bill. """
    #
    # Globals
    #
    #defaultPageSize = letter
    #PAGE_HEIGHT=letter[1]; PAGE_WIDTH=letter[0]
    #Title = "Skyline Bill"
    #pageinfo = "Skyline Bill"
    page_names = []

    def __init__(self):
        """
        Config should be a dict of configuration keys and values.
        """
        # TODO Reportlab base class is old-style class
        #super(BillDoc, self).__init__("./basedoctemplate.pdf", pagesize=letter, showBoundary=0, allowSplitting=0)
        # TODO poor design of base class requires filename on __init__
        # Here, the filename is passed in on render()
        # TODO filesep
        #BaseDocTemplate.__init__(self, "%s/%s" % (output_directory, output_name), pagesize=letter, showBoundary=0, allowSplitting=0)
        BaseDocTemplate.__init__(self, "basedoctemplate.pdf", pagesize=letter, showBoundary=0, allowSplitting=0)

    def _load_fonts(self):

        # TODO make font directories relocatable
        rptlab_folder = os.path.join(os.path.dirname(reportlab.__file__), 'fonts')
        our_fonts = os.path.join(os.path.join(self.skin_directory, 'fonts/'))

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

        #register Inconsolata
        pdfmetrics.registerFont(TTFont("Inconsolata", os.path.join(our_fonts,'Inconsolata.ttf')))
        pdfmetrics.registerFont(TTFont("Inconsolata-Bold", os.path.join(our_fonts,'Inconsolata-Bold.ttf')))
        registerFontFamily('Inconsolata', 
                            normal = 'Inconsolata', 
                            bold = 'Inconsolata-Bold',
                            italic = 'Inconsolata')

        pdfmetrics.registerFont(TTFont('BryantBd', os.path.join(our_fonts, os.path.join('Bryant', 'Bryant-BoldAlternate.ttf'))))
        pdfmetrics.registerFont(TTFont('BryantLA', os.path.join(our_fonts, os.path.join('Bryant', 'Bryant-LightAlternate.ttf'))))
        pdfmetrics.registerFont(TTFont('BryantMA', os.path.join(our_fonts, os.path.join('Bryant', 'Bryant-MediumAlternate.ttf'))))
        pdfmetrics.registerFont(TTFont('BryantRA', os.path.join(our_fonts, os.path.join('Bryant', 'Bryant-RegularAlternate.ttf'))))
        registerFontFamily('Bryant',normal='BryantRA',bold='BryantBd',italic='',boldItalic='')

        pdfmetrics.registerFont(TTFont('AvenirBd', os.path.join(our_fonts, os.path.join('Avenir', 'AvenirNext-Bold.ttf'))))
        pdfmetrics.registerFont(TTFont('AvenirI', os.path.join(our_fonts, os.path.join('Avenir', 'AvenirNext-Italic.ttf'))))
        pdfmetrics.registerFont(TTFont('AvenirBI', os.path.join(our_fonts, os.path.join('Avenir', 'AvenirNext-BoldItalic.ttf'))))
        pdfmetrics.registerFont(TTFont('Avenir', os.path.join(our_fonts, os.path.join('Avenir', 'AvenirNext-Regular.ttf'))))
        registerFontFamily('Avenir',normal='Avenir',bold='AvenirBd',italic='AvenirI',boldItalic='AvenirBI')


    def _set_styles(self):

        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(name='BillLabel', fontName='AvenirBd', fontSize=10, leading=10))
        self.styles.add(ParagraphStyle(name='BillLabelRight', fontName='AvenirBd', fontSize=10, leading=10, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillLabelLg', fontName='AvenirBd', fontSize=16, leading=14))
        self.styles.add(ParagraphStyle(name='BillLabelLgRight', fontName='AvenirBd', fontSize=12, leading=14, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillLabelSm', fontName='AvenirBd', fontSize=8, leading=8))
        self.styles.add(ParagraphStyle(name='BillLabelExSm', fontName='AvenirBd', fontSize=6, leading=8))
        self.styles.add(ParagraphStyle(name='BillLabelMicro', fontName='AvenirBd', fontSize=5, leading=8))
        self.styles.add(ParagraphStyle(name='BillLabelSmRight', fontName='AvenirBd', fontSize=8, leading=8, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillLabelSmCenter', fontName='AvenirBd', fontSize=8, leading=8, alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='GraphLabel', fontName='AvenirBd', fontSize=6, leading=6))
        self.styles.add(ParagraphStyle(name='BillText', fontName='BryantRA', fontSize=10, leading=10, alignment=TA_LEFT))
        self.styles.add(ParagraphStyle(name='BillField', fontName='BryantMA', fontSize=10, leading=10, alignment=TA_LEFT))
        self.styles.add(ParagraphStyle(name='BillFieldLg', fontName='BryantMA', fontSize=14, leading=14, alignment=TA_LEFT))
        self.styles.add(ParagraphStyle(name='BillFieldLgBold', fontName='BryantBd', fontSize=16, leading=14, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillFieldRight', fontName='BryantMA', fontSize=10, leading=10, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillFieldLeft', fontName='BryantMA', fontSize=10, leading=10, alignment=TA_LEFT))
        self.styles.add(ParagraphStyle(name='BillFieldSm', fontName='BryantMA', fontSize=8, leading=8, alignment=TA_LEFT))
        self.styles.add(ParagraphStyle(name='BillFieldExSm', fontName='BryantMA', fontSize=6, leading=8, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillFieldSmRight', fontName='BryantMA', fontSize=8, leading=8, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillFieldMicroRight', fontName='BryantMA', fontSize=5, leading=8, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillLabelFake', fontName='VerdanaB', fontSize=8, leading=8, textColor=colors.white))


    # NOTE: this should not be public but it can't be changed due to definition in ReportLab
    def afterPage(self):
#        if self.pageTemplate.id == self.page_names[0]:
#            self.canv.saveState()
#            #self.canv.setStrokeColorRGB(32,32,32)
#            #self.canv.setLineWidth(.05)
#            #self.canv.setDash(1,3)
#            #self.canv.line(0,537,612,537)
#            #self.canv.line(0,264,612,264)
#            self.canv.restoreState()
#        if self.pageTemplate.id == self.page_names[1]:
#            self.canv.saveState()
#            #self.canv.setStrokeColorRGB(0,0,0)
#            #self.canv.setLineWidth(.05)
#            #self.canv.setDash(1,3)
#            #self.canv.line(0,264,612,264)
#            self.canv.restoreState()
        pass

    # NOTE: this should not be public but it can't be changed due to definition in ReportLab
    def handle_pageBegin(self):
        BaseDocTemplate.handle_pageBegin(self)

    # Staples envelope (for send)
    # #10 (4-1/8" (297pt)  x 9-1/2")
    # Left window position fits standard formats
    # Window size: 1-1/8" x 4-1/2" (324pt)
    # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom

    # canvas: x,y,612w,792h w/ origin bottom left
    # 72 dpi
    # frame (x,y,w,h)

    # Staples envelope (for return)
    # #9 standard invoice (3-7/8" (279pt) x 8-7/8" (639pt))
    # Left window position fits standard formats
    # Window size: 1-1/8" (81pt) x 4-1/2" (324pt)
    # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom
        # Staples envelope (for bill return)
        # #9 standard invoice (3-7/8" (279pt) x 8-7/8" (639pt))
        # Left window position fits standard formats
        # Window size: 1-1/8" (81pt) x 4-1/2" (324pt)
        # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom

    # Fanfolds
    # Top Y 528
    # Middle y 264
    # Bottom Y 0

    def _assemble_pages(self):
        pages = []
        for i, frames in enumerate(self._page_frames()):
            pages.append(PageTemplate(id=self.page_names[i], frames=frames))

        self.addPageTemplates(pages)

    # NOTE: this should not be public but it can't be changed due to definition in ReportLab
    def build(self, flowables):
        """build the document using the _flowables while drawing lines and figures on top of them."""

        # TODO: 17377331 - find out why the failure is silent
        BaseDocTemplate.build(self, flowables, canvasmaker=canvas.Canvas)

    def render(self, data, output_directory, output_name, skin_directory, skin_name, fields = None):
        self.filename = os.path.join("%s", "%s") % (output_directory, output_name)
        self.skin_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), skin_directory)
        self.skin = skin_name
        self.fields = fields
        self._load_fonts()
        self._set_styles()
        self._assemble_pages()
        self.build(self._flowables(data))

class ThermalBillDoc(BillDoc):

    page_names = ['First Page', 'Second Page']

    def _page_frames(self):

        _showBoundaries = 0

        # canvas: x,y,612w,792h w/ origin bottom left
        # 72 dpi
        # frame (x,y,w,h)

        #page one frames; divided into three sections:  Summary, graphs, Charge Details

        backgroundF1 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background1', showBoundary=_showBoundaries)

        # section 1/3 (612)w x (792pt-279pt=)h (to fit #9 envelope)

        billPeriodTableF = Frame(36, 167, 241, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billPeriod', showBoundary=_showBoundaries)


        # Customer service address Frame
        serviceAddressF = Frame(371, 570, 227, 80, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='serviceAddress', showBoundary=_showBoundaries)

        # Staples envelope (for bill send)
        # #10 (4-1/8" (297pt)  x 9-1/2")
        # Left window position fits standard formats
        # Window size: 1-1/8" x 4-1/2" (324pt)
        # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom

        # Customer billing address frame
        #billingAddressF = Frame(78, 600, 250, 60, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)
        billingAddressF = Frame(38, 570, 330, 80, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)

        # section 2/3

        # section 3/3

        # summary background block
        summaryBackgroundF = Frame(141, 75, 443, 152, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryBackground', showBoundary=_showBoundaries)

        # Skyline Account number frame
        billIdentificationF = Frame(0, 657, 227, 37, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='accountNumber', showBoundary=_showBoundaries)

        # Due date and Amount and remit to  frame
        amountDueF = Frame(230, 657, 360, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)

        # summary charges block
        summaryChargesTableF = Frame(328, 167, 252, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryCharges', showBoundary=_showBoundaries)

        # balance block
        balanceF = Frame(77, 105, 265, 50, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balance', showBoundary=_showBoundaries)

        # adjustments block
        adjustmentsF = Frame(77, 64, 265, 50, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='adjustments', showBoundary=_showBoundaries)

        # current charges block
        # your savings and renewable charges
        currentChargesF = Frame(360, 108, 220, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='currentCharges', showBoundary=_showBoundaries)

        # balance forward block
        balanceForwardF = Frame(360, 75, 220, 21, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balance', showBoundary=_showBoundaries)

        # balance due block
        balanceDueF = Frame(360, 41, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balanceDue', showBoundary=_showBoundaries)

        # build page container for _flowables to populate
        firstPage = [backgroundF1, billIdentificationF, amountDueF, serviceAddressF, billingAddressF, summaryBackgroundF, billPeriodTableF, summaryChargesTableF, balanceF, adjustmentsF, currentChargesF, balanceForwardF, balanceDueF]

        # page two frames

        # page two background frame
        backgroundF2 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background2', showBoundary=_showBoundaries)


        # Measured Usage header frame
        measuredUsageHeaderF = Frame(30, 500, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='measuredUsageHeader', showBoundary=_showBoundaries)

        # measured usage meter summaries
        measuredUsageF = Frame(30, 400, 550, 105, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billableUsage', showBoundary=_showBoundaries)

        # Charge details header frame
        chargeDetailsHeaderF = Frame(30, 350, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetailsHeader', showBoundary=_showBoundaries)

        # charge details frame
        chargeDetailsF = Frame(30, 1, 550, 350, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)

        # build page container for _flowables to populate
        #secondPage = PageTemplate(id=secondPageName,frames=[backgroundF2, measuredUsageHeaderF, measuredUsageF, chargeDetailsHeaderF, chargeDetailsF])
        secondPage = [backgroundF2, measuredUsageHeaderF, measuredUsageF, chargeDetailsHeaderF, chargeDetailsF]

        return [firstPage, secondPage]

    def _flowables(self, bill_data):

        b = bill_data[-1]

        fl = []

        s = self.styles

        #
        # First Page
        #

        # populate backgroundF1
        pageOneBackground = Image(os.path.join(os.path.join(self.skin_directory, self.skin), "page_one.png"),letter[0], letter[1])

        fl.append(pageOneBackground)

        # populate account number, bill id & issue date
        issue_date = b["issue_date"]
        accountNumber = [
            [Paragraph("Account Number", s['BillLabelRight']),Paragraph(
                b["account"] + " " + str(b["sequence"]),s['BillField'])],
            [Paragraph("Issue Date", s['BillLabelRight']), Paragraph(issue_date.strftime('%m-%d-%Y') if issue_date is not None else 'None', s['BillField'])]
        ]

        t = Table(accountNumber, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        #fits perfectly
        #fl.append(UseUpSpace())

        # populate due date and amount
        dueDateAndAmount = [
            [Paragraph("Due Date", s['BillLabelRight']), Paragraph(b["due_date"]
            .strftime('%m-%d-%Y') if b["due_date"] is not None
            else 'None', s['BillFieldRight'])],
            [Paragraph("Balance Due", s['BillLabelRight']), Paragraph(
                format_for_display(b["balance_due"]), s['BillFieldRight'])],
            [Paragraph("Remit Payment To", s['BillLabelRight']), Paragraph(
                b["payment_payee"] if b['payment_payee'] is not None else '' ,
                s['BillFieldRight'])]
        ]

        t = Table(dueDateAndAmount, [135,160])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate service address
        fl.append(Spacer(100,10))
        fl.append(Paragraph("Service Location", s['BillLabel']))

        fl.append(Paragraph(b["service_addressee"], s['BillField']))
        fl.append(Paragraph(b["service_street"], s['BillField']))
        fl.append(Paragraph(" ".join((b["service_city"], b["service_state"], b["service_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())

        # populate special instructions
        #fl.append(Spacer(50,50))
        #fl.append(UseUpSpace())

        # populate billing address
        fl.append(Spacer(100,20))
        fl.append(Paragraph(b["billing_addressee"], s['BillFieldLg']))
        fl.append(Paragraph(b["billing_street"], s['BillField']))
        #fl.append(Paragraph(" ".join((b["billing_city"], b["billing_state"], b["billing_postal_code"])), s['BillFieldLg']))
        fl.append(Paragraph(" ".join((b["billing_city"], b["billing_state"], b["billing_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())

        # populate summary background
        fl.append(Image(os.path.join(self.skin_directory,'images','SummaryBackground.png'), 443, 151))
        fl.append(UseUpSpace())

        # populate billPeriodTableF
        # spacer so rows can line up with those in summarChargesTableF rows
        #periods=reebill_document.renewable_energy_period()
        serviceperiod = [
                [Paragraph("spacer", s['BillLabelFake']), Paragraph("spacer", s['BillLabelFake']), Paragraph("spacer", s['BillLabelFake'])],
                [Paragraph("", s['BillLabelSm']), Paragraph("From", s['BillLabelSm']), Paragraph("To", s['BillLabelSm'])]
            ] + [
                [
                    Paragraph( u' service',s['BillLabelSmRight']),
                    Paragraph(b["begin_period"].strftime('%m-%d-%Y'), s['BillFieldRight']),
                    Paragraph(b["end_period"].strftime('%m-%d-%Y'), s['BillFieldRight'])
                ]
            ]

        t = Table(serviceperiod, colWidths=[115,70,70])

        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'CENTER'), ('ALIGN',(2,0),(2,-1),'CENTER'), ('RIGHTPADDING', (0,2),(0,-1), 8), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,2), (-1,-1), 0.25, colors.black), ('BOX', (1,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,2),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        utilitycharges = [
            [Paragraph("Your Utility Charges", s['BillLabelSmCenter']),Paragraph("", s['BillLabelSm']),Paragraph("Green Energy", s['BillLabelSmCenter'])],
            [Paragraph("w/o Renewable", s['BillLabelSmCenter']),Paragraph("w/ Renewable", s['BillLabelSmCenter']),Paragraph("Value", s['BillLabelSmCenter'])]
        ]+[
            [
                Paragraph(str(format_for_display(b["hypothetical_charges"])),s['BillFieldRight']),
                Paragraph(str(format_for_display(b["total_utility_charges"])),s['BillFieldRight']),
                Paragraph(str(format_for_display(b["ree_value"])),s['BillFieldRight'])
            ]
        ]

        t = Table(utilitycharges, colWidths=[84,84,84])

        t.setStyle(TableStyle([('SPAN', (0,0), (1,0)), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,2), (-1,-1), 0.25, colors.black), ('BOX', (0,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,2),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate balances
        balances = [
            [Paragraph("Prior Balance", s['BillLabelRight']), Paragraph(
                str(format_for_display(b["prior_balance"])),s[
                    'BillFieldRight'])],
            [Paragraph("Payment Received", s['BillLabelRight']),
                Paragraph(str(format_for_display(b["payment_received"])),
                    s['BillFieldRight'])]
        ]

        t = Table(balances, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate adjustments
        manual_adjustments = b["manual_adjustment"]
        other_adjustments = b["total_adjustment"]
        adjustments = [
            [Paragraph("Manual Adjustments", s['BillLabelRight']), Paragraph(str(format_for_display(manual_adjustments)), s['BillFieldRight'])],
            [Paragraph("Other Adjustments", s['BillLabelRight']), Paragraph(str(format_for_display(other_adjustments)), s['BillFieldRight'])]
        ]

        t = Table(adjustments, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())


        try:
            # populate current charges
            late_charges = b["late_charge"]
        except KeyError:
            late_charges = None

        # depiction of conditional template logic based on ReeBill returning None
        # we will want to distinguish between a late charge, a zero dollar late charge and no late charge
        # to allow the template to do fancy formatting
        if late_charges is not None:
            currentCharges = [
                [Paragraph("Your Savings", s['BillLabelRight']), Paragraph(str(format_for_display(b["ree_savings"])), s['BillFieldRight'])],
                [Paragraph("Renewable Charges", s['BillLabelRight']), Paragraph(str(format_for_display(b["ree_charge"])), s['BillFieldRight'])],
                [Paragraph("Late Charges", s['BillLabelRight']), Paragraph(str(format_for_display(late_charges)), s['BillFieldRight'])]
            ]
        else:
            currentCharges = [
                [Paragraph("Your Savings", s['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_savings)), s['BillFieldRight'])],
                [Paragraph("Renewable Charges", s['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_charge)), s['BillFieldRight'])],
                [Paragraph("Late Charges", s['BillLabelRight']), Paragraph(str("n/a"), s['BillFieldRight'])]
            ]

        t = Table(currentCharges, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate balanceForward
        balance = [
            [Paragraph("Balance Forward", s['BillLabelRight']), Paragraph(str(format_for_display(b["balance_forward"])), s['BillFieldRight'])]
        ]

        t = Table(balance, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())


        # populate balanceDueFrame
        balanceDue = [
            [Paragraph("Balance Due", s['BillLabelLgRight']), Paragraph(str(format_for_display(b["balance_due"])), s['BillFieldRight'])]
        ]

        t = Table(balanceDue, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        #
        # Second Page
        #
        fl.append(NextPageTemplate(self.page_names[1]));
        fl.append(PageBreak());


        pageTwoBackground = Image(os.path.join(self.skin_directory, self.skin, "page_two.png"), letter[0], letter[1])
        fl.append(pageTwoBackground)

        #populate measured usage header frame
        fl.append(Paragraph("Measured renewable and conventional energy.", s['BillLabel']))
        fl.append(UseUpSpace())

        # list of the rows
        measuredUsage = [
            ["Utility Register", "Description", "Quantity", "", "",""],
            [None, None, "Renewable", "Utility", "Total", None],
            [None, None, None, None,  None, None,]
        ]
        for meter in b["utility_meters"]:
            for register in meter["registers"]:
                measuredUsage.append([
                   "%s %s" % (meter["meter_id"], register["register_id"]),
                   register["description"],
                   register["shadow_total"],
                   register["utility_total"],
                   register["total"],
                   register["quantity_units"]
                ])

        # Load registers and match up shadow registers to actual registers
#        assert len(reebill.utilbills)==1
#        shadow_registers = reebill_document.get_all_shadow_registers_json()
#        utilbill_doc=self._reebill_dao.load_doc_for_utilbill(reebill.utilbills[0])
#        actual_registers = mongo.get_all_actual_registers_json(
#           utilbill_doc)
#        for s_register in shadow_registers:
#            total = 0
#            for a_register in actual_registers:
#                if s_register['register_binding'] == a_register['binding']:
#                    shadow_total = s_register['quantity']
#                    utility_total = a_register['quantity']
#                    total += (utility_total + shadow_total)
#                    measuredUsage.append([
#                        a_register['meter_id'],
#                        a_register['description'],
#                        round_for_display(shadow_total),
#                        utility_total,
#                        round_for_display(total),
#                        a_register['quantity_units']
#                    ])
#


        measuredUsage.append([None, None, None, None, None, None])

class ThermalBillDoc(BillDoc):

    page_names = ['First Page', 'Second Page']

    def _page_frames(self):

        _showBoundaries = 0

        # canvas: x,y,612w,792h w/ origin bottom left
        # 72 dpi
        # frame (x,y,w,h)

        #page one frames; divided into three sections:  Summary, graphs, Charge Details

        backgroundF1 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background1', showBoundary=_showBoundaries)

        # section 1/3 (612)w x (792pt-279pt=)h (to fit #9 envelope) 

        billPeriodTableF = Frame(36, 167, 241, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billPeriod', showBoundary=_showBoundaries)


        # Customer service address Frame
        serviceAddressF = Frame(371, 570, 227, 80, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='serviceAddress', showBoundary=_showBoundaries)

        # Staples envelope (for bill send)
        # #10 (4-1/8" (297pt)  x 9-1/2")
        # Left window position fits standard formats
        # Window size: 1-1/8" x 4-1/2" (324pt)
        # Window placement: 7/8" (63pt) from left and 1/2" (36pt) from bottom

        # Customer billing address frame
        #billingAddressF = Frame(78, 600, 250, 60, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)
        billingAddressF = Frame(38, 570, 330, 80, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)

        # section 2/3

        # section 3/3

        # summary background block
        summaryBackgroundF = Frame(141, 75, 443, 152, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryBackground', showBoundary=_showBoundaries)

        # Skyline Account number frame
        billIdentificationF = Frame(0, 657, 227, 37, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='accountNumber', showBoundary=_showBoundaries)

        # Due date and Amount and remit to  frame
        amountDueF = Frame(230, 657, 360, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)

        # summary charges block
        summaryChargesTableF = Frame(328, 167, 252, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryCharges', showBoundary=_showBoundaries)

        # balance block
        balanceF = Frame(77, 105, 265, 50, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balance', showBoundary=_showBoundaries)

        # adjustments block
        adjustmentsF = Frame(77, 64, 265, 50, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='adjustments', showBoundary=_showBoundaries)

        # current charges block
        # your savings and renewable charges
        currentChargesF = Frame(360, 108, 220, 55, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='currentCharges', showBoundary=_showBoundaries)

        # balance forward block
        balanceForwardF = Frame(360, 75, 220, 21, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balance', showBoundary=_showBoundaries)

        # balance due block
        balanceDueF = Frame(360, 41, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balanceDue', showBoundary=_showBoundaries)

        # build page container for _flowables to populate
        firstPage = [backgroundF1, billIdentificationF, amountDueF, serviceAddressF, billingAddressF, summaryBackgroundF, billPeriodTableF, summaryChargesTableF, balanceF, adjustmentsF, currentChargesF, balanceForwardF, balanceDueF]

        # page two frames

        # page two background frame
        backgroundF2 = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background2', showBoundary=_showBoundaries)


        # Measured Usage header frame
        measuredUsageHeaderF = Frame(30, 500, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='measuredUsageHeader', showBoundary=_showBoundaries)

        # measured usage meter summaries
        measuredUsageF = Frame(30, 400, 550, 105, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billableUsage', showBoundary=_showBoundaries)

        # Charge details header frame
        chargeDetailsHeaderF = Frame(30, 350, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetailsHeader', showBoundary=_showBoundaries)

        # charge details frame
        chargeDetailsF = Frame(30, 1, 550, 350, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)

        # build page container for _flowables to populate
        #secondPage = PageTemplate(id=secondPageName,frames=[backgroundF2, measuredUsageHeaderF, measuredUsageF, chargeDetailsHeaderF, chargeDetailsF])
        secondPage = [backgroundF2, measuredUsageHeaderF, measuredUsageF, chargeDetailsHeaderF, chargeDetailsF]

        return [firstPage, secondPage]

    def _flowables(self, bill_data):

        b = bill_data[-1]

        fl = []

        s = self.styles 

        #
        # First Page
        #

        # populate backgroundF1
        pageOneBackground = Image(os.path.join(os.path.join(self.skin_directory, self.skin), "page_one.png"),letter[0], letter[1])

        fl.append(pageOneBackground)

        # populate account number, bill id & issue date
        issue_date = b["issue_date"]
        accountNumber = [
            [Paragraph("Account Number", s['BillLabelRight']),Paragraph(
                b["account"] + " " + str(b["sequence"]),s['BillField'])],
            [Paragraph("Issue Date", s['BillLabelRight']), Paragraph(issue_date.strftime('%m-%d-%Y') if issue_date is not None else 'None', s['BillField'])]
        ]

        t = Table(accountNumber, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        #fits perfectly
        #fl.append(UseUpSpace())

        # populate due date and amount
        dueDateAndAmount = [
            [Paragraph("Due Date", s['BillLabelRight']), Paragraph(b["due_date"]
            .strftime('%m-%d-%Y') if b["due_date"] is not None
            else 'None', s['BillFieldRight'])],
            [Paragraph("Balance Due", s['BillLabelRight']), Paragraph(
                format_for_display(b["balance_due"]), s['BillFieldRight'])],
            [Paragraph("Remit Payment To", s['BillLabelRight']), Paragraph(
                b["payment_payee"] if b['payment_payee'] is not None else '' ,
                s['BillFieldRight'])]
        ]
        
        t = Table(dueDateAndAmount, [135,160])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())
        
        # populate service address
        fl.append(Spacer(100,10))
        fl.append(Paragraph("Service Location", s['BillLabel']))

        fl.append(Paragraph(b["service_addressee"], s['BillField']))
        fl.append(Paragraph(b["service_street"], s['BillField']))
        fl.append(Paragraph(" ".join((b["service_city"], b["service_state"], b["service_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())

        # populate special instructions
        #fl.append(Spacer(50,50))
        #fl.append(UseUpSpace())
        
        # populate billing address
        fl.append(Spacer(100,20))
        fl.append(Paragraph(b["billing_addressee"], s['BillFieldLg']))
        fl.append(Paragraph(b["billing_street"], s['BillField']))
        #fl.append(Paragraph(" ".join((b["billing_city"], b["billing_state"], b["billing_postal_code"])), s['BillFieldLg']))
        fl.append(Paragraph(" ".join((b["billing_city"], b["billing_state"], b["billing_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())

        # populate summary background
        fl.append(Image(os.path.join(self.skin_directory,'images','SummaryBackground.png'), 443, 151))
        fl.append(UseUpSpace())

        # populate billPeriodTableF
        # spacer so rows can line up with those in summarChargesTableF rows
        #periods=reebill_document.renewable_energy_period()
        serviceperiod = [
                [Paragraph("spacer", s['BillLabelFake']), Paragraph("spacer", s['BillLabelFake']), Paragraph("spacer", s['BillLabelFake'])],
                [Paragraph("", s['BillLabelSm']), Paragraph("From", s['BillLabelSm']), Paragraph("To", s['BillLabelSm'])]
            ] + [
                [
                    Paragraph( u' service',s['BillLabelSmRight']), 
                    Paragraph(b["begin_period"].strftime('%m-%d-%Y'), s['BillFieldRight']),
                    Paragraph(b["end_period"].strftime('%m-%d-%Y'), s['BillFieldRight'])
                ] 
            ]

        t = Table(serviceperiod, colWidths=[115,70,70])

        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'CENTER'), ('ALIGN',(2,0),(2,-1),'CENTER'), ('RIGHTPADDING', (0,2),(0,-1), 8), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,2), (-1,-1), 0.25, colors.black), ('BOX', (1,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,2),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        utilitycharges = [
            [Paragraph("Your Utility Charges", s['BillLabelSmCenter']),Paragraph("", s['BillLabelSm']),Paragraph("Green Energy", s['BillLabelSmCenter'])],
            [Paragraph("w/o Renewable", s['BillLabelSmCenter']),Paragraph("w/ Renewable", s['BillLabelSmCenter']),Paragraph("Value", s['BillLabelSmCenter'])]
        ]+[
            [
                Paragraph(str(format_for_display(b["hypothetical_charges"])),s['BillFieldRight']),
                Paragraph(str(format_for_display(b["total_utility_charges"])),s['BillFieldRight']),
                Paragraph(str(format_for_display(b["ree_value"])),s['BillFieldRight'])
            ]
        ]

        t = Table(utilitycharges, colWidths=[84,84,84])

        t.setStyle(TableStyle([('SPAN', (0,0), (1,0)), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,2), (-1,-1), 0.25, colors.black), ('BOX', (0,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,2),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate balances
        balances = [
            [Paragraph("Prior Balance", s['BillLabelRight']), Paragraph(
                str(format_for_display(b["prior_balance"])),s[
                    'BillFieldRight'])],
            [Paragraph("Payment Received", s['BillLabelRight']),
                Paragraph(str(format_for_display(b["payment_received"])),
                    s['BillFieldRight'])]
        ]

        t = Table(balances, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate adjustments
        manual_adjustments = b["manual_adjustment"]
        other_adjustments = b["total_adjustment"]
        adjustments = [
            [Paragraph("Manual Adjustments", s['BillLabelRight']), Paragraph(str(format_for_display(manual_adjustments)), s['BillFieldRight'])],
            [Paragraph("Other Adjustments", s['BillLabelRight']), Paragraph(str(format_for_display(other_adjustments)), s['BillFieldRight'])]
        ]
        
        t = Table(adjustments, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())


        try:
            # populate current charges
            late_charges = b["late_charge"]
        except KeyError:
            late_charges = None

        # depiction of conditional template logic based on ReeBill returning None
        # we will want to distinguish between a late charge, a zero dollar late charge and no late charge
        # to allow the template to do fancy formatting
        if late_charges is not None:
            currentCharges = [
                [Paragraph("Your Savings", s['BillLabelRight']), Paragraph(str(format_for_display(b["ree_savings"])), s['BillFieldRight'])],
                [Paragraph("Renewable Charges", s['BillLabelRight']), Paragraph(str(format_for_display(b["ree_charge"])), s['BillFieldRight'])],
                [Paragraph("Late Charges", s['BillLabelRight']), Paragraph(str(format_for_display(late_charges)), s['BillFieldRight'])]
            ]
        else:
            currentCharges = [
                [Paragraph("Your Savings", s['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_savings)), s['BillFieldRight'])],
                [Paragraph("Renewable Charges", s['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_charge)), s['BillFieldRight'])],
                [Paragraph("Late Charges", s['BillLabelRight']), Paragraph(str("n/a"), s['BillFieldRight'])]
            ]

        t = Table(currentCharges, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # populate balanceForward
        balance = [
            [Paragraph("Balance Forward", s['BillLabelRight']), Paragraph(str(format_for_display(b["balance_forward"])), s['BillFieldRight'])]
        ]

        t = Table(balance, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())


        # populate balanceDueFrame
        balanceDue = [
            [Paragraph("Balance Due", s['BillLabelLgRight']), Paragraph(str(format_for_display(b["balance_due"])), s['BillFieldRight'])]
        ]

        t = Table(balanceDue, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,0),(-1,-1),colors.white)]))
        fl.append(t)
        fl.append(UseUpSpace())

        #
        # Second Page
        #
        fl.append(NextPageTemplate(self.page_names[1]));
        fl.append(PageBreak());


        pageTwoBackground = Image(os.path.join(self.skin_directory, self.skin, "page_two.png"), letter[0], letter[1])
        fl.append(pageTwoBackground)

        #populate measured usage header frame
        fl.append(Paragraph("Measured renewable and conventional energy.", s['BillLabel']))
        fl.append(UseUpSpace())

        # list of the rows
        measuredUsage = [
            ["Utility Register", "Description", "Quantity", "", "",""],
            [None, None, "Renewable", "Utility", "Total", None],
            [None, None, None, None,  None, None,]
        ]
        for meter in b["utility_meters"]:
            for register in meter["registers"]:
                measuredUsage.append([
                   "%s %s" % (meter["meter_id"], register["register_id"]),
                   register["description"],
                   register["shadow_total"],
                   register["utility_total"],
                   register["total"],
                   register["quantity_units"]
                ])

        # Load registers and match up shadow registers to actual registers
#        assert len(reebill.utilbills)==1
#        shadow_registers = reebill_document.get_all_shadow_registers_json()
#        utilbill_doc=self._reebill_dao.load_doc_for_utilbill(reebill.utilbills[0])
#        actual_registers = mongo.get_all_actual_registers_json(
#           utilbill_doc)
#        for s_register in shadow_registers:
#            total = 0
#            for a_register in actual_registers:
#                if s_register['register_binding'] == a_register['binding']:
#                    shadow_total = s_register['quantity']
#                    utility_total = a_register['quantity']
#                    total += (utility_total + shadow_total)
#                    measuredUsage.append([
#                        a_register['meter_id'],
#                        a_register['description'],
#                        round_for_display(shadow_total),
#                        utility_total,
#                        round_for_display(total),
#                        a_register['quantity_units']
#                    ])
#


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

        fl.append(t)
        fl.append(UseUpSpace())


        fl.append(Paragraph("Original utility charges prior to renewable energy.", s['BillLabel']))
        fl.append(UseUpSpace())

        # list of the rows
        chargeDetails = [
            [None, "Charge Description", "Quantity","", "Rate","", "Total"],
            [None, None, None, None, None, None, None]
        ]

        for group, charges in b["hypothetical_chargegroups"].iteritems():
            for i, charge in enumerate(charges):
                if not i: chargeDetails.append([group, None, None, None, None, None, None])
                chargeDetails.append([
                    None,
                    charge["description"],
                    charge["quantity"],
                    # quantity units
                    None,
                    charge["rate"],
                    # rate units
                    None,
                    charge["total"],
                ])
        chargeDetails.append([None, None, None, None, None, None,
            format_for_display(
                b["hypothetical_charges"],
                places=2)
        ])


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

        fl.append(t)
        fl.append(UseUpSpace())

        return fl


class PVBillDoc(BillDoc):

    page_names = ['first', 'second']

    def _page_frames(self):
        """
        Returns list (all pages) of lists (each a page) of frames 
        """

        _showBoundaries = 0

        # first page frames
        fr1 = []

        #page one frames; divided into three sections:  Summary, graphs, Charge Details

        fr1.append(
            Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background1', showBoundary=_showBoundaries)
        )

        # service address
        fr1.append(
            Frame(125, 645, 195, 60, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='serviceAddress', showBoundary=_showBoundaries)
        )


        # Issue Date

        fr1.append(
            Frame(125, 620, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)
        )


        # Bill Period

        fr1.append(
            Frame(125, 595, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billPeriod', showBoundary=_showBoundaries)
        )

        # bill summary

        fr1.append(
            Frame(350, 595, 237, 120, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billSummary', showBoundary=_showBoundaries)
        )

        # amount due
        fr1.append(
            Frame(350, 550, 237, 45, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)
        )
       
        # How you are Saving

        fr1.append(
            Frame(25, 346, 281, 170, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='howSaving', showBoundary=_showBoundaries)
        )

        #
        # NEG monetized
        #

        # RE&E savings assertion

        # How you are Consuming

        fr1.append(
            Frame(311, 346, 276, 170, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='howConsuming', showBoundary=_showBoundaries)
        )


        fr1.append(
            Frame(25, 264, 562, 70, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='monthStrip', showBoundary=_showBoundaries)
        )
        # Remit Payment To:

        fr1.append(
            Frame(72, 50, 220, 80, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)
        )


        # amount due mailer

        # TODO: dollar value
        fr1.append(
            Frame(350, 136, 237, 80, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDueMailer', showBoundary=_showBoundaries)
        )

        # billing address

        fr1.append(
            Frame(360, 25, 227, 90, leftPadding=10, bottomPadding=0, rightPadding=0, topPadding=0, id='billingAddress', showBoundary=_showBoundaries)
        )

        # end page one frames


        # page two frames
        fr2 = []

        # page two background frame
        fr2.append(
            Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background2', showBoundary=_showBoundaries)
        )

        # Measured Usage header frame
        fr2.append(
            Frame(30, 500, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='measuredUsageHeader', showBoundary=_showBoundaries)
        )

        # measured usage meter summaries
        fr2.append(
            Frame(30, 400, 550, 105, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billableUsage', showBoundary=_showBoundaries)
        )

        # Charge details header frame
        fr2.append(
            Frame(30, 350, 550, 20, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetailsHeader', showBoundary=_showBoundaries)
        )

        # charge details frame
        fr2.append(
            Frame(30, 1, 550, 350, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='chargeDetails', showBoundary=_showBoundaries)
        )

        return [fr1, fr2]

    def _flowables(self, bill_data):
        """
        Returns list of _flowables for all pages
        """

        s = self.styles 

        b = bill_data[-1]

        # first page _flowables
        fl = []

        fl.append(
           Image(os.path.join(os.path.join(self.skin_directory, self.skin), "page_one.png"),letter[0], letter[1])
        )

        # 1/3 (612)w x (792pt-279pt=)h (to fit #9 envelope) 

        # service address

        fl.append(Paragraph("Service Location", s['BillLabel']))
        fl.append(Spacer(220,10))

        fl.append(Paragraph(b["service_addressee"], s['BillField']))
        fl.append(Paragraph(b["service_street"], s['BillField']))
        fl.append(Paragraph(" ".join((b["service_city"], b["service_state"], b["service_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())

        # Issue Date

        issue_date = b["issue_date"].strftime('%m-%d-%Y')

        issue_date_table_data = [
            [Paragraph("Billing Date", s['BillLabel']), Paragraph(issue_date, s['BillField'])]
        ]
        t = Table(issue_date_table_data, colWidths=[125,85])

        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # Bill Period

        period_begin = b["begin_period"].strftime('%m-%d-%Y')
        period_end = b["end_period"].strftime('%m-%d-%Y')
         
        billing_period_table_data = [
            [Paragraph("Billing Period", s['BillLabel']), Paragraph(period_begin, s['BillField']), Paragraph(period_end, s['BillField'])]
        ]
        t = Table(billing_period_table_data, colWidths=[90, 70, 70])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-3),'LEFT'), ('ALIGN',(1,0),(1,-2),'LEFT'), ('ALIGN', (2,0),(1,-1), 'LEFT'), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # bill summary

        # TODO manual adjustment
        bill_summary_table_data = [
            [Paragraph('Prior Balance', s['BillLabel']), Paragraph(locale.currency(b['prior_balance'],grouping=True), s['BillFieldRight'])],
            [Paragraph('Payments', s['BillLabel']), Paragraph(locale.currency(b['payment_received'],grouping=True), s['BillFieldRight'])],
            [Paragraph('Adjustments', s['BillLabel']), Paragraph(locale.currency(b['total_adjustment'],grouping=True), s['BillFieldRight'])],
            # conditional if there are late charges
            [Paragraph('Late Charges', s['BillLabel']),  Paragraph(locale.currency(b['late_charge'],grouping=True), s['BillFieldRight'])],
            [Paragraph('Balance Forward', s['BillLabel']), Paragraph(locale.currency(b['balance_forward'],grouping=True), s['BillFieldRight'])],
            [Paragraph('Current RE', s['BillLabel']), Paragraph(locale.currency(b['ree_charge'],grouping=True), s['BillFieldRight'])]
        ]
        if b['neg_ree_charge']:
            bill_summary_table_data.append([Paragraph('Prior RE (NEG)', s['BillLabel']), Paragraph(locale.currency(b['neg_ree_charge'],grouping=True), s['BillFieldRight'])])
        t = Table(bill_summary_table_data, colWidths=[135,102])
        t.setStyle(TableStyle([('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # amount due

        # TODO: dollar value
        amount_due = locale.currency(b["balance_due"], grouping=True)

        # TODO: large style
        amount_due_table_data = [
            [Paragraph("Amount Due", s['BillLabelLg']), Paragraph(amount_due, s['BillFieldLgBold'])]
        ]
        t = Table(amount_due_table_data, colWidths=[125,112])

        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (1,0),(-1,-1),6), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # How you are Saving

        #how_saving_table_data = [
        #    [Paragraph('How You Are Saving', s['BillLabel']), ''],
        #    ['Utility bill before solar', '$20,000'],
        #    ['Renewable energy bill', '$11,000'],
        #    ['Current utility bill', '$11,000'],
        #    ['Since you are saving at', 'X%'],
        #    ['You have saved', '$X,XXX']
        #]
        fl.append(Paragraph('How You Are Saving', s['BillLabel']))

        #
        # NEG monetized
        #

        # RE&E savings assertion
        fl.append(Spacer(281,5))
        fl.append(Paragraph(
            'Your utility bill would have been %s prior to solar. '
            'Your current utility bill is %s %s and the value '
            'of the renewable energy used is %s.   Since you have a Skyline discount '
            'of %s%% you have paid %s for renewable energy and have realized a savings '
            'of %s.'
            % (locale.currency(b['hypothetical_charges'], grouping=True),
            '(exclusive of NEG credit)' if b['neg_ree_charge'] else '',
            locale.currency(b['total_utility_charges'], grouping=True),
            locale.currency(b['ree_value'], grouping=True),
            (b['discount_rate']*100),
            locale.currency(b['ree_charge'], grouping=True),
            locale.currency(b['ree_savings'], grouping=True)), s['BillText']))

        if (b['neg_ree_savings']):
            # NEG savings assertion
            fl.append(Spacer(281,5))
            fl.append(Paragraph('A NEG credit of %s for the value of renewable '
            'energy that skyline previously sold to your utility has been applied '
            'to your utility bill.  Now that you\'ve used this credit, you have paid '
            '%s for renewable energy and have saved an additional %s dollars.'
                % (locale.currency(b['neg_credit_applied'], grouping=True),
                locale.currency(b['neg_ree_charge'], grouping=True),
                locale.currency(b['neg_ree_savings'], grouping=True)), s['BillText']))

        if (b['neg_ree_potential_savings']):
            # NEG Balance assertion 
            fl.append(Spacer(281,5))
            fl.append(Paragraph('You still have a NEG credit balance of %s '
            'dollars that has a potential savings of %s should that credit '
            'be used.' % (locale.currency(b['neg_credit_balance'], grouping=True),
            locale.currency(b['neg_ree_potential_savings'], grouping=True)), s['BillText']))

        fl.append(UseUpSpace())

        # How you are Consuming

        fl.append(Paragraph('How You Are Consuming (kWh)', s['BillLabel']))
        fl.append(Spacer(300,5))

        how_consuming_table_data = [
            [Paragraph('Renewable Energy Generated', s['BillText']), Paragraph('{:.0f}'.format(b['total_re_generated']), s['BillFieldRight'])],
            [Paragraph('Renewable Energy Consumed', s['BillText']), Paragraph('{:.0f}'.format(b['total_re_consumed']), s['BillFieldRight'])],
            [Paragraph('Conventional Energy Consumed', s['BillText']), Paragraph('{:.0f}'.format(b['total_ce_consumed']), s['BillFieldRight'])],
            [Paragraph('Total Energy Consumed', s['BillText']), Paragraph('{:.0f}'.format(b['total_energy_consumed']), s['BillFieldRight'])],
            [Paragraph('Renewable Energy Delivered to Grid', s['BillText']), Paragraph('{:.0f}'.format(b['total_re_delivered_grid']), s['BillFieldRight'])],
        ]

        t = Table(how_consuming_table_data, colWidths=[215,61])
        t.setStyle(TableStyle([('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        pad_monthss = range(13 - len(bill_data))

        # 13 month strip padding
        date_hdrs = [''] + ['' for i in pad_monthss]
        neg_credit_applied = [Paragraph('NEG Applied ($)', s['BillLabelMicro'])] + ['' for i in pad_monthss]
        neg_credit_balance = [Paragraph('NEG Balance ($)', s['BillLabelMicro'])] + ['' for i in pad_monthss]

        for i in bill_data:
            date_hdrs.append(Paragraph(i['begin_period'].strftime("%b %y"), s['BillLabelMicro']))
            neg_credit_applied.append(Paragraph(locale.currency(i['neg_credit_applied'], symbol=False), s['BillFieldMicroRight']))
            neg_credit_balance.append(Paragraph(locale.currency(i['neg_credit_balance'], symbol=False), s['BillFieldMicroRight']))

        # convert last date header to 'current'
        date_hdrs[-1] = Paragraph("Current", s['BillLabelMicro'])

        month_strip_table_data = [date_hdrs, neg_credit_applied, neg_credit_balance]

        t = Table(month_strip_table_data, colWidths=[68, 38])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,0),'RIGHT'), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # Remit Payment To:

        fl.append(Paragraph("Remit Payment To:", s['BillLabel']))
        fl.append(Spacer(220,10))
        fl.append(Paragraph(b["payment_payee"], s['BillField']))
        fl.append(Paragraph(b["payment_street"], s['BillField']))
        fl.append(Paragraph(" ".join((b["payment_city"], b["payment_state"], b["payment_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())


        # amount due mailer

        # TODO: dollar value
        amount_due = locale.currency(b["balance_due"], grouping=True)
        due_date = b["due_date"].strftime("%Y-%m-%d")
        account_number = b["account"]

        # TODO: large style
        # TODO: get sequence number in here
        amount_due_mailer_table_data = [
            [Paragraph("Account", s['BillLabel']), Paragraph(account_number, s['BillField'])],
            [Paragraph("Amount Due", s['BillLabel']), Paragraph(amount_due, s['BillField'])],
            [Paragraph("Due Date", s['BillLabel']), Paragraph(due_date, s['BillField'])]
        ]
        t = Table(amount_due_mailer_table_data, colWidths=[137,100])

        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        fl.append(t)
        fl.append(UseUpSpace())

        # billing address

        fl.append(Paragraph("Billing Address", s['BillLabel']))
        fl.append(Spacer(227,10))

        fl.append(Paragraph(b["billing_addressee"], s['BillField']))
        fl.append(Paragraph(b["billing_street"], s['BillField']))
        fl.append(Paragraph(" ".join((b["billing_city"], b["billing_state"], b["billing_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())

        #
        # Second Page
        #
        fl.append(NextPageTemplate(self.page_names[1]));
        fl.append(PageBreak());


        pageTwoBackground = Image(os.path.join(self.skin_directory, self.skin, "page_two.png"), letter[0], letter[1])
        fl.append(pageTwoBackground)

        #populate measured usage header frame
        fl.append(Paragraph("Measured renewable and conventional energy.", s['BillLabel']))
        fl.append(UseUpSpace())

        # list of the rows
        measuredUsage = [
            ["Utility Register", "Description", "Quantity", "", "",""],
            [None, None, "Renewable", "Utility", "Total", None],
            [None, None, None, None,  None, None,]
        ]
        for meter in b["utility_meters"]:
            for register in meter["registers"]:
                measuredUsage.append([
                   "%s %s" % (meter["meter_id"], register["register_id"]),
                   register["description"],
                   register["shadow_total"],
                   register["utility_total"],
                   register["total"],
                   register["quantity_units"]
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

        fl.append(t)
        fl.append(UseUpSpace())


        fl.append(Paragraph("Original utility charges prior to renewable energy.", s['BillLabel']))
        fl.append(UseUpSpace())

        # list of the rows
        chargeDetails = [
            [None, "Charge Description", "Quantity","", "Rate","", "Total"],
            [None, None, None, None, None, None, None]
        ]

        for group, charges in b["hypothetical_chargegroups"].iteritems():
            for i, charge in enumerate(charges):
                if not i: chargeDetails.append([group, None, None, None, None, None, None])
                chargeDetails.append([
                    None,
                    charge["description"],
                    charge["quantity"],
                    charge["rate"],
                    charge["total"],
                ])
        chargeDetails.append([None, None, None, None, None, None,
            format_for_display(
                b["hypothetical_charges"],
                places=2)
        ])

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

        fl.append(t)
        fl.append(UseUpSpace())

        return fl

class SummaryBillDoc(BillDoc):

    page_names = ['First Page', 'Second Page']

    def _page_frames(self):
        """
        Returns list (all pages) of lists (each a page) of frames 
        """

        _showBoundaries = 0

        # first page frames
        fr1 = []

        #page one frames; 

        # holds background image w/ logo 
        fr1.append(
            Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background1', showBoundary=_showBoundaries)
        )

        # TODO: dynamic based on financier
        # Remit Payment To:
        fr1.append(
            Frame(35, 590, 220, 80, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='remitPayment', showBoundary=_showBoundaries)
        )

        # Total Amount Due for all bills
        fr1.append(
            Frame(300, 620, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='totalAmountDue', showBoundary=_showBoundaries)
        )


        fr1.append(
            Frame(35, 35, 542, 500, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billList', showBoundary=_showBoundaries)
        )

        fr2 = []
        # bill list1
        fr2.append(
            Frame(35, 35, 542, 730, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='SecondPagebillList2', showBoundary=_showBoundaries)
        )

        return [fr1, fr2]

    def _flowables(self, bill_data):
        """
        Returns list of _flowables for all pages
        """

        s = self.styles 

        # first page _flowables
        fl = []

        fl.append(
           Image(os.path.join(os.path.join(self.skin_directory, self.skin), "page_one.png"),letter[0], letter[1])
        )

        # TODO: use up space?

        # 1/3 (612)w x (792pt-279pt=)h (to fit #9 envelope) 

        # TODO: make sure there is a first bill
        first_bill = bill_data[0]

        fl.append(Paragraph("Remit Payment To:", s['BillLabelLg']))
        fl.append(Spacer(10,10))
        # TODO: fields now passed into render, so the first bill does not have to be relied on for the fields below
        fl.append(Paragraph(first_bill["payment_payee"] if first_bill["payment_payee"] is not None else "None", s['BillLabel']))
        fl.append(Paragraph(first_bill["payment_street"] if first_bill["payment_street"] is not None else "None", s['BillLabel']))
        fl.append(Paragraph("%s, %s  %s" % (
            first_bill["payment_state"] if first_bill["payment_state"] is not None else "None",
            first_bill["payment_city"] if first_bill["payment_city"] is not None else "None",
            first_bill["payment_postal_code"] if first_bill["payment_postal_code"] is not None else "None"
        ), s['BillLabel']))
        fl.append(UseUpSpace())

        fl.append(Paragraph("Amount Due:  %s" % format_for_display(self.fields['balance_due']), s['BillLabelLg']))
        fl.append(UseUpSpace())

        # First row of summary table
        summary_table_data = [[
            Paragraph("Account", s['BillLabelExSm']),
            Paragraph("Service Location", s['BillLabelExSm']),
            Paragraph("Green Energy", s['BillLabelExSm']),
            Paragraph("Prior Balance", s['BillLabelExSm']),
            Paragraph("Payment Rcvd", s['BillLabelExSm']),
            Paragraph("Balance Fwd", s['BillLabelExSm']),
            Paragraph("Late Charges", s['BillLabelExSm']),
            Paragraph("Balance Due", s['BillLabelExSm']),
            ]] 
        import copy
        # tables simply won't split and go into next frame, which is the whole purpose of flowables.wtf.
        for b in bill_data[:20]:
            summary_table_data.append([
                Paragraph("%s-%s" % (b["account"], b["sequence"]), s['BillFieldExSm']),
                Paragraph(b["service_street"], s['BillFieldExSm']),
                # Need units to be passed in
                Paragraph("%s" % b["total_re_consumed"], s['BillFieldExSm']),
                Paragraph(format_for_display(b["prior_balance"]), s['BillFieldExSm']),
                Paragraph(format_for_display(b["payment_received"]), s['BillFieldExSm']),
                Paragraph(format_for_display(b["prior_balance"]), s['BillFieldExSm']),
                Paragraph(format_for_display(b["late_charge"]), s['BillFieldExSm']),
                Paragraph(format_for_display(b["balance_due"]), s['BillFieldExSm'])
            ])

        t = Table(summary_table_data, colWidths=[55, 158, 55, 55, 55, 55, 55, 55], repeatRows=0)
        t.setStyle(TableStyle([('ALIGN',(0,0),(1,-1),'LEFT'), ('ALIGN',(2,0),(7,-1),'RIGHT'), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black), ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))

        fl.append(t)
        fl.append(UseUpSpace())

        if len(bill_data) > 20:

            fl.append(NextPageTemplate(self.page_names[1]));
            fl.append(PageBreak());

            # and we repeat here the next part of the table, because tables themselves won't split.wtf.
            # First row of summary table
            summary_table_data = [[
                Paragraph("Account", s['BillLabelExSm']),
                Paragraph("Service Location", s['BillLabelExSm']),
                Paragraph("Green Energy", s['BillLabelExSm']),
                Paragraph("Prior Balance", s['BillLabelExSm']),
                Paragraph("Payment Rcvd", s['BillLabelExSm']),
                Paragraph("Balance Fwd", s['BillLabelExSm']),
                Paragraph("Late Charges", s['BillLabelExSm']),
                Paragraph("Balance Due", s['BillLabelExSm']),
            ]]

            # tables simply won't split and go into next frame, which is the whole purpose of flowables.wtf.
            for b in bill_data[20:]:
                summary_table_data.append([
                    Paragraph("%s-%s" % (b["account"], b["sequence"]), s['BillFieldExSm']),
                    Paragraph(b["service_street"], s['BillFieldExSm']),
                    # Need units to be passed in
                    Paragraph("%s" % b["total_re_consumed"], s['BillFieldExSm']),
                    Paragraph(format_for_display(b["prior_balance"]), s['BillFieldExSm']),
                    Paragraph(format_for_display(b["payment_received"]), s['BillFieldExSm']),
                    Paragraph(format_for_display(b["prior_balance"]), s['BillFieldExSm']),
                    Paragraph(format_for_display(b["late_charge"]), s['BillFieldExSm']),
                    Paragraph(format_for_display(b["balance_due"]), s['BillFieldExSm'])
                ])

            t = Table(summary_table_data, colWidths=[55, 158, 55, 55, 55, 55, 55, 55], repeatRows=0)
            t.setStyle(TableStyle([('ALIGN',(0,0),(1,-1),'LEFT'), ('ALIGN',(2,0),(7,-1),'RIGHT'), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black), ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))

            fl.append(t)

        # and now what are we supposed to do if there are more than 40 bills to list? Replace ReportLab.wtf.

        return fl


def init_logging(args):
    '''Return initialized logger.'''
    #globals & logger init
    LOGGER_NAME = "Bill Renderer"
    std_formatter = logging.Formatter('%(asctime)s - %(funcName)s : '
                                      '%(levelname)-8s %(message)s')
    _logger = logging.getLogger(LOGGER_NAME)
    _logger.setLevel(logging.DEBUG)

    #configure writing to stdout (bhvr toggled w/ verbose flag)
    so_handler = logging.StreamHandler(sys.stdout)
    so_formatter = std_formatter

    so_handler.setFormatter(so_formatter)
    if args.verbose:
        so_handler.setLevel(logging.DEBUG) 
    else:
        so_handler.setLevel(logging.INFO) 
    _logger.addHandler(so_handler)

    return _logger

def build_parsers():
    '''Return initialized argument parser.'''
    parser = ArgumentParser(description="CLI for producing sample bills")

    parser.add_argument("-v", "--verbose", dest="verbose", 
                        default=False,  action='store_true',
                        help="Maximum output to stdout.  Default: %(default)r")

    parser.add_argument("--skindirectory", dest="skin_directory", 
                        default=False,  nargs="?", required=True,
                        help="Specify skin bundle directory.  Default: %(default)r")

    parser.add_argument("--skinname", dest="skin_name", 
                        default=False,  nargs="?", required=True,
                        help="Specify skin name.  Default: %(default)r")

    parser.add_argument("--outputdirectory", dest="output_directory", 
                        default=False,  nargs="?", required=True,
                        help="Specify output directory.  Default: %(default)r")

    parser.add_argument("--outputfile", dest="output_file", 
                        default=False,  nargs="?", required=True,
                        help="Specify output file.  Default: %(default)r")

    parser.add_argument("--datafile", dest="data_file", 
                        default=False,  nargs="?", required=False,
                        help="Specify input data file. Omit for one bill.  Default: %(default)r")
    return parser

if __name__ == '__main__':

    # run pv bill with input data 
    # python processing/bill_templates.py --skinname skyline_pv --skindirectory reebill_templates --outputdirectory /tmp --outputfile pv.pdf --datafile test/bill_templates.csv

    # run one bill with teva template 
    # python processing/bill_templates.py --skinname skyline_pv --skindirectory reebill_templates --outputdirectory /tmp --outputfile pv.pdf 

    parser = build_parsers()
    args = parser.parse_args()

    logger = init_logging(args)

    if not os.path.exists(args.output_directory):
        os.mkdir(args.output_directory)

    fake_bill_fields = {
        "account": "38291",
        "sequence": "1",
        "begin_period": datetime.strptime("2013-01-01", "%Y-%m-%d"),
        "manual_adjustment": float("0"),
        "balance_forward": float("0"),
        "payment_received": float("0"),
        "balance_due": float("12471.62"),
        "total_energy_consumed": float("159756.09"),
        "total_re_consumed": float("127914"),
        "total_ce_consumed": float("31842.09"),
        "total_re_delivered_grid": float("0"),
        "total_re_generated": float("127914"),
        "due_date": datetime.strptime("2013-03-01", "%Y-%m-%d"),
        "end_period": datetime.strptime("2013-02-01", "%Y-%m-%d"),
        "hypothetical_charges": float("18371.95"),
        "actual_charges": float("3661.84"),
        "discount_rate": float("0.99"),
        "issue_date": datetime.strptime("2013-02-01", "%Y-%m-%d"),
        "late_charge": float("0"),
        "prior_balance": float("0"),
        "ree_charge": float("12471.62"),
        "neg_credit_applied": float("0"),
        "neg_ree_charge": float("0"),
        "neg_credit_balance": float("0"),
        "ree_savings": float("2238.5"),
        "neg_ree_savings": float("0"),
        "neg_ree_potential_savings": float("0"),
        "ree_value": float("14710.11"),
        "service_addressee": "Service Location",
        "service_city": "Washington",
        "service_postal_code": "20009",
        "service_state": "DC",
        "service_street": "2020 K Street",
        "total_adjustment": float("0"),
        "total_hypothetical_charges": float("0"),
        "total_utility_charges": float("0"),
        "payment_payee": "Skyline Innovations",
        "payment_city": "Washington",
        "payment_postal_code": "20009",
        "payment_state": "DC",
        "payment_street": "1606 20th St NW",
        "billing_addressee": "Example Billee",
        "billing_street": "1313 Elm Street",
        "billing_city": "Washington",
        "billing_postal_code": "20009",
        "billing_state": "DC"
    }

    fake_utility_meters = [
        {
            'meter_id':'meter 1',
            'registers':[
                {
                    'register_id':'register 1',
                    'description':'description',
                    'utility_total':0,
                    'shadow_total':0,
                    'total':0,
                    'quantity_units':'Therms'
                }, {
                    'register_id':'register 2',
                    'description':'description ',
                    'utility_total':0,
                    'shadow_total':0,
                    'total':0,
                    'quantity_units':'Therms'
                }, {
                    'register_id':'register 3',
                    'description':'description',
                    'utility_total':0,
                    'shadow_total':0,
                    'total':0,
                    'quantity_units':'Therms'
                }
            ],
            'total':0
        }, {
            'meter_id':'meter 2',
            'registers':[
                {
                    'register_id':'register 1',
                    'description':'description',
                    'utility_total':0,
                    'shadow_total':0,
                    'total':0,
                    'quantity_units':'Therms'
                }, {
                    'register_id':'register 2',
                    'description':'description',
                    'utility_total':0,
                    'shadow_total':0,
                    'total':0,
                    'quantity_units':'Therms'
                }, {
                    'register_id':'register 3',
                    'description':'description',
                    'utility_total':0,
                    'shadow_total':0,
                    'total':0,
                    'quantity_units':'Therms'
                }
            ],
            'total':0
        }
    ]

    fake_hypo_chargegroups = {
        "group 1": [
            {
                "description":"description 1",
                "quantity":0,
                "rate":0,
                "total":0
            }, {
                "description":"description 2",
                "quantity":0,
                "rate":0,
                "total":0
            }, {
                "description":"description 3",
                "quantity":0,
                "rate":0,
                "total":0
            }
        ],
        "group 2": [
            {
                "description":"description 1",
                "quantity":0,
                "rate":0,
                "total":0
            }, {
                "description":"description 2",
                "quantity":0,
                "rate":0,
                "total":0
            }, {
                "description":"description 3",
                "quantity":0,
                "rate":0,
                "total":0
            }
        ],
        "group3": [
            {
                "description":"description 1",
                "quantity":0,
                "rate":0,
                "total":0
            }, {
                "description":"description 2",
                "quantity":0,
                "rate":0,
                "total":0
            }, {
                "description":"description 3",
                "quantity":0,
                "rate":0,
                "total":0
            }
        ],
    } 

    if args.data_file:

        # read in lots of simulated data
        reader = csv.reader(open(args.data_file))

        for row, record in enumerate(reader):
            if row == 0:
                # the first column is the name of the variable
                # create a dictionary whose keys are date column headers
                by_date_dict = dict((datetime.strptime(col, '%Y-%m-%d'), dict()) for col in record[1:])

                # keep track of the dates in column order
                col_hdrs = [datetime.strptime(r, '%Y-%m-%d') for r in record[1:]]
            else:
                for col_index, value in enumerate(record[1:]):
                    the_date = col_hdrs[col_index]
                    if record[0] in ['begin_period', 'end_period', 'due_date', 'issue_date']:
                        value = datetime.strptime(value, '%Y-%m-%d')
                    elif record[0] in ['manual_adjustment', 'balance_due', 'balance_forward', 'hypothetical_charges', 
                        'late_charge', 'payment_received','prior_balance', 'ree_charge', 'ree_savings', 'ree_value',
                        'total_adjustment', 'total_hypothetical_charges', 'total_utility_charges', 'actual_charges',
                        'discount_rate', 'neg_credit_applied', 'neg_ree_savings', 'neg_ree_charge', 'neg_credit_balance', 
                        'neg_ree_potential_savings', 'total_re_generated', 'total_re_consumed', 'total_ce_consumed',
                        'total_energy_consumed', 'total_re_delivered_grid']:
                        value = float(value)

                    by_date_dict[the_date][record[0]] = value

                    # tack on fake meters 
                    by_date_dict[the_date]['utility_meters'] = fake_utility_meters

                    by_date_dict[the_date]['hypothetical_chargegroups'] = fake_hypo_chargegroups
    else:
        logger.info("No datafile supplied, generating one bill")
        # implemented here so all necessary fields can be seen
        by_date_dict = {'2014-01-01': fake_bill_fields}
        by_date_dict['2014-01-01']['utility_meters'] = fake_utility_meters
        by_date_dict['2014-01-01']['hypothetical_chargegroups'] = fake_hypo_chargegroups
    

    bill_data = deque([],13)

    for i, kvp in enumerate(sorted(by_date_dict.keys())):
        bill_data.append(by_date_dict[kvp])

        # pass in all cycles data (for historical lookback)

        # for some reasons, if the file path passed in does not exist, BillDoc fails silently 
        if args.skin_name == "nextility_swh" or args.skin_name == "skyline":
            doc = ThermalBillDoc()
        elif args.skin_name == "skyline_pv":
            doc = PVBillDoc()
        elif args.skin_name == "summary":
            doc = SummaryBillDoc()
        doc.render(bill_data, args.output_directory, "%s-%s" % ("{0:02}".format(i), args.output_file), args.skin_directory, args.skin_name)
