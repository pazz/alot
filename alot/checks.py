import mailbox
import re
from urlparse import urlparse

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
