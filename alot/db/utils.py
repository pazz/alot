import os
import email
import tempfile
import re
import shlex
from email.header import Header
import email.charset as charset
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
from email.iterators import typed_subpart_iterator

import alot.helper as helper
from alot.settings import settings
from alot.helper import string_sanitize
from alot.helper import string_decode



def extract_headers(mail, headers=None):
    """
    returns subset of this messages headers as human-readable format:
    all header values are decoded, the resulting string has
    one line "KEY: VALUE" for each requested header present in the mail.

    :param mail: the mail to use
    :type mail: :class:`email.Message`
    :param headers: headers to extract
    :type headers: list of str
    """
    headertext = u''
    if headers == None:
        headers = mail.keys()
    for key in headers:
        value = u''
        if key in mail:
            value = decode_header(mail.get(key, ''))
        headertext += '%s: %s\n' % (key, value)
    return headertext


def extract_body(mail, types=None):
    """
    returns a body text string for given mail.
    If types is `None`, 'text/*' is used:
    In case mail has a 'text/html' part, it is prefered over
    'text/plain' parts.

    :param mail: the mail to use
    :type mail: :class:`email.Message`
    :param types: mime content types to use for body string
    :type types: list of str
    """
    html = list(typed_subpart_iterator(mail, 'text', 'html'))

    # if no specific types are given, we favor text/html over text/plain
    drop_plaintext = False
    if html and not types:
        drop_plaintext = True

    body_parts = []
    for part in mail.walk():
        ctype = part.get_content_type()

        if types is not None:
            if ctype not in types:
                continue
        cd = part.get('Content-Disposition', '')
        if cd.startswith('attachment'):
            continue

        enc = part.get_content_charset() or 'ascii'
        raw_payload = part.get_payload(decode=True)
        if part.get_content_maintype() == 'text':
            raw_payload = string_decode(raw_payload, enc)
        if ctype == 'text/plain' and not drop_plaintext:
            body_parts.append(string_sanitize(raw_payload))
        else:
            #get mime handler
            handler = settings.get_mime_handler(ctype, key='view',
                                                interactive=False)
            if handler:
                #open tempfile. Not all handlers accept stuff from stdin
                tmpfile = tempfile.NamedTemporaryFile(delete=False,
                                                      suffix='.html')
                #write payload to tmpfile
                if part.get_content_maintype() == 'text':
                    tmpfile.write(raw_payload.encode('utf8'))
                else:
                    tmpfile.write(raw_payload)
                tmpfile.close()
                #create and call external command
                cmd = handler % tmpfile.name
                cmdlist = shlex.split(cmd.encode('utf-8', errors='ignore'))
                rendered_payload, errmsg, retval = helper.call_cmd(cmdlist)
                #remove tempfile
                os.unlink(tmpfile.name)
                if rendered_payload:  # handler had output
                    body_parts.append(string_sanitize(rendered_payload))
                elif part.get_content_maintype() == 'text':
                    body_parts.append(string_sanitize(raw_payload))
                # else drop
    return '\n\n'.join(body_parts)


def decode_header(header, normalize=False):
    """
    decode a header value to a unicode string

    values are usually a mixture of different substrings
    encoded in quoted printable using diffetrent encodings.
    This turns it into a single unicode string

    :param header: the header value
    :type header: str
    :param normalize: replace trailing spaces after newlines
    :type normalize: bool
    :rtype: unicode
    """

    # If the value isn't ascii as RFC2822 prescribes,
    # we just return the unicode bytestring as is
    value = string_decode(header)  # convert to unicode
    try:
        value = value.encode('ascii')
    except UnicodeEncodeError:
        return value

    # otherwise we interpret RFC2822 encoding escape sequences
    valuelist = email.header.decode_header(header)
    decoded_list = []
    for v, enc in valuelist:
        v = string_decode(v, enc)
        decoded_list.append(string_sanitize(v))
    value = u' '.join(decoded_list)
    if normalize:
        value = re.sub(r'\n\s+', r' ', value)
    return value


def encode_header(key, value):
    """
    encodes a unicode string as a valid header value

    :param key: the header field this value will be stored in
    :type key: str
    :param value: the value to be encoded
    :type value: unicode
    """
    # handle list of "realname <email>" entries separately
    if key.lower() in ['from', 'to', 'cc', 'bcc']:
        rawentries = value.split(',')
        encodedentries = []
        for entry in rawentries:
            m = re.search('\s*(.*)\s+<(.*\@.*\.\w*)>\s*$', entry)
            if m:  # If a realname part is contained
                name, address = m.groups()
                # try to encode as ascii, if that fails, revert to utf-8
                # name must be a unicode string here
                namepart = Header(name)
                # append address part encoded as ascii
                entry = '%s <%s>' % (namepart.encode(), address)
            encodedentries.append(entry)
        value = Header(', '.join(encodedentries))
    else:
        value = Header(value)
    return value
