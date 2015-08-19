"""
A test script for a function that gets charges from a bill regardless of its
layout. See documentation for :func:`charge_gobbler` below.
"""

from sqlalchemy import func

from billentry.billentry_model import BEUtilBill
from core import initialize
from core.extraction.extraction import Extractor
from core.extraction.task import _create_bill_file_handler
from core.extraction.type_conversion import convert_table_charges
from exc import ConversionError, ExtractionError
from util.layout import TEXTLINE
from util.pdf import PDFUtil

initialize()

from core.model import Session, UtilBill, Charge

s = Session()
bfh = _create_bill_file_handler()

def get_bill(id):
    return s.query(UtilBill).filter(UtilBill.id == id).one()

def get_extractor(id):
    return s.query(Extractor).filter(Extractor.extractor_id == id).one()

def charge_gobbler(bill, debug=False):
    """
    Finds and processes charges on a given bill.
    This function searches for all text boxes on a bill that match an
    existing charge name.
    If one is found, the charge rate and value are captured by looking at
    textboxes on the same row.
    This works under the assumption that charges are stored in a table
    format, with charge names on the left and charge values on the right.
    This assumption doesn't always hold true (e.g. some bills have the charge
    name and value in the same textbox, and multiple charges on the same
    horizontal line). When this is the case the function acts conservatively,
    and simply ignores those textboxes.

    This function doesn't find *all* charges for a bill, but works for almost
    any format, and captures supply charges that are often not found in a
    single, predictable region on the page, so in some cases this is more
    effective than a layout extractor.
    Thus, this could be a good preliminary tool for populating the database
    with charges of bills, before using layout extractors and human review.

    :param bill: The bill to get charges from
    :return: A list of charges, or an error
    """
    pages = bill.get_layout(bfh, PDFUtil())
    pages = [filter(lambda o: o.type == TEXTLINE, p) for p in pages]

    # get charge names from the database
    q = s.query(Charge.description, Charge.rsi_binding).filter(
        (Charge.description != 'New Charge - Insert description here') &
        (Charge.description != '')).distinct()
    charge_results = q.all()

    # find charges in bill
    charge_rows = []
    for p in pages:
        obj_index = 0
        while obj_index < len(p):
            obj = p[obj_index]
            sanitized_textline = Charge.description_to_rsi_binding(obj.text)
            if not sanitized_textline:
                obj_index += 1
                continue

            matching_charge = None
            for c in charge_results:
                sanitized_charge_name = Charge.description_to_rsi_binding(
                    c.description)
                if sanitized_textline == sanitized_charge_name:
                    matching_charge = c
                    break
            if matching_charge is None:
                obj_index += 1
                continue

            # get whole row to the right of current box
            row = [obj.text.strip()]
            obj_index += 1
            while obj_index < len(p) and p[obj_index].bounding_box.y0 == \
                    obj.bounding_box.y0:
                row.append(p[obj_index].text.strip())
                obj_index += 1
            # ignore rows with only one piece of text, as they are most
            # likely not charges.
            if len(row) > 1:
                charge_rows.append(row)

    # process these charges
    try:
        new_charges = convert_table_charges(charge_rows)
        if debug:
            for r in charge_rows:
                print "\033[35m %s \033[0m" % r
            for c in new_charges:
                print "\033[34m Charge: desc = %s, rsi = %s, total = %.2f " \
                      "\033[" \
                      "0m" % ( c.description, c.rsi_binding, c.target_total)
        return new_charges
    except ConversionError as ce:
        return ce

def main():
    q = s.query(UtilBill).filter(UtilBill.sha256_hexdigest != None,
        UtilBill.sha256_hexdigest != '')
    q = q.filter(UtilBill.utility_id > 2, UtilBill.utility_id != 5,
        UtilBill.utility_id != 34)
    q = q.order_by(func.random()).limit(100)
    bills = q.all()
    success = empty = error = 0
    # bills = [get_bill(26517)]
    for b in bills:
        out = charge_gobbler(b, debug=True)
        if isinstance(out, ExtractionError):
            print "error on bill id %d" % b.id
            print "\033[31m %s \033[0m" % out
            error += 1
        if isinstance(out, list):
            print "Bill #%d has %d charges." % (b.id, len(out))
            if len(out) == 0:
                empty += 1
            else:
                success += 1
        s.commit()
        print "success: %d, empty: %d, error: %d" % (success, empty, error)
    return

if __name__ == '__main__':
    main()
