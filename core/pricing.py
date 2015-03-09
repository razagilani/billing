from __future__ import division
from collections import defaultdict
from datetime import date, timedelta
from sys import maxint

from exc import NoSuchBillException
from core.model import Charge, Utility, RateClass


class PricingModel(object):
    '''Responsible for determining what charges are on a given utility bill.
    '''
    def __init__(self, logger=None):
        ''''
        'logger': optional Logger object to record messages about rate
        structure prediction.
        '''
        # TODO instead of using None as logger, use a logger that does nothing,
        # to avoid checking if it's None
        self.logger = logger

    def get_predicted_charges(self, utilbill):
        raise NotImplementedError('Subclasses should override this')

class FuzzyPricingModel(PricingModel):
    '''A pricing model that guesses what charges are going to be on a given
    utility bill by looking at other bills for the same rate class whose period
    dates are "near" that bill.
    '''
    # minimum normlized score for a charge to get included in a bill
    # (between 0 and 1)
    RSI_PRESENCE_THRESHOLD = 0.5

    @staticmethod
    def _manhattan_distance(p1, p2):
        # note that 15-day offset is a 30-day distance, 30-day offset is a
        # 60-day difference
        delta_begin = abs(p1[0] - p2[0]).days
        delta_end = abs(p1[1] - p2[1]).days
        return delta_begin + delta_end

    @staticmethod
    def _exp_weight_with_min(a, b, minimum):
        '''Exponentially-decreasing weight function with a minimum value so it's
        always nonnegative.'''
        return lambda x: max(a**(x * b), minimum)

    def __init__(self, utilbill_loader, logger=None):
        '''
        'utilbill_loader': an object that has a 'load_utilbills' method
        returning an iterable of state.UtilBills matching criteria given as
        keyword arguments (see state.UtilBillLoader). For testing, this can be
        replaced with a mock object.
        '''
        super(FuzzyPricingModel, self).__init__(logger)
        self._utilbill_loader = utilbill_loader

    def _get_probable_shared_charges(self, period, relevant_bills, charge_type,
                                     threshold=RSI_PRESENCE_THRESHOLD,
                                     ignore=lambda x: False, verbose=False):
        """Constructs and returns a list of :py:class:`Charge`
        instances, each of which is unattached to any :py:class:`UtilBill`.

        The charges returned represent a guess as to which formulas should
        be present on the utilbill.

        :param relevant_bills: iterable of other bills to look at when
        deciding which charges should be included in this bill.
        :param threshold: the minimum score (between 0 and 1) for an RSI to be
        included.
        :param ignore: an optional function to exclude UPRSs from the input data
        """
        assert isinstance(period[0], date) and isinstance(period[1], date)
        assert charge_type in Charge.CHARGE_TYPES
        assert isinstance(threshold, (int, float))
        assert callable(ignore)

        distance_func=self.__class__._manhattan_distance
        weight_func=self.__class__._exp_weight_with_min(0.5, 7, 0.000001)

        # the unique identifier of "the same charge" across more than one bill
        # is a combination of both 'type' (e.g. "distribution" or "supply") and
        # 'rsi_binding' (standardized name). in theory charges with the same
        # rsi_binding always have the same type; that could be guaranteed in
        # by a database constraint but it currently isn't.
        # only rsi_binding values are collected here because only charges
        # matching the 'charge_type' argument are relevant.
        bindings = set()
        for utilbill in relevant_bills:
            for charge in utilbill.charges:
                if charge.type == charge_type:
                    bindings.add(charge.rsi_binding)

        scores = defaultdict(lambda: 0)
        total_weight = defaultdict(lambda: 0)
        closest_occurrence = defaultdict(lambda: (maxint, None))

        for binding in bindings:
            for utilbill in relevant_bills:
                distance = distance_func((utilbill.period_start,
                                          utilbill.period_end), period)
                weight = weight_func(distance)
                try:
                    # an "occurrence of the same charge" is one that has the
                    # same 'rsi_binding' AND the relevant 'type'
                    charge = next(c for c in utilbill.charges if
                                  (c.type, c.rsi_binding) == (
                                  charge_type, binding))
                except StopIteration:
                    pass
                else:
                    if charge.shared:
                        # binding present in charge and shared: add 1 * weight
                        # to score
                        scores[binding] += weight
                        # if this distance is closer than the closest occurrence
                        # seen so far, put charge object in closest_occurrence
                        if distance < closest_occurrence[binding][0]:
                            closest_occurrence[binding] = (distance, charge)
                    else:
                        # binding present in charge but un-shared
                        continue
                # whether the binding was present or not, update total weight
                total_weight[binding] += weight

        # include in the result all charges whose normalized weight
        # exceeds 'threshold', with the rate and quantity formulas it had in
        # its closest occurrence.
        result = []
        if verbose:
            self.logger.info('Predicted charges for %s - %s' % period)
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
                charge = closest_occurrence[binding][1]
                result.append(Charge.formulas_from_other(charge))
        return result

    def _load_relevant_bills_distribution(self, utilbill, ignore_func):
        if None in (utilbill.utility, utilbill.rate_class):
            return []
        return [utilbill for utilbill in
                         self._utilbill_loader.load_real_utilbills(
                             utility=utilbill.utility,
                             rate_class=utilbill.rate_class,
                             processed=True
                         ) if not ignore_func(utilbill)]

    def _load_relevant_bills_supply(self, utilbill, ignore_func):
        if utilbill.supplier is None:
            return []
        return [utilbill for utilbill in
                self._utilbill_loader.load_real_utilbills(
                    supplier=utilbill.supplier, processed=True
                ) if not ignore_func(utilbill)]

    def get_predicted_charges(self, utilbill):
        """Constructs and returns a list of :py:class:`processing.state.Charge`
        instances, each of which is unattached to any
        :py:class:`proessing.state.UtilBill`.

        The charges returned represent a guess as to which formulas should
        be present on the utilbill.

        :utilbill: a :class:`processing.state.UtilBill` instance
        """
        # shared charges
        if (utilbill.period_start, utilbill.period_end) == (None, None):
            # no dates known: no shared charges
            return []

        # if only one date is known, the other one is probably about 30 days
        # away from it, which is enough to guess the charges
        start = utilbill.period_start or utilbill.period_end - timedelta(30)
        end = utilbill.period_end or utilbill.period_start + timedelta(30)

        # only ignore the target bill
        ignore_func = lambda ub:ub.id == utilbill.id

        # same set of relevant bills for both supply and distribution charges
        distribution_relevant_bills = self._load_relevant_bills_distribution(
            utilbill, ignore_func)
        supply_relevant_bills = self._load_relevant_bills_supply(
            utilbill, ignore_func)
        distribution_charges = self._get_probable_shared_charges(
            (start, end), distribution_relevant_bills, Charge.DISTRIBUTION,
            ignore=ignore_func)
        supply_charges = self._get_probable_shared_charges(
            (start, end), supply_relevant_bills, Charge.SUPPLY,
            ignore=ignore_func)

        # result is the union by 'rsi_binding' of all the charges in both groups
        # (supply charges taking priority over distribution over any
        # distribution charges with the same rsi_binding, in case that happens)
        result = dict({c.rsi_binding: c for c in distribution_charges},
                      **{c.rsi_binding: c for c in supply_charges}).values()

        # individual charges:
        # add any charges from the predecessor that are not already there
        try:
            predecessor = self._utilbill_loader.get_last_real_utilbill(
                utilbill.utility_account.account, end=utilbill.period_start,
                utility=utilbill.utility, rate_class=utilbill.rate_class,
                processed=True)
        except NoSuchBillException:
            # if there's no predecessor, there are no charges to add
            pass
        else:
            for charge in predecessor.charges:
                if not (charge.shared or charge.rsi_binding in (
                        c.rsi_binding for c in result)):
                    result.append(Charge.formulas_from_other(charge))

        return result

