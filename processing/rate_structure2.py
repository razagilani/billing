from __future__ import division
import ast
from itertools import chain
from datetime import datetime, date
from collections import defaultdict
import sys
import uuid
from math import sqrt, log, exp
from bson import ObjectId
from mongoengine import Document, EmbeddedDocument
from mongoengine import StringField, ListField, EmbeddedDocumentField, DateTimeField
from billing.util.mongo_utils import bson_convert, python_convert, format_query
from billing.processing.exceptions import FormulaError, FormulaSyntaxError
from billing.processing.state import UtilBill

# minimum normlized score for an RSI to get included in a probable UPRS
# (between 0 and 1)
RSI_PRESENCE_THRESHOLD = 0.5

def manhattan_distance(p1, p2):
    # note that 15-day offset is a 30-day distance, 30-day offset is a
    # 60-day difference
    delta_begin = abs(p1[0] - p2[0]).days
    delta_end = abs(p1[1] - p2[1]).days
    return delta_begin + delta_end

def gaussian(height, center, fwhm):
    def result(x):
        sigma =  fwhm / 2 * sqrt(2 * log(2))
        return height * exp(- (x - center)**2 / (2 * sigma**2))
    return result

def exp_weight(a, b):
    return lambda x: a**(x * b)

def exp_weight_with_min(a, b, minimum):
    '''Exponentially-decreasing weight function with a minimum value so it's
    always nonnegative.'''
    return lambda x: max(a**(x * b), minimum)


