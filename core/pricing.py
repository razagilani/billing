from __future__ import division
from collections import defaultdict
from datetime import date, timedelta
from itertools import chain
from logging import getLogger
from sys import maxint

from exc import NoSuchBillException
from core.model import Charge, Utility, RateClass


class PricingModel(object):
    """Responsible for determining what charges are on a given utility bill.
    """
    def get_predicted_charges(self, utilbill):
        raise NotImplementedError('Subclasses should override this')

class FuzzyPricingModel(PricingModel):
    '''A pricing model that guesses what charges are going to be on a given
    utility bill by looking at other bills for the same rate class whose period
    dates are "near" that bill.
    '''
    # minimum normlized score for a charge to get included in a bill
    # (between 0 and 1)
    THRESHOLD = 0.5

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
        always positive.
        '''
        return lambda x: max(a**(x * b), minimum)

    def __init__(self, utilbill_loader):
        """
        :param utilbill_loader: an object that has a 'load_utilbills' method
        returning an iterable of core.model.UtilBills matching criteria given as
        keyword arguments (see core.utilbill_loader.UtilBillLoader).
        """
        super(FuzzyPricingModel, self).__init__()
        self._utilbill_loader = utilbill_loader

    def _get_charge_scores(self, period, relevant_bills, charge_type):
        """Main part of the algorithm to guess what charges will be included
        in a bill.

        :param period: (start date, end date) of the bill
        :param relevant_bills: iterable of other bills to look at when
        deciding which charges should be included in this bill
        :param charge_type: one of the values in Charge.CHARGE_TYPES: only
        charges of this type in the 'relevant_bills' are considered

        :return 3 dictionaries:
        charge name -> score (float in [0, 1])
        charge name -> total weight of bills that contributed to its score
        (float >= 0)
        charge name -> highest-scoring occurrence of that charge and its
        distance (tuple of float, Charge object)
        """
        assert isinstance(period[0], date) and isinstance(period[1], date)
        assert charge_type in Charge.CHARGE_TYPES

        distance_func = self.__class__._manhattan_distance
        weight_func = self.__class__._exp_weight_with_min(0.5, 7, 0.000001)

        # the unique identifier of "the same charge" across more than one bill
        # is a combination of both 'type' (e.g. "distribution" or "supply") and
        # 'rsi_binding' (standardized name). in theory charges with the same
        # rsi_binding always have the same type; that could be guaranteed in
        # by a database constraint but it currently isn't.
        # only rsi_binding values are collected here because only charges
        # matching the 'charge_type' argument are relevant.
        bindings = set(c.rsi_binding for c in chain.from_iterable(
            utilbill.charges for utilbill in relevant_bills) if
                       c.type == charge_type)

        # these 3 dictionaries are the 3 return values
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

        # normalize the score of each charge by dividing by the total weight
        for binding in scores.iterkeys():
            if total_weight[binding] == 0:
                scores[binding] = 0
            else:
                scores[binding] /= total_weight[binding]
            assert 0 <= scores[binding] <= 1

        return scores, total_weight, closest_occurrence

    def _get_probable_shared_charges(self, period, relevant_bills, charge_type,
                                     threshold=THRESHOLD, verbose=False):
        """Get a list of charges that are expected to be included in a bill
        with the given period, based on existing bills.

        :param period: (start date, end date) of the bill
        :param relevant_bills: iterable of other bills to look at when
        deciding which charges should be included in this bill.
        :param threshold: the minimum score (between 0 and 1) for an RSI to be
        included.

        :return: a list of :py:class:`Charge` instances, each of which is
        unattached to any :py:class:`UtilBill`.
        """
        assert isinstance(period[0], date) and isinstance(period[1], date)
        assert charge_type in Charge.CHARGE_TYPES
        assert isinstance(threshold, (int, float))

        scores, total_weight, closest_occurrence = self._get_charge_scores(
            period, relevant_bills, charge_type)

        # include in the result all charges whose normalized weight
        # exceeds 'threshold', with the rate and quantity formulas it had in
        # its closest occurrence.
        result = []
        logger = getLogger()
        if verbose:
            logger.info('Predicted charges for %s - %s' % period)
            logger.info(
                '%35s %s %s' % ('binding:', 'weight:', 'normalized weight %:'))

        for binding, normalized_weight in scores.iteritems():
            logger.info('%35s %5d' % (binding, 100 * normalized_weight))

            # note that total_weight[binding] will never be 0 because it must
            # have occurred somewhere in order to occur in 'scores'
            if normalized_weight >= threshold:
                charge = closest_occurrence[binding][1]
                result.append(charge.clone())
        return result

    def _load_relevant_bills_distribution(self, utilbill, ignore_func):
        """Return an iterable of UtilBills relevant for determining the
        distribution charges of 'utilbill' (currently defined as having the
        same rate class).
        :param utilbill: UtilBill whose charges are being generated
        :param ignore_func: exclude bills for which this returns true
        """
        if None in (utilbill.utility, utilbill.rate_class):
            return []
        return [u for u in self._utilbill_loader.load_real_utilbills(
            utility=utilbill.utility, rate_class=utilbill.rate_class,
            processed=True) if not ignore_func(u)]

    def _load_relevant_bills_supply(self, utilbill, ignore_func):
        """Return an iterable of UtilBills relevant for determining the
        supply charges of 'utilbill' (currently defined as those having the
        same supply_group, or supplier if the supply_group is not known).
        :param utilbill: UtilBill whose charges are being generated
        :param ignore_func: exclude bills for which this returns true
        """
        if utilbill.supplier is None:
            return []
        if utilbill.supply_group is None:
            return [u for u in self._utilbill_loader.load_real_utilbills(
                supplier=utilbill.supplier, processed=True) if
                    not ignore_func(u)]
        # any two bills with the same supply group should also have the same
        # supplier, so "supplier" is not used as one of the filtering criteria
        return [u for u in self._utilbill_loader.load_real_utilbills(
            supply_group=utilbill.supply_group, processed=True) if
                not ignore_func(u)]

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

        # get distribution charges
        distribution_relevant_bills = self._load_relevant_bills_distribution(
            utilbill, ignore_func)
        distribution_charges = self._get_probable_shared_charges(
            (start, end), distribution_relevant_bills, Charge.DISTRIBUTION)
        del distribution_relevant_bills

        # get supply charges
        supply_relevant_bills = self._load_relevant_bills_supply(
            utilbill, ignore_func)
        supply_charges = self._get_probable_shared_charges(
            (start, end), supply_relevant_bills, Charge.SUPPLY)
        del supply_relevant_bills

        # combine distribution and supply charges to get the full set of
        # shared charges. there shouldn't be any overlap between the two groups.
        assert set(distribution_charges).isdisjoint(set(supply_charges))
        result = distribution_charges + supply_charges

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
                    result.append(charge.clone())

        return result

    def get_closest_occurrence_of_charge(self, charge):
        """
        :param charge: Charge (must be associated with a UtilBill)
        :return: a charge with the same rsi_binding as the given charge, whose
        bill's period is closest to the bill of the given one, or None if no
        occurrences were found.
        """
        utilbill = charge.utilbill
        assert charge.utilbill is not None
        if charge.type == Charge.SUPPLY:
            relevant_bills = self._load_relevant_bills_supply(
                utilbill, ignore_func=lambda ub: ub.id == utilbill.id)
        else:
            relevant_bills = self._load_relevant_bills_distribution(
                utilbill, ignore_func=lambda ub: ub.id == utilbill.id)

        # gathering all this unused data is wasteful
        _, _, closest_occurrence = self._get_charge_scores(
            (utilbill.period_start, utilbill.period_end), relevant_bills,
            charge.type)
        if charge.rsi_binding not in closest_occurrence:
            return None
        _, charge = closest_occurrence[charge.rsi_binding]
        return charge