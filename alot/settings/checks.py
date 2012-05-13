import mailbox
import re
from urlparse import urlparse
from validate import VdtTypeError
from validate import ValidateError

from alot import crypto
from alot.errors import GPGProblem


def mail_container(value):
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


def gpg_key(value):
    """
    test if value points to a known gpg key
    and return that key as :class:`pyme.pygpgme._gpgme_key`.
    """
    try:
        key = crypto.CryptoContext().get_key(value)
        if key == None:
            raise ValidateError('No key found for hint %s' % value)
        return key
    except GPGProblem, e:
        raise ValidateError(e.message)