class RateStructureDAO(object):
    '''Loads and saves RateStructure objects. Also responsible for generating
    predicted UPRSs based on existing ones.
    '''

    def __init__(self, reebill_dao, logger=None, **kwargs):
        # TODO **kwargs == bad and should go away
        '''kwargs catches extra junk from config dictionary unpacked into
        constructor arguments.'''
        self.reebill_dao = reebill_dao
        self.logger = logger

    def _get_probable_rsis(self, session, utility, service,
            rate_structure_name, period, distance_func=manhattan_distance,
            weight_func=exp_weight_with_min(0.5, 7, 0.000001),
            threshold=RSI_PRESENCE_THRESHOLD, ignore=lambda x: False,
            verbose=False):
        '''Returns list of RateStructureItems: a guess of what RSIs will be in
        a new bill for the given rate structure during the given period. The
        list will be empty if no guess could be made. 'threshold' is the
        minimum score (between 0 and 1) for an RSI to be included. 'ignore' is
        an optional function to exclude UPRSs from the input data.
        '''
        # load all UPRSs and their utility bill period dates (to avoid repeated
        # queries)
        all_uprss = [(uprs, start, end) for (uprs, start, end) in
                self._load_uprss_for_prediction(session, utility,
                service, rate_structure_name) if not ignore(uprs)]

        # find every RSI binding that ever existed for this rate structure
        bindings = set()
        for uprs, _, _ in all_uprss:
            for rsi in uprs.rates:
                bindings.add(rsi.rsi_binding)
        
        # for each UPRS period, update the presence/absence score, total
        # presence/absence weight (for normalization), and full RSI dictionary
        # for the occurrence of each RSI binding closest to the target period
        scores = defaultdict(lambda: 0)
        total_weight = defaultdict(lambda: 0)
        closest_occurrence = defaultdict(lambda: (sys.maxint, None))
        for binding in bindings:
            for uprs, start, end in all_uprss:
                # calculate weighted distance of this UPRS period from the
                # target period
                distance = distance_func((start, end), period)
                weight = weight_func(distance)

                # update score and total weight for this binding
                try:
                    rsi_dict = next(rsi for rsi in uprs.rates if
                            rsi.rsi_binding == binding)
                    # binding present in UPRS: add 1 * weight to score
                    scores[binding] += weight 
                    # if this distance is closer than the closest occurence seen so
                    # far, put the RSI dictionary in closest_occurrence
                    if distance < closest_occurrence[binding][0]:
                        closest_occurrence[binding] = (distance, rsi_dict)
                except StopIteration:
                    # binding not present in UPRS: add 0 * weight to score
                    pass
                # whether the binding was present or not, update total weight
                total_weight[binding] += weight


        # include in the result all RSI bindings whose normalized weight
        # exceeds 'threshold', with the rate and quantity formulas it had in
        # its closest occurrence.
        result = []
        if verbose:
            self.logger.info('Predicted RSIs for %s %s %s - %s' % (utility,
                    rate_structure_name, period[0], period[1]))
            self.logger.info('%35s %s %s' % ('binding:', 'weight:',
                'normalized weight %:'))
        for binding, weight in scores.iteritems():
            normalized_weight = weight / total_weight[binding] if \
                    total_weight[binding] != 0 else 0
            if self.logger:
                self.logger.info('%35s %f %5d' % (binding, weight,
                        100 * normalized_weight))

            # note that total_weight[binding] will never be 0 because it must
            # have occurred somewhere in order to occur in 'scores'
            if normalized_weight >= threshold:
                rsi_dict = closest_occurrence[binding][1]
                rate, quantity = 0, 0
                try:
                    rate = rsi_dict.rate
                    quantity = closest_occurrence[binding][1].quantity
                except KeyError:
                    if self.logger:
                        self.logger.error('malformed RSI: %s' % rsi_dict)
                result.append(RateStructureItem(rsi_binding=binding, rate=rate,
                    quantity=quantity, uuid1=str(uuid.uuid1())))
        return result

    def get_probable_uprs(self, session, utility, service, rate_structure_name,
            start, end, ignore=lambda x: False):
        '''Returns a guess of the rate structure for a new utility bill of the
        given utility name, service, and dates.
        
        'ignore' is a boolean-valued function that should return True when
        given a UPRS document should be excluded from prediction.
        
        The returned document has no _id, so the caller can add one before
        saving.'''
        return RateStructure(type='UPRS', rates=self._get_probable_rsis(
                session, utility, service, rate_structure_name, (start, end),
                ignore=ignore))

    def load_uprs_for_utilbill(self, utilbill, reebill=None):
        '''Loads and returns a UPRS document for the given state.Utilbill.

        If 'reebill' is None, this is the "current" document, i.e. the one
        whose _id is in the utilbill table.

        If a ReeBill is given, this is the UPRS document for the version of the
        utility bill associated with the current reebill--either the same as
        the "current" one if the reebill is unissued, or a frozen one (whose
        _id is in the utilbill_reebill table) if the reebill is issued.'''
        if reebill is None or reebill.document_id_for_utilbill(utilbill) \
                is None:
            return self._load_rs_by_id(utilbill.uprs_document_id)
        return self._load_rs_by_id(reebill.uprs_id_for_utilbill(utilbill))

    def load_cprs_for_utilbill(self, utilbill, reebill=None):
        '''Loads and returns a CPRS document for the given state.Utilbill.

        If 'reebill' is None, this is the "current" document, i.e. the one
        whose _id is in the utilbill table.

        If a ReeBill is given, this is the CPRS document for the version of the
        utility bill associated with the current reebill--either the same as
        the "current" one if the reebill is unissued, or a frozen one (whose
        _id is in the utilbill_reebill table) if the reebill is issued.'''
        if reebill is None or reebill.document_id_for_utilbill(utilbill) \
                is None:
            return self._load_rs_by_id(utilbill.cprs_document_id)
        return self._load_rs_by_id(reebill.cprs_id_for_utilbill(utilbill))

    def _load_rs_by_id(self, _id):
        '''Loads and returns a rate structure document by its _id (string).
        '''
        assert isinstance(_id, basestring)
        doc = RateStructure.objects.get(id=ObjectId(_id))
        return doc

    def _delete_rs_by_id(self, _id):
        '''Deletes the rate structure document with the given _id. Raises a
        MongoError if deletion fails.
        '''
        result = RateStructure.objects.get(id=ObjectId(_id)).delete()
        # TODO is there a way to specify safe mode or get the result "err" and
        # "n"? look at 'write_concern' argument

    def _load_uprss_for_prediction(self, session, utility_name, service,
            rate_structure_name, verbose=False):
        '''Returns list of (UPRS document, start date, end date) tuples
        with the given utility and rate structure name.'''
        # skip Hypothetical utility bills--they have a UPRS document, but it's
        # fake, so it should not count toward the probability of RSIs being
        # included in other bills. (ignore utility bills that are
        # 'SkylineEstimated' or 'Hypothetical')
        utilbills = session.query(UtilBill)\
                .filter(UtilBill.service==service)\
                .filter(UtilBill.utility==utility_name)\
                .filter(UtilBill.rate_class==rate_structure_name)\
                .filter(UtilBill.state <= UtilBill.SkylineEstimated)
        result = []
        for utilbill in utilbills:
            if utilbill.uprs_document_id is None:
                self.logger.warning(('ignoring utility bill for %(account)s '
                    'from %(start)s to %(end)s: has state %(state)s but lacks '
                    'uprs_document_id') % {'state': utilbill.state,
                    'account': utilbill.customer.account, 'start':
                    utilbill.period_start, 'end': utilbill.period_end})
                continue
                            
            # load UPRS document for the current version of this utility bill
            # (it never makes sense to use a frozen utility bill's URPS here
            # because the only UPRSs that should count are "current" ones)
            doc = self.load_uprs_for_utilbill(utilbill)
            # only include RS docs that correspond to a current utility bill
            # (not one belonging to a reebill that has been corrected); this
            # will be subtly broken until old versions of utility bills are
            # excluded from MySQL: see
            # https://www.pivotaltracker.com/story/show/51683847
            result.append((doc, utilbill.period_start, utilbill.period_end))
        return result

    def delete_rs_docs_for_utilbill(self, utilbill):
        '''Removes the UPRS and CPRS documents for the given state.UtilBill.
        This should be done when the utility bill is deleted. Raises a
        MongoError if deletion fails.'''
        self._delete_rs_by_id(utilbill.uprs_document_id)
        self._delete_rs_by_id(utilbill.cprs_document_id)


