# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import mailbox
import re
from urwid import AttrSpec, AttrSpecError
from urlparse import urlparse
from validate import VdtTypeError
from validate import is_list
from validate import ValidateError, VdtValueTooLongError, VdtValueError

from .. import crypto
from ..errors import GPGProblem


def attr_triple(value):
    """
    Check that interprets the value as `urwid.AttrSpec` triple for the colour
    modes 1,16 and 256.  It assumes a <6 tuple of attribute strings for
    mono foreground, mono background, 16c fg, 16c bg, 256 fg and 256 bg
    respectively. If any of these are missing, we downgrade to the next
    lower available pair, defaulting to 'default'.

    :raises: VdtValueTooLongError, VdtTypeError
    :rtype: triple of `urwid.AttrSpec`
    """
    keys = ['dfg', 'dbg', '1fg', '1bg', '16fg', '16bg', '256fg', '256bg']
    acc = {}
    if not isinstance(value, (list, tuple)):
        value = value,
    if len(value) > 6:
        raise VdtValueTooLongError(value)
    # ensure we have exactly 6 attribute strings
    attrstrings = (value + (6 - len(value)) * [None])[:6]
    # add fallbacks for the empty list
    attrstrings = (2 * ['default']) + attrstrings
    for i, value in enumerate(attrstrings):
        if value:
            acc[keys[i]] = value
        else:
            acc[keys[i]] = acc[keys[i - 2]]
    try:
        mono = AttrSpec(acc['1fg'], acc['1bg'], 1)
        normal = AttrSpec(acc['16fg'], acc['16bg'], 16)
        high = AttrSpec(acc['256fg'], acc['256bg'], 256)
    except AttrSpecError as e:
        raise ValidateError(e.message)
    return mono, normal, high


def align_mode(value):
    """
    test if value is one of 'left', 'right' or 'center'
    """
    if value not in ['left', 'right', 'center']:
        raise VdtValueError
    return value


def width_tuple(value):
    """
    test if value is a valid width indicator (for a sub-widget in a column).
    This can either be
    ('fit', min, max): use the length actually needed for the content, padded
                       to use at least width min, and cut of at width max.
                       Here, min and max are positive integers or 0 to disable
                       the boundary.
    ('weight',n): have it relative weight of n compared to other columns.
                  Here, n is an int.
    """
    if value is None:
        res = 'fit', 0, 0
    elif not isinstance(value, (list, tuple)):
        raise VdtTypeError(value)
    elif value[0] not in ['fit', 'weight']:
        raise VdtTypeError(value)
    if value[0] == 'fit':
        if not isinstance(value[1], int) or not isinstance(value[2], int):
            VdtTypeError(value)
        res = 'fit', int(value[1]), int(value[2])
    else:
        if not isinstance(value[1], int):
            VdtTypeError(value)
        res = 'weight', int(value[1])
    return res


def mail_container(value):
    """
    Check that the value points to a valid mail container,
    in URI-style, e.g.: `mbox:///home/username/mail/mail.box`.
    The value is cast to a :class:`mailbox.Mailbox` object.
    """
    if not re.match(r'.*://.*', value):
        raise VdtTypeError(value)
    mburl = urlparse(value)
    if mburl.scheme == 'mbox':
        box = mailbox.mbox(mburl.path)
    elif mburl.scheme == 'maildir':
        box = mailbox.Maildir(mburl.path)
    elif mburl.scheme == 'mh':
        box = mailbox.MH(mburl.path)
    elif mburl.scheme == 'babyl':
        box = mailbox.Babyl(mburl.path)
    elif mburl.scheme == 'mmdf':
        box = mailbox.MMDF(mburl.path)
    else:
        raise VdtTypeError(value)
    return box


def force_list(value, min=None, max=None):
    """
    Check that a value is a list, coercing strings into
    a list with one member.

    You can optionally specify the minimum and maximum number of members.
    A minumum of greater than one will fail if the user only supplies a
    string.

    The difference to :func:`validate.force_list` is that this test
    will return an empty list instead of `['']` if the config value
    matches `r'\s*,?\s*'`.

    >>> vtor.check('force_list', 'hello')
    ['hello']
    >>> vtor.check('force_list', '')
    []
    """
    if not isinstance(value, (list, tuple)):
        value = [value]
    rlist = is_list(value, min, max)
    if rlist == ['']:
        rlist = []
    return rlist


def gpg_key(value):
    """
    test if value points to a known gpg key
    and return that key as :class:`pyme.pygpgme._gpgme_key`.
    """
    try:
        return crypto.get_key(value)
    except GPGProblem as e:
        raise ValidateError(e.message)
