#!/usr/bin/env python
from operator import attrgetter
import os
from argparse import ArgumentParser
from itertools import groupby
from errno import EEXIST, ENOENT

import reportlab
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


# Important for currency formatting
import locale
from exc import InvalidParameter
from util.pdf import PDFConcatenator

locale.setlocale(locale.LC_ALL, '')

def round_for_display(x, places=2):
    '''Rounds the float 'x' for display as dollars according to the previous
    behavior in reebill_file_handler.py using Decimals, which was to round to the nearest
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

class ReebillFileHandler(object):
    '''Methods for working with Reebill PDF files.
    '''
    FILE_NAME_FORMAT = '%(account)s_%(sequence)04d.pdf'

    @staticmethod
    def _ensure_directory_exists(path):
        '''Create directories if necessary to ensure that the given path is
        valid.
        '''
        try:
            os.makedirs(os.path.dirname(path))
        except OSError as e:
            # makedirs fails if the directories already exist
            if e.errno == EEXIST:
                pass

    def __init__(self, output_dir_path, teva_accounts):
        '''
        :param template_dir_path: path of directory where
        "templates" and fonts are stored, RELATIVE to billing directory.
        :param output_dir_path: absolute path of directory where reebill PDF
        files are stored.
        :param teva accounts: list of customer accounts (strings) that should
        have PDFs with the "teva" PDF format instead of the normal one.
        '''
        base_path = os.path.dirname(os.path.dirname(__file__))
        template_dir_path = 'reebill/reebill_templates'
        self._template_dir_path = os.path.join(base_path, template_dir_path)
        if not os.access(self._template_dir_path, os.R_OK):
            raise InvalidParameter('Path "%s" is not readable' %
                                   self._template_dir_path)
        self._pdf_dir_path = output_dir_path
        self._teva_accounts = teva_accounts

    def get_file_name(self, reebill):
        '''Return name of the PDF file associated with the given :class:`ReeBill`
        (the file may not exist).
        '''
        return ReebillFileHandler.FILE_NAME_FORMAT % dict(
                account=reebill.get_account(), sequence=reebill.sequence)

    def get_file_contents(self, reebill):
        '''Return contents of the PDF file associated with the given
        :class:`ReeBill` (the file may not exist).
        '''
        file_path = os.path.join(self._pdf_dir_path, reebill.get_account(),
                self.get_file_name(reebill))
        file_obj = open(file_path, 'r')
        contents = file_obj.read()
        file_obj.close()
        return contents

    def get_file_path(self, reebill):
        '''Return full path to the PDF file associated with the given
        :class:`ReeBill` (the file may not exist).
        '''
        return os.path.join(self._pdf_dir_path,reebill.get_account(),
                self.get_file_name(reebill))

    def get_file_display_path(self, reebill):
        ''' Returns relative path to the PDF file accosiated with the given
        reebill for path used in the sent e-mail to customer
        '''
        return os.path.join(reebill.get_account(),
                self.get_file_name(reebill))

    def get_file(self, reebill):
        """Return the file itself opened in "rb" mode. The consumer must
        close it.
        """
        return open(self.get_file_path(reebill), 'rb')

    def delete_file(self, reebill, ignore_missing=False):
        '''Delete the file belonging to the given :class:`ReeBill`.
        If ignore_missing is True, no exception will be raised if the file to
        be deleted does not exist.
        '''
        # note that this will fail if the file does not exist. that is not
        # supposed to happen so it is not being ignored.
        path = self.get_file_path(reebill)
        try:
            os.remove(path)
        except OSError as e:
            if not ignore_missing or e.errno != ENOENT:
                raise

    def _generate_document(self, reebill):
        # charges must be sorted by type in order for 'groupby' to work below
        sorted_charges = sorted(reebill.charges, key=attrgetter('type'))

        def get_utilbill_register_data_for_reebill_reading(reading):
            utilbill = reading.reebill.utilbill
            try:
                register = next(r for r in utilbill.registers
                        if r.register_binding == reading.register_binding)
            except StopIteration:
                return '', '', ''
            return (register.meter_identifier, register.identifier,
                    register.description)
        return {
            'account': reebill.get_account(),
            'sequence': str(reebill.sequence),
            'begin_period': reebill.utilbills[0].period_start,
            'manual_adjustment': reebill.manual_adjustment,
            'balance_forward': reebill.balance_forward,
            'payment_received': reebill.payment_received,
            'balance_due': reebill.balance_due,
            'total_energy_consumed': reebill.get_total_renewable_energy() + \
                                     reebill.get_total_conventional_energy(),
            'total_re_consumed': reebill.get_total_renewable_energy(),
            'total_ce_consumed': reebill.get_total_conventional_energy(),
            'total_re_delivered_grid': 0,
            'total_re_generated': reebill.get_total_conventional_energy(),
            'due_date': reebill.due_date,
            'end_period': reebill.utilbill.period_end,
            'hypothetical_charges': reebill.get_total_hypothetical_charges(),
            'discount_rate': reebill.discount_rate,
            'issue_date': reebill.issue_date,
            'late_charge': reebill.late_charge,
            'prior_balance': reebill.prior_balance,
            'ree_charge': reebill.ree_charge,
            'neg_credit_applied': 0,
            'neg_ree_charge': 0,
            'neg_credit_balance': 0,
            'ree_savings': reebill.ree_savings,
            'neg_ree_savings': 0,
            'neg_ree_potential_savings': 0,
            'ree_value': reebill.ree_value,
            'service_addressee': reebill.service_address.addressee,
            'service_city': reebill.service_address.city,
            'service_postal_code': reebill.service_address.postal_code,
            'service_state': reebill.service_address.state,
            'service_street': reebill.service_address.street,
            'total_adjustment': reebill.total_adjustment,
            'total_utility_charges': reebill.get_total_actual_charges(),
            'payee': reebill.get_payee(),
            'payment_addressee': 'Nextility',
            'payment_city': 'Washington',
            'payment_postal_code': '20009',
            'payment_state': 'DC',
            'payment_street': '1606 20th St NW',
            'billing_addressee': reebill.billing_address.addressee,
            'billing_street': reebill.billing_address.street,
            'billing_city': reebill.billing_address.city,
            'billing_postal_code': reebill.billing_address.postal_code,
            'billing_state': reebill.billing_address.state,
            'utility_meters':  [{
                'meter_id': meter_id,
                    'registers': [{
                    'register_id': register_id,
                    'description': description,
                    'shadow_total': reading.renewable_quantity,
                    'utility_total': reading.conventional_quantity,
                    'total': (reading.conventional_quantity +
                              reading.renewable_quantity),
                    'quantity_units': reading.unit,
                } for reading in readings]
            } for (meter_id, register_id, description), readings
                    in groupby(reebill.readings, key=lambda r: \
                    get_utilbill_register_data_for_reebill_reading(r))],
            'hypothetical_chargegroups': {
                type: [{
                    'description': charge.description,
                    'quantity': charge.h_quantity,
                    'rate': charge.rate,
                    'total': charge.h_total
                } for charge in charges]
            for type, charges in groupby(sorted_charges,
                                               key=attrgetter('type'))},
        }

    def _get_skin_directory_name_for_account(self, account):
        '''Return name of the directory in which "skins" (image files) to be
        used in bill PDFs for the given account are stored.
        '''
        if account in self._teva_accounts:
            return 'teva'
        else:
            # TODO this will be set by type of energy service
            # see https://www.pivotaltracker.com/story/show/78497806
            return 'nextility_swh'

    def render(self, reebill):
        '''Create a PDF of the given :class:`ReeBill`.
        '''
        path = self.get_file_path(reebill)
        self._ensure_directory_exists(path)
        dir_path, file_name = os.path.split(path)
        document = self._generate_document(reebill)
        ThermalBillDoc().render([document], dir_path,
                file_name, self._template_dir_path,
                self._get_skin_directory_name_for_account(
                        reebill.get_account()))

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
        self.styles.add(ParagraphStyle(name='BillFieldSmRight', fontName='BryantMA', fontSize=8, leading=8, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillFieldMicroRight', fontName='BryantMA', fontSize=5, leading=8, alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='BillLabelFake', fontName='VerdanaB', fontSize=8, leading=8, textColor=colors.white))


    # NOTE: this should not be public but it can't be changed due to definition in ReportLab
    def afterPage(self):
        if self.pageTemplate.id == self.page_names[0]:
            self.canv.saveState()
            #self.canv.setStrokeColorRGB(32,32,32)
            #self.canv.setLineWidth(.05)
            #self.canv.setDash(1,3)
            #self.canv.line(0,537,612,537)
            #self.canv.line(0,264,612,264)
            self.canv.restoreState()
        if self.pageTemplate.id == self.page_names[1]:
            self.canv.saveState()
            #self.canv.setStrokeColorRGB(0,0,0)
            #self.canv.setLineWidth(.05)
            #self.canv.setDash(1,3)
            #self.canv.line(0,264,612,264)
            self.canv.restoreState()

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

    def render(self, data, output_directory, output_name, skin_directory, skin_name):
        self.filename = os.path.join("%s", "%s") % (output_directory, output_name)
        self.skin_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), skin_directory)
        self.skin = skin_name
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

        billPeriodTableF = Frame(36, 167, 241, 90, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billPeriod', showBoundary=False)


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
        billIdentificationF = Frame(90, 657, 227, 37, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='accountNumber', showBoundary=_showBoundaries)

        # Due date and Amount frame
        amountDueF = Frame(353, 657, 227, 37, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='amountDue', showBoundary=_showBoundaries)


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

        # remit to block
        remitToF = Frame(77, 41, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='remitTo', showBoundary=_showBoundaries)

        # balance due block
        balanceDueF = Frame(360, 41, 220, 25, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='balanceDue', showBoundary=_showBoundaries)

        # build page container for _flowables to populate
        firstPage = [backgroundF1, billIdentificationF, amountDueF, serviceAddressF, billingAddressF, summaryBackgroundF, billPeriodTableF, summaryChargesTableF, balanceF, adjustmentsF, currentChargesF, balanceForwardF, remitToF, balanceDueF]

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
                format_for_display(b["balance_due"]), s[
                    'BillFieldRight'])]
        ]
        
        t = Table(dueDateAndAmount, [135,85])
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

        #populate remitTo
        remitTo = [
            [Paragraph("Remit To", s['BillLabelLgRight']), Paragraph(b["payee"] if b['payee'] is not None else '', s['BillFieldRight'])]
        ]

        t = Table(remitTo, [135,85])
        t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black), ('BACKGROUND',(0,0),(-1,-1),colors.white)]))
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

    def page_frames(self):
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

    def flowables(self, bill_data):
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
        fl.append(Paragraph(b["payment_addressee"], s['BillField']))
        fl.append(Paragraph(b["payment_street"], s['BillField']))
        fl.append(Paragraph(" ".join((b["payment_city"], b["payment_state"], b["payment_postal_code"])), s['BillField']))
        fl.append(UseUpSpace())


        # amount due mailer

        # TODO: dollar value
        amount_due = locale.currency(b["balance_due"], grouping=True)
        due_date = b["due_date"].strftime("%Y-%m-%d")
        account_number = b["account"]

        # TODO: large style
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


def build_parsers():
    '''Return initialized argument parser.'''
    parser = ArgumentParser(description="Send AMQP for recently modified records.")

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


class SummaryFileGenerator(object):
    """Generates a "summary" document from multiple ReeBills.
    """
    def __init__(self, reebill_file_handler, pdf_concatenator):
        self._reebill_file_handler = reebill_file_handler
        self._pdf_concatenator = pdf_concatenator

    def generate_summary_file(self, reebills, output_file):
        """
        :param reebills: nonempty iterable of ReeBills that should be included.
        :param output_file: file where the summary will be written.
        """
        assert reebills

        for reebill in reebills:
            # write every bill to a file, read it back again, and append it
            self._reebill_file_handler.render(reebill)
            input_file = self._reebill_file_handler.get_file(reebill)
            self._pdf_concatenator.append(input_file)

        # TODO: eventually there may be extra pages not taken from the bill
        # PDFs
        self._pdf_concatenator.write_result(output_file)