class RateStructureItem(EmbeddedDocument):
    '''A Rate Structure Item describes how a particular charge is computed, and
    computes the charge according to a formula using various named values as
    inputs (include register readings from a utility meter and other charges in
    the same bill).
    '''
    # unique name that matches this RSI with a charge on a bill
    rsi_binding = StringField(required=True)

    # descriptive human-readable name (rarely used)
    description = StringField()

    # the 'quantity' and 'rate' formulas provide the formula for computing the
    # charge when multiplied together; the separation into 'quantity' and
    # 'rate' is somewhat arbitrary
    quantity = StringField(required=True)
    quantity_units = StringField()
    rate = StringField(required=True)
    rate_units = StringField()

    # currently not used
    round_rule = StringField()

    # a way of identifying a particular RSI when edited in the browser
    uuid = StringField()

    def _parse_formulas(self):
        '''Parses the 'quantity' and 'rate' formulas as Python code using the
        'ast' module, and returns the tuple (quantity formula AST, rate formula
        AST). Raises FormulaSyntaxError either one couldn't be parsed.
        '''
        def parse_formula(name):
            try:
                return ast.parse(getattr(self, name))
            except SyntaxError:
                raise FormulaSyntaxError('Syntax error in %s formula of RSI '
                        '"%s":\n%s' % (name, self.rsi_binding,
                        getattr(self, name)))
        return parse_formula('quantity'), parse_formula('rate')

    def get_identifiers(self):
        '''Generates names of all identifiers occuring in this RSI's 'quantity'
        and 'rate' formulas (excluding built-in functions). Raises
        FormulaSyntaxError if the quantity or rate formula could not be parsed,
        so this method also provides syntax checking.
        '''
        # This is a horrible way to find out if an ast node is a builtin
        # function, but it seems to work, and I can't come up with a better
        # way. (Note that the type 'builtin_function_or_method' is not a
        # variable in global scope, like 'int' or 'str', so you can't refer to
        # it directly.)
        def _is_built_in_function(node):
            try:
                return eval('type(%s)' % node.id).__name__ \
                        == 'builtin_function_or_method'
            except NameError:
                return False

        # parse the two formulas, and return nodes of the resulting parse tree
        # whose type is ast.Name (and are not a built-in functions as
        # determined by the function above)
        quantity_tree, rate_tree = self._parse_formulas()
        for node in chain.from_iterable((ast.walk(quantity_tree),
                ast.walk(rate_tree))):
            if isinstance(node, ast.Name) and not _is_built_in_function(node):
                yield node.id

    def compute_charge(self, register_quantities):
        '''Evaluates this RSI's "quantity" and "rate" formulas, given the
        readings of registers in 'register_quantities' (a dictionary mapping
        register names to quantities), and returns (quantity result, rate
        result). Raises FormulaSyntaxError if either of the formulas could not
        be parsed.
        '''
        # check syntax
        self._parse_formulas()

        # identifiers in RSI formulas end in ".quantity", ".rate", or ".total";
        # the only way to evaluate these as Python code is to turn each of the
        # key/value pairs in 'register_quantities' into an object with a
        # "quantity" attribute
        class RSIFormulaIdentifier(object):
            def __init__(self, quantity=None, rate=None, total=None):
                self.quantity = quantity
                self.rate = rate
                self.total = total
        register_quantities = {reg_name: RSIFormulaIdentifier(**data) for
                reg_name, data in register_quantities.iteritems()}

        def compute(name):
            formula = getattr(self, name)
            try:
                return eval(formula, {}, register_quantities)
            except Exception as e:
                raise FormulaError(('Error when computing %s for RSI "%s": '
                        '%s') % (name, self.rsi_binding, self.description, e))
        return compute('quantity'), compute('rate')

    def to_dict(self):
        '''String representation of this RateStructureItem to send as JSON to
        the browser.
        '''
        return {
            'rsi_binding': self.rsi_binding,
            'quantity': self.quantity,
            'quantity_units': self.quantity_units,
            'rate': self.rate,
            'rate_units': self.rate_units,
            'round_rule': self.round_rule,
            'description': self.description,
            'uuid': self.uuid,
        }

    def update(self, rsi_binding=None, quantity=None, quantity_units=None,
            rate=None, rate_units=None, round_rule=None, description=None,
            uuid=None):
        if rsi_binding is not None:
            self.rsi_binding = rsi_binding
        if quantity is not None:
            self.quantity = quantity
        if quantity_units is not None:
            self.quantity_units = quantity_units
        if rate is not None:
            self.rate = rate
        if rate_units is not None:
            self.rate_units = rate_units
        if roundrule is not None:
            self.roundrule = roundrule
        if description is not None:
            self.description = description
        if uuid is not None:
            self.uuid = uuid

class Register(EmbeddedDocument):
    # this is the only field that has any meaning, since a "register" in a rate
    # structure document really just means a name
    register_binding = StringField(required=True)

    # these are random junk fields that were inserted in the DB in Rich's code
    quantity = StringField()
    quantity_units = StringField()
    description = StringField()
    uuid = StringField()

class RateStructure(Document):
    meta = {
        'db_alias': 'ratestructure',
        'collection': 'ratestructure',
        'allow_inheritance': True
    }

    type = StringField(required=True)
    registers = ListField(field=EmbeddedDocumentField(Register), default=[])

    rates = ListField(field=EmbeddedDocumentField(RateStructureItem),
            default=[])

    def rsis_dict(self):
        result = {}
        for rsi in self.rates:
            binding = rsi['rsi_binding']
            if binding in result:
                raise ValueError('Duplicate rsi_binding "%s"' % binding)
            result[binding] = rsi
        return result

if __name__ == '__main__':
    import mongoengine
    mongoengine.connect('skyline-dev', host='localhost', port=27017,
            alias='ratestructure')
    print RateStructure.objects.count()
    RateStructure.objects.get(id=ObjectId('527001537eb49a64dde28ac4'))
