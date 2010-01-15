from reportlab.platypus import BaseDocTemplate, Paragraph, Table, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace

from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from pprint import pprint

from reportlab.pdfgen import canvas
from reportlab.pdfgen.pathobject import PDFPathObject



# for font management
import os  
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
#  Load Fonts
#
# add your font directories to the T1SearchPath in reportlab/rl_config.py as an alternative.
folder = os.path.dirname(reportlab.__file__) + os.sep + 'fonts'  

pdfmetrics.registerFont(TTFont('Vera', os.path.join(folder, 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('VeraBd', os.path.join(folder, 'VeraBd.ttf')))
pdfmetrics.registerFont(TTFont('VeraIt', os.path.join(folder, 'VeraIt.ttf')))
pdfmetrics.registerFont(TTFont('VeraBI', os.path.join(folder, 'VeraBI.ttf')))
registerFontFamily('Vera',normal='Vera',bold='VeraBd',italic='VeraIt',boldItalic='VeraBI')


pdfmetrics.registerFont(TTFont("Verdana", 'fonts/verdana.ttf'))  
pdfmetrics.registerFont(TTFont("VerdanaB", 'fonts/verdanab.ttf'))  
pdfmetrics.registerFont(TTFont("VerdanaI", 'fonts/verdanai.ttf'))  
registerFontFamily('Verdana',normal='Verdana',bold='VerdanaB',italic='VerdanaI')



#
# Globals
#
defaultPageSize = letter
PAGE_HEIGHT=letter[1]; PAGE_WIDTH=letter[0]
Title = "Skyline Bill"
pageinfo = "Skyline Bill"
firstPageName = "FirstPage"
secondPageName = "SecondPage"



class SIBillDocTemplate(BaseDocTemplate):
    """Structure Skyline Innovations Bill. """

    def build(self,flowables, canvasmaker=canvas.Canvas):
        """build the document using the flowables while drawing lines and figureson top of them."""
 
        BaseDocTemplate.build(self,flowables, canvasmaker=canvasmaker)
        
    def beforePage(self):
        print "Before Page: ", self.pageTemplate.id
        
    def afterPage(self):
        print "After Page"
        if self.pageTemplate.id == firstPageName:
            self.canv.saveState()
            self.canv.setStrokeColorRGB(255.0,255.0,255.0)
            self.canv.setLineWidth(.2)
            self.canv.setDash(1,3)
            self.canv.line(0,265,612,265)
            self.canv.line(0,550,612,550)
            self.canv.restoreState()
        
        
    def handle_pageBegin(self):
        print "handle_pageBegin"
        BaseDocTemplate.handle_pageBegin(self)






def progress(type,value):
    print type, value
     
def go():


    dom = bindery.parse("../bills/Skyline-1-10001.xml")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BillLabel', fontName='Verdana', fontSize=10, leading=1))
    styles.add(ParagraphStyle(name='BillLabel1', fontName='Vera', fontSize=10, leading=1))
    style = styles["BillLabel"]
    #pprint(dir(style))
    #pprint(dir(styles["Normal"]))


    _showBoundaries = 0

    # 612w 792h
    backgroundF = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="background", showBoundary=_showBoundaries)

    # bill dates block
    billIssueDateF = Frame(90, 690, 120, 6, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="billIssueDate", showBoundary=_showBoundaries)
    billDueDateF = Frame(210, 690, 130, 6, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="billDueDate", showBoundary=_showBoundaries)
    billPeriodTableF = Frame(90, 640, 250, 40, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="billDueDate", showBoundary=_showBoundaries)


    #
    chargesWithoutF = Frame(360, 690, 125, 6, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="chargesWithout", showBoundary=_showBoundaries)
    chargesWithF = Frame(500, 690, 80, 6, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="chargesWith", showBoundary=_showBoundaries)
    chargesTableF = Frame(360, 640, 220, 40, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id="chargesWith", showBoundary=_showBoundaries)

    contentFrame = Frame(100,100, 200,200, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=_showBoundaries)
    serviceAddrFrame = Frame(200,200, 300, 300, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=_showBoundaries)

    firstPage = PageTemplate(id=firstPageName,frames=[backgroundF, billIssueDateF, billDueDateF, billPeriodTableF, chargesWithoutF, chargesWithF, chargesTableF])


    rbackgroundFrame = Frame(400,400, 100, 100, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, showBoundary=_showBoundaries)
    rcontentFrame = Frame(600,600, 100,100, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=_showBoundaries)

    secondPage = PageTemplate(id=secondPageName,frames=[backgroundF, contentFrame])

    doc = SIBillDocTemplate("bill.pdf", pagesize=letter, showBoundary=0, allowSplitting=0)
    doc.addPageTemplates([firstPage, secondPage])

    Elements = []


    # First page
    image = Image("images/EmeraldCityBackground.png",letter[0], letter[1])
    Elements.append(image)

    #print str(dom.xml_select(u'/ub:utilitybill/ub:skylinebill/ub:issued')[0])

    Elements.append(Paragraph("<b>Bill</b> <i>Issued</i> " + str(dom.xml_select(u'/ub:utilitybill/ub:skylinebill/ub:issued')[0]), styles["BillLabel"]))
    Elements.append(UseUpSpace())

    Elements.append(Paragraph("<b>Bill</b> <i>Due</i> <b><i>Date</i></b> XX/XX/XX", styles["BillLabel1"]))
    Elements.append(UseUpSpace())


    # Construct service bill periods
    serviceperiod = [[str(summary.service) + u' service period', str(summary.billperiodbegin), str(summary.billperiodend)] for summary in iter(dom.utilitybill.summary)]

    pprint(serviceperiod)

    Elements.append(Table(serviceperiod, [100,75,75]))
    Elements.append(UseUpSpace())


    Elements.append(Paragraph("<u>Charges Without Skyline</u>", styles["BillLabel"]))
    Elements.append(UseUpSpace())

    Elements.append(Paragraph("<u>With Skyline</u>", styles["BillLabel"]))
    Elements.append(UseUpSpace())

    Elements.append(Table([["Service A", "$100.00", "$50.00"], ["Service B", "$200.00", "$65.00"]], [75,75,50]))
    Elements.append(UseUpSpace())



    Elements.append(NextPageTemplate("SecondPage"));
    Elements.append(PageBreak());

    Elements.append(image)

    Elements.append(Paragraph("Content Frame  asdasd asdas asd as asd asd asd asd asd asd asd asd", styles['Normal']))
    #Elements.append(UseUpSpace())
     
    doc.setProgressCallBack(progress)
    doc.build(Elements)

     
if __name__ == "__main__":  
    go()