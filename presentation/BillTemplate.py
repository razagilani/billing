from reportlab.platypus import BaseDocTemplate, Paragraph, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace

from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class SIBillDocTemplate(BaseDocTemplate):
    """Structure Skyline Innovations Bill. """
    #_invalidInitArgs = ('pageTemplates',)

    #def handle_pageBegin(self):
    #    '''override base method to add a change of page template after the firstpage.
    #    '''
    #    self._handle_pageBegin()
    #    self._handle_nextPageTemplate('Later')

    def build(self,flowables, canvasmaker=canvas.Canvas):
        """build the document using the flowables.  Annotate the first page using the onFirstPage
               function and later pages using the onLaterPages function.  The onXXX pages should follow
               the signature

                  def myOnFirstPage(canvas, document):
                      # do annotations and modify the document
                      ...

               The functions can do things like draw logos, page numbers,
               footers, etcetera. They can use external variables to vary
               the look (for example providing page numbering or section names).
        """
        #self._calc()    #in case we changed margins sizes etc
        #frameT = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
        #self.addPageTemplates([PageTemplate(id='First',frames=frameT, onPage=onFirstPage,pagesize=self.pagesize),
        #                PageTemplate(id='Later',frames=frameT, onPage=onLaterPages,pagesize=self.pagesize)])
        #if onFirstPage is _doNothing and hasattr(self,'onFirstPage'):
        #    self.pageTemplates[0].beforeDrawPage = self.onFirstPage
        #if onLaterPages is _doNothing and hasattr(self,'onLaterPages'):
        #    self.pageTemplates[1].beforeDrawPage = self.onLaterPages
        BaseDocTemplate.build(self,flowables, canvasmaker=canvasmaker)
        
    #def beforePage(self):
    #    print "Before Page: ", self.pageTemplate.id
        
    #def afterPage(self):
    #    print "After Page"
        
        
    #def handle_pageBegin(self):
    #    print "handle_pageBegin"
    #    BaseDocTemplate.handle_pageBegin(self)



defaultPageSize = letter
PAGE_HEIGHT=letter[1]; PAGE_WIDTH=letter[0]
Title = "Hello world"
pageinfo = "platypus example"


def myFirstPage(canvas, doc):
   canvas.saveState()
   canvas.setFont('Times-Bold',16)
   canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-108, Title)
   canvas.setFont('Times-Roman',9)
   canvas.drawString(inch, 0.75 * inch, "First Page / %s" % pageinfo)
   canvas.restoreState()

     
def myLaterPages(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Roman',9)
    canvas.drawString(inch, 0.75 * inch, "Page %d %s" % (doc.page, pageinfo))
    canvas.restoreState()
     

def progress(type,value):
    print type, value
     
#def myTemplateOnPage():

#def myTemplateOnPageEnd():

     
def go():


    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BillLabel', 
        fontName='Helvetica', 
        fontSize=10, 
        leading=0) 
        )

    style = styles["BillLabel"]


    # 612 792
    backgroundF = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, showBoundary=0)
    billIssueDateF = Frame(75, 675, 150, 12, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, showBoundary=1)
    billDueDateF = Frame(225, 675, 150, 12, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, showBoundary=1)

    contentFrame = Frame(100,100, 200,200, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=1)
    serviceAddrFrame = Frame(200,200, 300, 300, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=1)

    firstPage = PageTemplate(id="FirstPage",frames=[backgroundF, billIssueDateF, billDueDateF])


    rbackgroundFrame = Frame(400,400, 100, 100, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, showBoundary=1)
    rcontentFrame = Frame(600,600, 100,100, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=1)

    secondPage = PageTemplate(id="SecondPage",frames=[rbackgroundFrame, rcontentFrame])

    doc = SIBillDocTemplate("bill.pdf", pagesize=letter, showBoundary=1, allowSplitting=0)
    doc.addPageTemplates([firstPage, secondPage])

    Elements = []

    image = Image("images/EmeraldCityBackground.png",letter[0], letter[1])
    Elements.append(image)

    Elements.append(Paragraph("<b>Bill Issued:</b> MMM DD YYYY", style))
    #Elements.append(UseUpSpace())

    Elements.append(Paragraph("<b>Bill Due Date:</b> MMM DD YYYY", style))
    #Elements.append(UseUpSpace())


    Elements.append(NextPageTemplate("SecondPage"));

    Elements.append(Paragraph("Content Frame", style))
    #Elements.append(UseUpSpace())


    Elements.append(Paragraph("Service Frame", style))
    #Elements.append(UseUpSpace())

    Elements.append(Paragraph("Background Frame 1", style))
    #Elements.append(UseUpSpace())

    Elements.append(Paragraph("Content Frame 1", style))
    #Elements.append(UseUpSpace())

    Elements.append(Paragraph("Service Frame", style))
    #Elements.append(UseUpSpace())




    #image = Image("images/EmeraldCityBackground.png",letter[0], letter[1])
    #Elements.append(image)
     
    '''
    Elements.append(PageBreak());
     
    for i in range(4):
         bogustext = ("This is Paragraph number %s. " % i) *20
         p = Paragraph(bogustext, style)
         Elements.append(p)
         Elements.append(Spacer(1,0.2*inch))

    '''
    doc.setProgressCallBack(progress)
    doc.build(Elements)

     
if __name__ == "__main__":  
    go()