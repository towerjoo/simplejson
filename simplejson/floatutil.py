"""Float utils used by simplejson
"""
import sys
import struct

def _floatconstants():
    _BYTES = '7FF80000000000007FF0000000000000'.decode('hex')
    # The struct module in Python 2.4 would get frexp() out of range here
    # when an endian is specified in the format string. Fixed in Python 2.5+
    if sys.byteorder != 'big':
        _BYTES = _BYTES[:8][::-1] + _BYTES[8:][::-1]
    nan, inf = struct.unpack('dd', _BYTES)
    return nan, inf, -inf

NaN, PosInf, NegInf = _floatconstants()

FLOAT_REPR = repr

def floatstr(o, allow_nan=True,
        _repr=FLOAT_REPR, _inf=PosInf, _neginf=-PosInf):
    # Check for specials. Note that this type of test is processor
    # and/or platform-specific, so do tests which don't depend on
    # the internals.

    if o != o:
        text = 'NaN'
    elif o == _inf:
        text = 'Infinity'
    elif o == _neginf:
        text = '-Infinity'
    else:
        return _repr(o)

    if not allow_nan:
        raise ValueError(
            "Out of range float values are not JSON compliant: " +
            repr(o))

    return text
