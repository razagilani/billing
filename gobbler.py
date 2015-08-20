"""
A test script for a function that gets charges from a bill regardless of its
layout. See documentation for :func:`charge_gobbler` below.
"""
import re

from sqlalchemy import func

from billentry.billentry_model import BEUtilBill
from core import initialize
from core.extraction.extraction import Extractor
from core.extraction.task import _create_bill_file_handler
from core.extraction.type_conversion import convert_table_charges
from exc import ConversionError, ExtractionError
from util import dateutils
from util.layout import TEXTLINE
from util.pdf import PDFUtil

initialize()

from core.model import Session, UtilBill, Charge, RateClass

s = Session()
bfh = _create_bill_file_handler()

def get_bill(id):
    return s.query(UtilBill).filter(UtilBill.id == id).one()

def get_extractor(id):
    return s.query(Extractor).filter(Extractor.extractor_id == id).one()

def normalize_text(text):
    """
    Normalizes text by removing non-alphanumeric characters and replacing
    them with underscores. Trailing and leading non-alphanumeric characters
    are removed.
    :return:
    """
    text = text.upper()
    text = re.sub(r'[^A-Z0-9]', ' ', text)
    text = text.strip().lstrip()
    return re.sub(r'\s+', '_', text)

def sanitize_rate_class_name(text):
    text = re.sub("^rate(?: class)?:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub("service number[\d\s]+", "", text, flags=re.IGNORECASE)
    return text

date_long_format = r'[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4}'
date_mm_dd_yy_format = r'\d{2}\/\d{2}\/\d{2,4}'

def bill_period_gobbler(bill, debug=False):
    """
    A function that attempts to get the billing period of a bill.
    1. First, all dates on the bill are loaded, and their location stored.
    2. Then, pairs of dates that are roughly one month apart are grouped as
     potential start and end dates.
    3. The start and end dates that are geometrically closest (usually in the
     same textbox, so a distance of 0) are then chosen as the most likely
     bill period.
     *** (Note: the x distance is weighted less than the y distance,
     since pieces of text on the same line are more likely to be related than
     pieces of text that are vertically aligned but on different lines.
    4. It's possible for a bill (e.g. for BGE, with both gas and electric
     services) to have multiple periods on it, so an array of possibly
     periods is returned.
    :param bill: The bill to be analyzed
    :return: A list of possible bill periods. Each bill period is a tuple (
    start_date, end_date, distance), where distance is the geometrical
    distance on the bill's page.
    """
    pages = bill.get_layout(bfh, PDFUtil())
    pages = [filter(lambda o: o.type == TEXTLINE, p) for p in pages]
    # check if bill has no text
    if sum(len(p) for p in pages) == 0:
        return None

    dates = []
    for p in pages:
        for obj in p:
            matches = re.findall(date_long_format, obj.text)
            matches += re.findall(date_mm_dd_yy_format, obj.text)
            for s in matches:
                date = dateutils.parse_date(s)
                # store obj to keep track of page number, x, y
                date_obj = {'date': date, 'obj': obj }
                dates.append(date_obj)
    dates = sorted(dates, key=lambda do: do['date'])
    # Find potential ~1 month periods
    periods = []
    for idx, start_obj in enumerate(dates):
        for end_obj in dates[idx+1:]:
            # skip if dates are on a different page
            if start_obj['obj'].page_num != end_obj['obj'].page_num:
                continue
            # bill period length must be in [20, 40]
            if (end_obj['date'] - start_obj['date']).days < 20:
                continue
            if (end_obj['date'] - start_obj['date']).days > 40:
                break
            # get geometric (manhattan) distance of text boxes
            dx = abs(start_obj['obj'].bounding_box.x0 -
                     end_obj['obj'].bounding_box.x0)
            dy = abs(start_obj['obj'].bounding_box.y1 -
                     end_obj['obj'].bounding_box.y1)
            # x distance is less improtant than y - pieces of text on
            # different lines are less likely to be related.
            distance = 0.25 * dx + 1.0 * dy
            periods.append((start_obj['date'], end_obj['date'], distance))

    # sort by geometric distance on bill, after removing duplicate values
    periods = sorted(set(periods), key=lambda p: p[2])
    # get only the pairs of dates that are closest to each other on the page
    likeliest_periods = filter(lambda p: p[2] == periods[0][2], periods)

    if debug:
        for p in periods:
            print "\033[34m Period: start = %s, end = %s, distance %.2f \033[" \
                  "0m" % (p[0], p[1], p[2])

    return likeliest_periods

def rate_class_gobbler(bill, debug=False):
    """
    Function that looks for pieces of text in a bill that matches an existing
    rate class. The rate classe for the bill's utility are loaded, and are
    normalized to a standard name to account for formatting differences in
    the database. Then, for any piece of text that matches an existing rate
    class name, the corresponding rate class is returned.

    Multiple rate classes are returned to either a) indicate that an
    ambiguous result was found or b) to deal, for instance, with BGE bills
    which have rate classes for both their gas and electric services.

    :param bill: The bill to analyze
    :return: A list of rate classes, or None if the bill has no text.
    """
    pages = bill.get_layout(bfh, PDFUtil())
    pages = [filter(lambda o: o.type == TEXTLINE, p) for p in pages]
    # check if bill has no text
    if sum(len(p) for p in pages) == 0:
        return None

    # get rate classes from the database
    q = s.query(RateClass).filter(RateClass.utility_id == bill.utility_id)
    rate_classes = q.all()
    if len(rate_classes) == 0:
        return []

    # group rate classes by normalized name
    rc_map = {normalize_text(rc.name): rc for rc in rate_classes}
    print "%d rate class names found." % len(rc_map.keys())

    # find rate class in bill
    matching_rate_classes = {}
    for p in pages:
        for obj in p:
            sanitized_textline = sanitize_rate_class_name(obj.text)
            normalized_textline = normalize_text(sanitized_textline)
            if not normalized_textline:
                continue

            for rc in rc_map.values():
                normalized_rate_class_name = normalize_text(rc.name)
                if normalized_textline == normalized_rate_class_name:
                    matching_rate_classes[normalized_rate_class_name] = rc
                    break
    if debug:
        for rc in matching_rate_classes.values():
            print "\033[34m Rate Class: name = %s, utility = %s \033[0m" \
                  % ( rc.name, rc.utility.name)
    return matching_rate_classes.values()

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
    # check if bill has no text
    if sum(len(p) for p in pages) == 0:
        return None

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
    # q = q.filter(UtilBill.utility_id > 2, UtilBill.utility_id != 5,
    #     UtilBill.utility_id != 34)
    q = q.order_by(func.random()).limit(100)
    bills = q.all()
    # bills = [get_bill(14852)]
    success = empty = notext = error = 0
    for b in bills:
        out = rate_class_gobbler(b, debug=True)
        if out is None:
            print "Bill id %d has no text." % b.id
            notext += 1
        if isinstance(out, ExtractionError):
            print "error on bill id %d" % b.id
            print "\033[31m %s \033[0m" % out
            error += 1
        if isinstance(out, list):
            print "Bill #%d has %d rate classes." % (b.id, len(out))
            if len(out) == 0:
                empty += 1
            else:
                success += 1
        s.commit()
        print "success: %d, empty: %d, no text: %d, error: %d" % (success,
                empty, notext, error)
    return

if __name__ == '__main__':
    main()