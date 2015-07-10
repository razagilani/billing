from xml.sax.saxutils import escape
from StringIO import StringIO
import codecs
import os.path
import sys
from pdfminer.layout import LTComponent, LTChar, LTTextBox, LTTextLine, \
    LTLayoutContainer, LTCurve, LTImage

from core import initialize
from core.extraction.task import _create_bill_file_handler
from sqlalchemy import desc, func
from util.pdf import PDFUtil, apply_recursively_to_pdfminer_ltobj

initialize()

from core.model import Session, UtilBill, Utility

s = Session()
bfh = _create_bill_file_handler()

def bounding_boxes_to_svg(page, filename):
    print filename
    outfile = codecs.open(filename, 'w', 'utf-8')
    outfile.write("""
    <svg version="1.1"
     baseProfile="full"
     xmlns="http://www.w3.org/2000/svg">
    """)

    def write_bounding_box(obj):
        """
        Outputs the bounding box of a layout object into an svg file.
        The text of character objects is also overlayed.
        :param obj: an LTComponent object
        """
        # Note: pdfminer inverts y values (origin is at bottom left of page)

        if isinstance(obj, LTComponent):
            if isinstance(obj, LTChar):
                text_baseline = page.height - obj.y0 - 2
                text_chars = obj.get_text()
                # replace (cid:###), and replace non-ascii chars with "!"
                text_chars = escape(text_chars)

                text_fmt = '<text x="%f" y="%f" fill="black" ' \
                           'font-size="%d">%s</text>\n'
                text_values = (obj.x0, text_baseline, obj.height,
                            text_chars)
                out_text = text_fmt % text_values
                outfile.write(out_text)
                return

            alpha = 1
            if isinstance(obj, LTTextBox):
                color = "#000000"
            elif isinstance(obj, LTTextLine):
                color = "#000000"
                alpha = 0.3
            elif isinstance(obj, LTLayoutContainer):
                # layout containers, eg pages and figures, are blue
                color = "#000066"
            elif isinstance(obj, LTCurve) or isinstance(obj, LTImage):
                # shapes are yellow
                color = "#666600"
            else:
                color = "#000000"

            typename = obj.__class__.__name__
            #pdf miner inverts y coordiantes, relative to the screen
            display_y = page.height - obj.y0 - obj.height
            #make sure lines are visible
            width = max(obj.width, 1)
            height = max(obj.height, 1)

            rect_fmt = '<rect pdfminer-type="%s" style="stroke:%s; ' \
                       'fill:none;" x="%f" y="%f" actual-y = "%f" width="%f" ' \
                       'height="%f" stroke-opacity="%f"/>\n'
            rect_values = (typename, color, obj.x0, display_y, obj.y0, width,
                        height, alpha)
            outfile.write(rect_fmt % rect_values)

    apply_recursively_to_pdfminer_ltobj(page, write_bounding_box)
    outfile.write("</svg>")
    outfile.close()

def print_bills_svg(bills, output_directory):
    print "Printing %d bills..." % len(bills)
    for b in bills:
        fname = "%s_%s" % (b.id, b.sha256_hexdigest)
        fpath = os.path.join(output_directory, fname)

        infile = StringIO()
        bfh.write_copy_to_file(b, infile)
        pages = PDFUtil().get_pdfminer_layout(infile)
        for p in pages:
            bounding_boxes_to_svg(p, "%s_%d.svg" % (fpath, p.pageid))

def download_bills(bills, output_directory):
    """
    Downloads a list of bills nad places the PDFs in givne the output directory.
    """
    print "Downloading %d bills..." % len(bills)
    for b in bills:
        fname = "%s_%s.pdf" % (b.id, b.sha256_hexdigest)
        fpath = os.path.join(output_directory, fname)
        outfile = open(fpath, 'wb')
        bfh.write_copy_to_file(b, outfile)
        print fpath
        outfile.close()

def main(argv):
    import getopt
    def usage():
        print "Usage:"
        print "%s [-u <utility_name>] [-m <max_bills>] [-o " \
              "<output_directory>] [-p] [<id>...]" % argv[0]
        print "Options:"
        print "-u <util_name>, --utility-name <util_name>   Filter bills by utility."
        print "-m <max>, --max-bills <max>                  Download at most <max> bills."
        print "-o <dir>, --output-directory <dir>           Output directory [default:./]"
        print "-p, --print-svg                              Print an SVG of " \
              "bounding boxes instead of download the PDF"
        return 100

    if len(argv) == 1:
        return usage()
    try:
        (opts, args) = getopt.getopt(argv[1:], 'u:m:o:p', ['utility-name=',
            'max-bills=', 'output-directory=', 'print-svg'])
    except getopt.GetoptError:
        return usage()

    is_bulk = False
    max_bills = None
    output_directory = "./"
    utility_id = None
    print_svg = False
    for k, v in opts:
        if k in ['-u', '--utility-name']:
            is_bulk = True
            utility_id = s.query(Utility.id).filter(Utility.name==v).one()
        if k in ['-m', '--max-bills']:
            is_bulk = True
            max_bills = v
        if k in ['-o', '--output-directory']:
            output_directory = v
        if k in ['-p', '--print-svg']:
            print_svg = True

    bills = []

    if is_bulk:
        #get bills with valid sha256 digest, ie with valid filename
        bulk_query = s.query(UtilBill).filter(UtilBill.sha256_hexdigest != None,
        UtilBill.sha256_hexdigest != '').order_by(
        func.random())
        if utility_id:
            bulk_query = bulk_query.filter(UtilBill.utility_id==utility_id)
        if max_bills:
            bulk_query = bulk_query.limit(max_bills)
        bills += bulk_query.all()

    bill_ids = args
    if bill_ids:
        id_query = s.query(UtilBill).filter(UtilBill.id.in_(bill_ids))
        bills += id_query.all()

    if bills:
        if print_svg:
            print_bills_svg(bills, output_directory)
        else:
            download_bills(bills, output_directory)
    else:
        print "No bills to download."

    return

if __name__ == '__main__': sys.exit(main(sys.argv))