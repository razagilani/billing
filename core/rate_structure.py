from __future__ import division
from collections import defaultdict
from sys import maxint

from billing.exc import NoSuchBillException
from billing.core.model import Charge


# minimum normlized score for an RSI to get included in a probable RS
# (between 0 and 1)
RSI_PRESENCE_THRESHOLD = 0.5

def _manhattan_distance(p1, p2):
    # note that 15-day offset is a 30-day distance, 30-day offset is a
    # 60-day difference
    delta_begin = abs(p1[0] - p2[0]).days
    delta_end = abs(p1[1] - p2[1]).days
    return delta_begin + delta_end

def _exp_weight_with_min(a, b, minimum):
    '''Exponentially-decreasing weight function with a minimum value so it's
    always nonnegative.'''
    return lambda x: max(a**(x * b), minimum)

class RateStructureDAO(object):
    '''Loads and saves RateStructure objects. Also responsible for generating
    predicted UPRSs based on existing ones.
    '''
    def __init__(self, logger=None):
        ''''
        'logger': optional Logger object to record messages about rate
        structure prediction.
        '''
        # TODO instead of using None as logger, use a logger that does nothing,
        # to avoid checking if it's None
        self.logger = logger

    def _get_probable_shared_charges(self, utilbill_loader, utility, service,
            rate_class, period, distance_func=_manhattan_distance,
            weight_func=_exp_weight_with_min(0.5, 7, 0.000001),
            threshold=RSI_PRESENCE_THRESHOLD, ignore=lambda x: False,
            verbose=False):
        """Constructs and returns a list of :py:class:`processing.state.Charge`
        instances, each of which is unattached to any
        :py:class:`proessing.state.UtilBill`.

        The charges returned represent a guess as to which formulas should
        be present on the utilbill.

        :param threshold: the minimum score (between 0 and 1) for an RSI to be
        included.
        :param ignore: an optional function to exclude UPRSs from the input data
        """
        all_utilbills = [utilbill for utilbill in
                         utilbill_loader.load_real_utilbills(
                            service=service,
                            utility=utility,
                            rate_class=rate_class,
                            processed=True
                         ) if not ignore(utilbill)]

        bindings = set()
        for utilbill in all_utilbills:
            for charge in utilbill.charges:
                bindings.add(charge.rsi_binding)

        scores = defaultdict(lambda: 0)
        total_weight = defaultdict(lambda: 0)
        closest_occurrence = defaultdict(lambda: (maxint, None))

        for binding in bindings:
            for utilbill in all_utilbills:
                distance = distance_func((utilbill.period_start,
                                          utilbill.period_end), period)
                weight = weight_func(distance)
                try:
                    charge = next(c for c in utilbill.charges
                                  if c.rsi_binding == binding)
                except StopIteration:
                    pass
                else:
                    if charge.shared:
                        # binding present in charge and shared: add 1 * weight
                        # to score
                        scores[binding] += weight
                        # if this distance is closer than the closest occurence
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
            self.logger.info('Predicted RSIs for %s %s %s - %s' % (utility,
                    rate_class, period[0], period[1]))
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

    def get_predicted_charges(self, utilbill, utilbill_loader):
        """Constructs and returns a list of :py:class:`processing.state.Charge`
        instances, each of which is unattached to any
        :py:class:`proessing.state.UtilBill`.

        The charges returned represent a guess as to which formulas should
        be present on the utilbill.

        :utilbill: a :class:`processing.state.UtilBill` instance
        'utilbill_loader': an object that has a 'load_utilbills' method
        returning an iterable of state.UtilBills matching criteria given as
        keyword arguments (see state.UtilBillLoader). For testing, this can be
        replaced with a mock object.
        """
        result = self._get_probable_shared_charges(utilbill_loader,
                utilbill.utility, utilbill.service, utilbill.rate_class,
                (utilbill.period_start, utilbill.period_end),
                ignore=lambda ub:ub.id == utilbill.id)

        # add any charges from the predecessor that are not already there
        try:
            predecessor = utilbill_loader.get_last_real_utilbill(
                    utilbill.customer.account, utilbill.period_start,
                    service=utilbill.service, utility=utilbill.utility,
                    rate_class=utilbill.rate_class, processed=True)
        except NoSuchBillException:
            # if there's no predecessor, there are no charges to add
            pass
        else:
            for charge in predecessor.charges:
                if not (charge.shared or charge.rsi_binding in (c.rsi_binding for c in
                            result)):
                    result.append(Charge.formulas_from_other(charge))

        return result

