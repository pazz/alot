import mailbox
import re
from urlparse import urlparse
from validate import VdtTypeError
from validate import is_list
from validate import ValidateError

from alot import crypto
from alot.errors import GPGProblem


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
        return crypto.CryptoContext().get_key(value)
    except GPGProblem, e:
        raise ValidateError(e.message)
