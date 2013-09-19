from __future__ import division
from mongoengine import Document, EmbeddedDocument
from mongoengine import StringField, ListField, EmbeddedDocumentField, DateTimeField
from datetime import datetime, date
from collections import defaultdict
from decimal import Decimal
import copy
import inspect
import jinja2
import os
import pymongo
from bson import ObjectId
import sys
import traceback
import uuid
import yaml
from math import sqrt, log, exp
from billing.util.mongo_utils import bson_convert, python_convert, format_query
from billing.processing.exceptions import RSIError, RecursionError, NoPropertyError, NoSuchRSIError, BadExpressionError, NoSuchBillException, NoRateStructureError
from billing.processing.state import UtilBill
from copy import deepcopy

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
    '''
    Manages loading and saving rate structures.

    Rate structures are composites from three sources:
    URS - Utility Rate Structure 
    - bill cycle independent global data
    - contains meter requirements to be satisfied by a ReeBill
    - contains RS name and information about the effective period for the  URS
    UPRS - Utility Periodic Rate Structure 
    - bill cycle dependent global data
    - typically contains monthly rate data
    CPRS - Customer Periodic Rate Structure 
    - bill cycle data specific to customer
    - typically contains one or two corrections to accurately compute bill

    When a rate structure is requested for a given ReeBill, the URS is first 
    looked up and its keys merged with what is found in the UPRS and then
    CPRS.  This way, the CPRS augments the UPRS which overrides the URS.

    There will be rules to how this augmentation works.
        Matching keys might just be outright replaced
        Matching keys might have their values be merged into a list
        Matching keys might be renamed

    When the URS, UPRS and CPRS are merged, a probable rate structure exists.
    It may be used to calculate a bill, or prompt a user for additional 
    processing information.
    '''

    def __init__(self, host, port, database, reebill_dao, logger=None,
            **kwargs):
        # TODO **kwargs == bad and should go away
        '''kwargs catches extra junk from config dictionary unpacked into
        constructor arguments.'''
        #try:
            #self.connection = pymongo.Connection(host, int(port))
        #except Exception as e: 
            #print >> sys.stderr, "Exception Connecting to Mongo:" + str(e)
            #raise e
        #self.database = self.connection[database]
        #self.collection = self.database['ratestructure']
        self.reebill_dao = reebill_dao
        self.logger = logger

    def _get_probable_rsis(self, session, utility, service,
            rate_structure_name, period, distance_func=manhattan_distance,
            weight_func=exp_weight_with_min(0.5, 7, 0.000001),
            threshold=RSI_PRESENCE_THRESHOLD, ignore=lambda x: False,
            verbose=False):
        '''Returns list of RSI dictionaries: a guess of what RSIs will be in a
        new bill for the given rate structure during the given period. The list
        will be empty if no guess could be made. 'threshold' is the minimum
        score (between 0 and 1) for an RSI to be included. 'ignore' is an
        optional function to exclude UPRSs from the input data (used for
        testing).'''
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
                # get period dates: unfortunately this requires loading the
                # bill TODO this sucks--figure out how to avoid it, especially
                # the part that involves using supposedly private methods and
                # directly accessing document structure
                #reebill = self.reebill_dao.load_reebill(uprs['_id']['account'],
                        #uprs['_id']['sequence'], version=uprs['_id']['version'])

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
            self.logger.info('%35s %s %s' % ('binding:', 'weight:', 'normalized weight %:'))
        for binding, weight in scores.iteritems():
            normalized_weight = weight / total_weight[binding] if \
                    total_weight[binding] != 0 else 0
            if self.logger:
                self.logger.info('%35s %f %5d' % (binding, weight, 100 * normalized_weight))

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
        
        'ignore' is a boolean-valued
        function that should return True when given a UPRS document that should
        be excluded from prediction.
        
        The returned document has no _id, so the caller can add one before
        saving.'''
        return RateStructure(type='UPRS', rates=self._get_probable_rsis(
                session, utility, service, rate_structure_name, (start, end),
                ignore=ignore))

    def _load_combined_rs_dict(self, utilbill, reebill=None):
        '''Returns a dictionary of combined rate structure (derived from URS,
        UPRS, and CPRS) belonging to the given state.UtilBill.
        
        If 'reebill' is None, this is based on the "current" UPRS and CPRS
        documents, i.e. the ones whose _id is in the utilbill table.

        If a ReeBill is given, this is based on the UPRS and CPRS documents for
        the version of the utility bill associated with the current
        reebill--either the same as the "current" ones if the reebill is
        unissued, or frozen ones (whose _ids are in the utilbill_reebill table)
        if the reebill is issued.
        '''
        urs = self.load_urs(utilbill.utility, utilbill.rate_class)
        uprs = self.load_uprs_for_utilbill(utilbill, reebill=reebill)
        cprs = self.load_cprs_for_utilbill(utilbill, reebill=reebill)

        # make sure "rsi_binding" is unique within UPRS and CPRS (not that we
        # have ever had a problem with this, but the data structure allows it)
        for rs in (uprs, cprs):
            for rsi in rs.rates:
                if any(other.rsi_binding == rsi.rsi_binding and other != rsi
                        for other in rs.rates):
                    raise RSIError('Multiple RSIs have rsi_binding "%s"' %
                            rsi.rsi_binding)

        # RSIs in CRPS override RSIs in URS with same "rsi_binding"
        rsis = {rsi.rsi_binding: rsi for rsi in uprs.rates}
        rsis.update({rsi.rsi_binding: rsi for rsi in cprs.rates})
        return RateStructure(rates=rsis.values(), registers=urs.registers)


    def load_rate_structure(self, utilbill, reebill=None):
        '''Returns the combined rate structure (CPRS, UPRS, URS) dictionary for
        the given state.UtilBill.
        
        If 'reebill' is None, this is based on the "current" UPRS and CPRS
        documents, i.e. the ones whose _id is in the utilbill table.

        If a ReeBill is given, this is based on the UPRS and CPRS documents for
        the version of the utility bill associated with the current
        reebill--either the same as the "current" ones if the reebill is
        unissued, or frozen ones (whose _ids are in the utilbill_reebill table)
        if the reebill is issued.'''
        return RateStructure(self._load_combined_rs_dict(utilbill,
                reebill=reebill))
    
    def load_urs(self, utility_name, rate_structure_name):
        '''Loads Utility (global) Rate Structure document from Mongo.
        '''
        result = URS.objects.get(id__type='URS', id__utility_name=utility_name,
                id__rate_structure_name=rate_structure_name)
        assert result.id.type == 'URS'
        return result

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
        '''Loads and returns a rate structure document by its _id.'''
        assert _id is not None
        doc = RateStructure.objects.get(id=ObjectId(_id))
        return doc

    def _delete_rs_by_id(self, _id):
        '''Deletes the rate structure document with the given _id. Raises a
        MongoError if deletion fails.'''
        result = self.collection.remove({'_id': ObjectId(_id)}, safe=True)
        # TODO is there a way to specify safe more or get the result "err" and "n"?

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

    def load_uprs(self, id):
        '''Returns a Utility Periodic Rate Structure document from Mongo.'''
        query = {"_id": ObjectId(id), "type": "UPRS"}
        uprs = self.collection.find_one(query)
        if uprs is None:
            raise ValueError('Could not find UPRS: query was %s' %
                    format_query(query))
        return uprs

    def load_cprs(self, id):
        '''Returns a Customer Periodic Rate Structure document from Mongo.'''
        query = {"_id": ObjectId(id), "type": "CPRS"}
        cprs = self.collection.find_one(query)
        if cprs is None:
            raise ValueError('Could not find CPRS: query was %s' %
                    format_query(query))
        return cprs

    def delete_rs_docs_for_utilbill(self, utilbill):
        '''Removes the UPRS and CPRS documents for the given state.UtilBill.
        This should be done when the utility bill is deleted. Raises a
        MongoError if deletion fails.'''
        self._delete_rs_by_id(utilbill.uprs_document_id)
        self._delete_rs_by_id(utilbill.cprs_document_id)






class RSIFormulaIdentifier(object):
    def __init__(self, quantity):
        self.quantity = quantity
class RateStructureItem(EmbeddedDocument):
    rsi_binding = StringField(required=True)
    quantity = StringField(required=True)
    quantity_units = StringField()
    rate = StringField(required=True)
    rate_units = StringField()
    round_rule = StringField()
    description = StringField()
    uuid = StringField()

    def compute_charge(self, register_quantities):
        '''Evaluates this RSI's "quantity" and "rate" formulas, given the
        readings of registers in 'register_quantities' (a dictionary mapping
        register names to quantities), and returns (quantity result, rate
        result).
        '''
        # identifiers in RSI formulas end in ".quantity"; the only way to
        # evaluate these as Python code is to turn each of the key/value pairs
        # in 'register_quantities' into an object with a "quantity" attribute
        register_quantities = {reg_name: RSIFormulaIdentifier(q) for reg_name,
                q in register_quantities.iteritems()}
        quantity = eval(self.quantity, {}, register_quantities)
        rate = eval(self.rate, {}, register_quantities)
        return quantity, rate

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
        'db_alias': 'rate_structure',
        'collection': 'rate_structure',
        'allow_inheritance': True
    }

    type = StringField(required=True)
    registers = ListField(field=EmbeddedDocumentField(Register))

    # NOTE for a ListField, required=True means it must be nonempty; it is not
    # possible to have an optional ListField (?) because there is a default
    # value of []
    rates = ListField(field=EmbeddedDocumentField(RateStructureItem))

    def rsis_dict(self):
        result = {}
        for rsi in self.rates:
            binding = rsi['rsi_binding']
            if binding in result:
                raise ValueError('Duplicate rsi_binding "%s"' % binding)
            result[binding] = rsi
        return result

#class URS(RateStructure):
    #meta = {
        #'db_alias': 'rate_structure',
        #'collection': 'rate_structure',
        #'allow_inheritance': True
    #}
    #utility_name = StringField(required=True)
    #rate_structure_name = StringField(required=True)

class URSID(EmbeddedDocument):
    type = StringField(required=True) # TODO figure out how to hard-code this as "URS"
    rate_structure_name=StringField(required=True)
    utility_name=StringField(required=True)

    # these are not used for anything but may be in some existing documents
    effective=DateTimeField()
    expires=DateTimeField()

# TODO deal with problem of "type" being in URS id and in URS itself since it
# inherits from RateStructure--the solution is probably to remove the "type"
# field and make them separate classes
class URS(RateStructure):
    meta = {
        'db_alias': 'rate_structure',
        #'collection': 'rate_structure',
        #'allow_inheritance': True
    }
    # MongoEngine uses the name "id" for the document's _id
    id = EmbeddedDocumentField(URSID, primary_key=True)
    #utility_name = StringField(required=True)
    #rate_structure_name = StringField(required=True)
