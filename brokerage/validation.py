from tablib import Databook, formats
# TODO: ValidationError should probably be specific to this module,
# not a global thing. this kind of validation doesn't have anything in common
#  with other validation.
import re
from core.exceptions import ValidationError

def _assert_true(p):
    if not p:
        raise ValidationError('Assertion failed')


def _assert_equal(a, b):
    if a != b:
        raise ValidationError("Expected %s, found %s" % (a, b))


def _assert_match(regex, string):
    if not re.match(regex, string):
        raise ValidationError('No match for "%s" in "%s"' % (regex, string))
