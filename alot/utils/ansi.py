# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import re


_b1 = r'\033\['  # Control Sequence Introducer
_b2 = r'[0-9:;<=>?]*'  # parameter bytes
_b3 = r'[ !\"#$%&\'()*+,-./]*'  # intermediate bytes
_b4 = r'[A-Z[\]^_`a-z{|}~]'  # final byte"
esc_pattern = re.compile(
    _b1 + r'(?P<pb>' + _b2 + ')' + r'(?P<ib>' + _b3 + ')' + r'(?P<fb>' + _b4 + ')')


def parse_csi(text):
    """Parse text and yield tuples for ANSI CSIs found in it.

    Each tuple is in the format ``(pb, ib, fb, s)`` with the parameter bytes
    (pb), the intermediate bytes (ib), the final byte (fb) and the substring (s)
    between this and the next CSI (or the end of the string).

    Note that the first tuple will always be ``(None, None, None, s)`` with
    ``s`` being the substring prior to the first CSI (or the end of the string
    if none was found).
    """
    i = 0
    pb, ib, fb = None, None, None
    for m in esc_pattern.finditer(text):
        yield pb, ib, fb, text[i:m.start()]
        pb, ib, fb = m.groups()
        i = m.end()
    yield pb, ib, fb, text[i:]


def remove_csi(text):
    """Return text with ANSI CSIs removed."""
    return "".join(s for *_, s in parse_csi(text))
