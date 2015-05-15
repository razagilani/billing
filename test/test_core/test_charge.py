from datetime import date
from mock import Mock

from core.model import Charge, UtilBill, Address, \
    ChargeEvaluation, UtilityAccount, Utility
from exc import FormulaError
from test import testing_utils


builtins = ['__import__', 'abs', 'all', 'any', 'apply', 'bin', 'callable',
            'chr', 'cmp', 'coerce', 'compile', 'delattr', 'dir', 'divmod',
            'eval', 'execfile', 'filter', 'format', 'getattr', 'globals',
            'hasattr', 'hash', 'hex', 'id', 'input', 'intern', 'isinstance',
            'issubclass', 'iter', 'len', 'locals', 'map', 'max', 'min', 'next',
            'oct', 'open', 'ord', 'pow', 'range', 'raw_input', 'reduce',
            'reload', 'repr', 'round', 'setattr', 'sorted', 'sum', 'unichr',
            'vars', 'zip']

class ChargeUnitTests(testing_utils.TestCase):
    """Unit Tests for the :class:`billing.processing.state.Charge` class"""

    def setUp(self):
        # TOOD: how can this work with strings as utility, rate class, supplier?
        self.bill = UtilBill(UtilityAccount('someone', '98989',
                                 Utility(name='FB Test Utility'),
                                 'FB Test Supplier', 'FB Test Rate Class', None,
                                 Address(), Address()),
                                 Utility(name='utility'), None,
                                 supplier='supplier',
                                 period_start=date(2000, 1, 1),
                                 period_end=date(2000, 2, 1))
        self.charge_params = dict(rsi_binding='SOME_RSI',
                                  rate=6,
                                  description='SOME_DESCRIPTION',
                                  unit='therms',
                                  formula="SOME_VAR.quantity * 2",
                                  has_charge=True,
                                  shared=False,
                                  roundrule="rounding",
                                  type='distribution')
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
        formulas = [('REG_TOTAL.quantity', set(['REG_TOTAL'])),
                    ('SOMEVAR.rr + zz',  set(['SOMEVAR', 'zz']))]
        for quantity_formula, formula_variables in formulas:
            self.charge.quantity_formula = quantity_formula
            self.assertEqual(formula_variables,
                             Charge.formula_variables(self.charge))
        self.charge.quantity_formula = '$958^04'
        self.assertRaises(SyntaxError, Charge.formula_variables, self.charge)

    def test_evaluate(self):
        evaluation = Charge.evaluate(self.charge, self.context)
        self.assertEqual(evaluation.quantity, 4)
        self.assertEqual(evaluation.total, 24)

    def test_evaluate_check_update_is_true(self):
        self.assertNotEqual(self.charge.quantity, 4)
        Charge.evaluate(self.charge, self.context, update=True)
        self.assertEqual(self.charge.quantity, 4)
        self.assertEqual(self.charge.total, 24)

    def test_evaluate_does_not_raise_on_bad_input_raise_exception_false(self):
        self.charge.quantity_formula = '^)%I$#*4'
        Charge.evaluate(self.charge, self.context)

    def test_evaluate_blank(self):
        '''Test that empty quantity_formula is equivalent to 0.
        '''
        c = Charge('X', '', 3, '', '', 'kWh')
        self.assertEqual(0, c.evaluate({}).quantity)
        self.assertEqual(0, c.evaluate({}).total)

    def test_rounding(self):
        c = Charge('A', formula='.005', rate=1)
        self.assertEqual(.005, c.evaluate({}).quantity)
        self.assertEqual(.01, c.evaluate({}).total)

        c = Charge('A', formula='-.005', rate=1)
        self.assertEqual(-.005, c.evaluate({}).quantity)
        self.assertEqual(-.01, c.evaluate({}).total)



