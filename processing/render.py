#!/usr/bin/env python
import sys
import os  
from decimal import *
import reportlab
from pyPdf import PdfFileWriter, PdfFileReader
from reportlab.platypus import BaseDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont  
from reportlab.pdfbase.pdfmetrics import registerFontFamily

from billing.processing import mongo

# TODO render should not depend on BillUpload--move this function out to its
# own file
from billing.processing.billupload import create_directory_if_necessary

sys.stdout = sys.stderr

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
        
    def afterPage(self):
        if self.pageTemplate.id == firstPageName:
            self.canv.saveState()
            self.canv.restoreState()
        if self.pageTemplate.id == secondPageName:
            self.canv.saveState()
            self.canv.restoreState()
        
        
    def handle_pageBegin(self):
        BaseDocTemplate.handle_pageBegin(self)


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
        self.current_template = self.default_template

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

        # Hack for overriding default template if a teva account
        if (account in self.teva_accounts):
            self.current_template = 'teva'
        else:
            self.current_template = self.default_template

        # render each version
        max_version = self.state_db.max_version(session, account, sequence)
        for version in range(max_version + 1):
            reebill = self.state_db.get_reebill(session, account, sequence,
                    version=version)
            reebill_document = self.reebill_dao.load_reebill(account, sequence,
                    version=version)
            self.render_version(reebill, reebill_document, outputdir,
                    outputfile +  '-%s' % version, verbose)

        # concatenate version pdfs
        input_paths = ['%s-%s' % (os.path.join(outputdir, outputfile), v)
                for v in range(max_version + 1)]
        output_path = os.path.join(outputdir, outputfile)
        concat_pdfs(input_paths, output_path)

        # delete version pdfs, leaving only the combined version
        for input_path in input_paths:
            os.remove(input_path)
 
    def render_max_version(self, session, account, sequence, outputdir, outputfile, verbose):
        # Hack for overriding default template if a teva account
        if (account in self.teva_accounts):
            self.current_template = 'teva'
        else:
            self.current_template = self.default_template
        max_version = self.state_db.max_version(session, account, sequence)
        reebill = self.state_db.get_reebill(session, account, sequence,
                version=max_version)
        reebill_document = self.reebill_dao.load_reebill(account, sequence,
                version=max_version)
        self.render_version(reebill, reebill_document, outputdir, outputfile,
                verbose)

    def render_version(self, reebill, reebill_document, outputdir,
                       outputfile, verbose):
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

        # 2/3 (removed)

        # 3/3

        # summary background block
        summaryBackgroundF = Frame(141, 75, 443, 152, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='summaryBackground', showBoundary=_showBoundaries)

        billPeriodTableF = Frame(30, 167, 241, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billPeriod', showBoundary=_showBoundaries)

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


        # build page container for flowables to populate
        firstPage = PageTemplate(id=firstPageName,frames=[backgroundF1, billIdentificationF, amountDueF, serviceAddressF, billingAddressF, summaryBackgroundF, billPeriodTableF, summaryChargesTableF, balanceF, adjustmentsF, currentChargesF, balanceForwardF, balanceDueF])
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
        doc = SIBillDocTemplate("%s/%s" % (outputdir, outputfile), pagesize=letter, showBoundary=0, allowSplitting=0)
        doc.addPageTemplates([firstPage, secondPage])

        Elements = []

        #
        # First Page
        #

        # populate backgroundF1
        pageOneBackground = Image(os.path.join(os.path.join(self.template_directory, self.current_template), "page_one.png"),letter[0], letter[1])
        Elements.append(pageOneBackground)

        # populate account number, bill id & issue date
        issue_date = reebill.issue_date
        accountNumber = [
            [Paragraph("Account Number", styles['BillLabelRight']),Paragraph(
                reebill.customer.account + " " + str(reebill.sequence),styles['BillField'])],
            [Paragraph("Issue Date", styles['BillLabelRight']), Paragraph(issue_date.strftime('%m-%d-%Y') if issue_date is not None else 'None', styles['BillField'])]
        ]

        t = Table(accountNumber, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        Elements.append(t)
        #fits perfectly
        #Elements.append(UseUpSpace())

        # populate due date and amount
        dueDateAndAmount = [
            [Paragraph("Due Date", styles['BillLabelRight']), Paragraph(reebill
            .due_date.strftime('%m-%d-%Y') if reebill.due_date is not None
            else 'None', styles['BillFieldRight'])],
            [Paragraph("Balance Due", styles['BillLabelRight']), Paragraph(
                format_for_display(reebill.balance_due), styles[
                    'BillFieldRight'])]
        ]
        
        t = Table(dueDateAndAmount, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
        Elements.append(t)
        Elements.append(UseUpSpace())
        
        # populate service address
        Elements.append(Spacer(100,10))
        Elements.append(Paragraph("Service Location", styles['BillLabel']))

        sa = stringify(reebill.service_address.to_dict())
        Elements.append(Paragraph(sa.get('addressee', ""), styles['BillField']))
        Elements.append(Paragraph(sa.get('street',""), styles['BillField']))
        Elements.append(Paragraph(" ".join((sa.get('city', ""), sa.get('state', ""), sa.get('postal_code', ""))), styles['BillField']))
        Elements.append(UseUpSpace())

        # populate billing address
        Elements.append(Spacer(100,20))
        ba = stringify(reebill.billing_address.to_dict())
        Elements.append(Paragraph(ba.get('addressee', ""), styles['BillFieldLg']))
        Elements.append(Paragraph(ba.get('street', ""), styles['BillFieldLg']))
        Elements.append(Paragraph(" ".join((ba.get('city', ""), ba.get('state', ""), ba.get('postal_code',""))), styles['BillFieldLg']))
        Elements.append(UseUpSpace())

        # populate summary background
        Elements.append(Image(os.path.join(self.template_directory,'images','SummaryBackground.png'), 443, 151))
        Elements.append(UseUpSpace())

        # populate billPeriodTableF
        # spacer so rows can line up with those in summarChargesTableF rows
        periods=reebill.get_period()
        serviceperiod = [
                [Paragraph("spacer", styles['BillLabelFake']), Paragraph("spacer", styles['BillLabelFake']), Paragraph("spacer", styles['BillLabelFake'])],
                [Paragraph("", styles['BillLabelSm']), Paragraph("From", styles['BillLabelSm']), Paragraph("To", styles['BillLabelSm'])]
            ] + [
                [
                    Paragraph(u' service',styles['BillLabelSmRight']),
                    Paragraph(periods[0].strftime('%m-%d-%Y'), styles['BillFieldRight']),
                    Paragraph(periods[1].strftime('%m-%d-%Y'), styles['BillFieldRight'])
                ]
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
                Paragraph(str(format_for_display(reebill_document
                .get_total_hypothetical_charges())),styles['BillFieldRight']),
                Paragraph(str(format_for_display(reebill_document
                .get_total_utility_charges())),styles['BillFieldRight']),
                Paragraph(str(format_for_display(reebill.ree_value)),styles[
                    'BillFieldRight'])
            ]
        ]

        t = Table(utilitycharges, colWidths=[84,84,84])

        t.setStyle(TableStyle([('SPAN', (0,0), (1,0)), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,2), (-1,-1), 0.25, colors.black), ('BOX', (0,2), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,2),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        # populate balances
        balances = [
            [Paragraph("Prior Balance", styles['BillLabelRight']), Paragraph(
                str(format_for_display(reebill.prior_balance)),styles[
                    'BillFieldRight'])],
            [Paragraph("Payment Received", styles['BillLabelRight']),
                Paragraph(str(format_for_display(reebill.payment_received)),
                    styles['BillFieldRight'])]
        ]

        t = Table(balances, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        # populate adjustments
        manual_adjustments = reebill.manual_adjustment
        other_adjustments = reebill.total_adjustment
        adjustments = [
            [Paragraph("Manual Adjustments", styles['BillLabelRight']), Paragraph(str(format_for_display(manual_adjustments)), styles['BillFieldRight'])],
            [Paragraph("Other Adjustments", styles['BillLabelRight']), Paragraph(str(format_for_display(other_adjustments)), styles['BillFieldRight'])]
        ]
        
        t = Table(adjustments, [180,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())


        try:
            # populate current charges
            late_charges = reebill.late_charge
        except KeyError:
            late_charges = None

        # depiction of conditional template logic based on ReeBill returning None
        # we will want to distinguish between a late charge, a zero dollar late charge and no late charge
        # to allow the template to do fancy formatting
        if late_charges is not None:
            currentCharges = [
                [Paragraph("Your Savings", styles['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_savings)), styles['BillFieldRight'])],
                [Paragraph("Renewable Charges", styles['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_charge)), styles['BillFieldRight'])],
                [Paragraph("Late Charges", styles['BillLabelRight']), Paragraph(str(format_for_display(late_charges)), styles['BillFieldRight'])]
            ]
        else:
            currentCharges = [
                [Paragraph("Your Savings", styles['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_savings)), styles['BillFieldRight'])],
                [Paragraph("Renewable Charges", styles['BillLabelRight']), Paragraph(str(format_for_display(reebill.ree_charge)), styles['BillFieldRight'])],
                [Paragraph("Late Charges", styles['BillLabelRight']), Paragraph(str("n/a"), styles['BillFieldRight'])]
            ]

        t = Table(currentCharges, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())

        # populate balanceForward
        balance = [
            [Paragraph("Balance Forward", styles['BillLabelRight']), Paragraph(str(format_for_display(reebill.balance_forward)), styles['BillFieldRight'])]
        ]

        t = Table(balance, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(1,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())



        # populate balanceDueFrame
        balanceDue = [
            [Paragraph("Balance Due", styles['BillLabelLgRight']), Paragraph(str(format_for_display(reebill.balance_due)), styles['BillFieldRight'])]
        ]

        t = Table(balanceDue, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,0),(-1,-1),colors.white)]))
        Elements.append(t)
        Elements.append(UseUpSpace())




        #
        # Second Page
        #
        Elements.append(NextPageTemplate("SecondPage"));
        Elements.append(PageBreak());



        pageTwoBackground = Image(os.path.join(self.template_directory, self.current_template, "page_two.png"), letter[0], letter[1])
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

        # Load registers and match up shadow registers to actual registers
        assert len(reebill.utilbills)==1
        shadow_registers = reebill_document.get_all_shadow_registers_json()
        utilbill_doc=self.reebill_dao.load_doc_for_utilbill(reebill.utilbills[0])
        actual_registers = mongo.get_all_actual_registers_json(
           utilbill_doc)
        for s_register in shadow_registers:
            total = 0
            for a_register in actual_registers:
                if s_register['register_binding'] == a_register['binding']:
                    shadow_total = s_register['quantity']
                    utility_total = a_register['quantity']
                    total += (utility_total + shadow_total)
                    measuredUsage.append([
                        a_register['meter_id'],
                        a_register['description'],
                        round_for_display(shadow_total),
                        utility_total,
                        round_for_display(total),
                        a_register['quantity_units']
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

        # muliple services are not supported
        assert len(reebill_document.services) == 1
        last_group=None
        for charge in reebill_document.get_all_hypothetical_charges():
            # Only print the group if it changed
            if last_group == charge['group']:
                group = None
            else:
                last_group = charge['group']
                group = last_group
                chargeDetails.append([reebill_document.services[0],
                              None, None, None, None, None, None])
            chargeDetails.append([
                group,
                charge.get('description', "No description"),
                format_for_display(charge['quantity'], places=3)
                    if 'quantity' in charge else Decimal("1"),
                charge.get('quantity_units', None),
                format_for_display(charge['rate'], places=5)
                    if 'rate' in charge else None,
                charge.get('rate_units', None),
                format_for_display(charge['total'], places=2)
                    if 'total' in charge else None
            ])
        chargeDetails.append([None, None, None, None, None, None, None])
        chargeDetails.append([None, None, None, None, None, None,
            format_for_display(
                reebill_document.get_total_hypothetical_charges(),
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

        Elements.append(t)
        Elements.append(UseUpSpace())

        # render the document    
        doc.setProgressCallBack(progress)
        doc.build(Elements)

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

