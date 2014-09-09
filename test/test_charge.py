from datetime import date

from billing.test import utils
from billing.processing.state import Charge, UtilBill, Customer, Address, \
    ChargeEvaluation
from billing.exc import FormulaSyntaxError, FormulaError


builtins = ['__import__', 'abs', 'all', 'any', 'apply', 'bin', 'callable',
            'chr', 'cmp', 'coerce', 'compile', 'delattr', 'dir', 'divmod',
            'eval', 'execfile', 'filter', 'format', 'getattr', 'globals',
            'hasattr', 'hash', 'hex', 'id', 'input', 'intern', 'isinstance',
            'issubclass', 'iter', 'len', 'locals', 'map', 'max', 'min', 'next',
            'oct', 'open', 'ord', 'pow', 'range', 'raw_input', 'reduce',
            'reload', 'repr', 'round', 'setattr', 'sorted', 'sum', 'unichr',
            'vars', 'zip']

class ChargeUnitTests(utils.TestCase):
    """Unit Tests for the :class:`billing.processing.state.Charge` class"""

    def setUp(self):
        bill = UtilBill(Customer('someone', '98989', 0.3, 0.1,
                                 'nobody@example.com', 'FB Test Utility',
                                 'FB Test Rate Class', Address(), Address()),
                        UtilBill.Complete, 'gas', 'utility', 'rate class',
                        Address(), Address(), period_start=date(2000, 1, 1),
                        period_end=date(2000, 2, 1))
        self.charge_params = dict(utilbill=bill,
                                  description='SOME_DESCRIPTION',
                                  group='SOME_GROUP',
                                  quantity=0.0,
                                  quantity_units='therms',
                                  rate=0.0,
                                  rsi_binding='SOME_RSI',
                                  total=0.0,
                                  quantity_formula="SOME_VAR.quantity * 2",
                                  rate_formula="OTHER_VAR.rate + 1",
                                  has_charge=True,
                                  shared=False,
                                  roundrule="rounding")
        self.charge = Charge(**self.charge_params)
        self.context = {'SOME_VAR': ChargeEvaluation(quantity=2, rate=3),
                        'OTHER_VAR': ChargeEvaluation(quantity=4, rate=5),
                        'ERROR': ChargeEvaluation(exception="uh oh")}

    def test_is_builtin(self):
        for builtin_function_name in builtins:
            self.assertTrue(self.charge.is_builtin(builtin_function_name))
        for function_name in ["No", "built-ins", "here"]:
            self.assertFalse(self.charge.is_builtin(function_name))

    def test_get_variable_names(self):
        for formula, expected in [('sum(x) if y else 5', ['y', 'x']),
                                  ('5*usage + 15 - spent', ['spent', 'usage']),
                                  ('range(20) + somevar', ['somevar'])]:
            self.assertEqual(expected, Charge.get_variable_names(formula))

    def test_formulas_from_other(self):
        charge_2 = Charge.formulas_from_other(self.charge)
        for key, val in self.charge_params.iteritems():
            self.assertEqual(getattr(charge_2, key),
                             None if key == 'utilbill' else val)

    def test_evaluate_formula(self):
        test_cases = [('5 + ', None, 'Syntax error'),
                      ('OTHER_VAR.quantity', 4, None),
                      ('SOME_VAR.rate * OTHER_VAR.quantity', 12, None),
                      ('asdf', None, "Error: name 'asdf' "
                                     "is not defined"),
                      ('ERROR.value', None, "Error: 'ChargeEvaluation' object has no "
                                            "attribute 'value'")]
        for formula, expected_result, expected_error_message in test_cases:
            try:
                result = self.charge._evaluate_formula(formula, self.context)
                self.assertEqual(result, expected_result)
            except FormulaError as error:
                self.assertEqual(error.message, expected_error_message)

    def test_formula_variable(self):
        formulas = [('REG_TOTAL.quantity', 'SOME_VAL.rate',
                     set(['REG_TOTAL', 'SOME_VAL'])),
                    ('SOMEVAR.rr', 'OTHERVAR + zz',
                     set(['SOMEVAR', 'OTHERVAR', 'zz']))]
        for quantity_formula, rate_formula, formula_variables in formulas:
            self.charge.quantity_formula = quantity_formula
            self.charge.rate_formula = rate_formula
            self.assertEqual(formula_variables,
                             Charge.formula_variables(self.charge))
        self.charge.quantity_formula = '$958^04'
        self.assertRaises(SyntaxError, Charge.formula_variables, self.charge)

    def test_evaluate(self):

        evaluation = Charge.evaluate(self.charge, self.context)
        self.assertEqual(evaluation.quantity, 4)
        self.assertEqual(evaluation.rate, 6)
        self.assertEqual(evaluation.total, 24)

    def test_evaluate_check_update_is_true(self):
        self.assertNotEqual(self.charge.quantity, 4)
        self.assertNotEqual(self.charge.rate, 6)
        Charge.evaluate(self.charge, self.context, update=True)
        self.assertEqual(self.charge.quantity, 4)
        self.assertEqual(self.charge.rate, 6)
        self.assertEqual(self.charge.total, 24)

    def test_evaluate_does_not_raise_on_bad_input_raise_exception_false(self):
        self.charge.quantity_formula = '^)%I$#*4'
        Charge.evaluate(self.charge, self.context)

