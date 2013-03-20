# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import email
import tempfile
import re
from email.header import Header
import email.charset as charset
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
from email.iterators import typed_subpart_iterator
import logging
import mailcap

import alot.helper as helper
from alot.settings import settings
from alot.helper import string_sanitize
from alot.helper import string_decode
from alot.helper import parse_mailcap_nametemplate
from alot.helper import split_commandstring


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
    If types is `None`, `text/*` is used:
    The exact preferred type is specified by the prefer_plaintext config option
    which defaults to text/html.

    :param mail: the mail to use
    :type mail: :class:`email.Message`
    :param types: mime content types to use for body string
    :type types: list of str
    """

    preferred = 'text/plain' if settings.get('prefer_plaintext') else 'text/html'
    has_preferred = False

    # see if the mail has our preferred type
    if types == None:
        has_preferred = list(typed_subpart_iterator(mail, *preferred.split('/')))

    body_parts = []
    for part in mail.walk():
        ctype = part.get_content_type()

        if types is not None:
            if ctype not in types:
                continue
        cd = part.get('Content-Disposition', '')
        if cd.startswith('attachment'):
            continue
        # if the mail has our preferred type, we only keep this type
        # note that if types != None, has_preferred always stays False
        if has_preferred and ctype != preferred:
            continue

        enc = part.get_content_charset() or 'ascii'
        raw_payload = part.get_payload(decode=True)
        if ctype == 'text/plain':
            raw_payload = string_decode(raw_payload, enc)
            body_parts.append(string_sanitize(raw_payload))
        else:
            #get mime handler
            key = 'copiousoutput'
            handler, entry = settings.mailcap_find_match(ctype, key=key)
            tempfile_name = None
            stdin = None

            if entry:
                handler_raw_commandstring = entry['view']
                # in case the mailcap defined command contains no '%s',
                # we pipe the files content to the handling command via stdin
                if '%s' in handler_raw_commandstring:
                    # open tempfile, respect mailcaps nametemplate
                    nametemplate = entry.get('nametemplate', '%s')
                    prefix, suffix = parse_mailcap_nametemplate(nametemplate)
                    tmpfile = tempfile.NamedTemporaryFile(delete=False,
                                                        prefix=prefix,
                                                        suffix=suffix)
                    # write payload to tmpfile
                    tmpfile.write(raw_payload)
                    tmpfile.close()
                    tempfile_name = tmpfile.name
                else:
                    stdin = raw_payload

                # read parameter, create handler command
                parms = tuple(map('='.join, part.get_params()))

                # create and call external command
                cmd = mailcap.subst(entry['view'], ctype,
                                    filename=tempfile_name, plist=parms)
                logging.debug('command: %s' % cmd)
                logging.debug('parms: %s' % str(parms))
                cmdlist = split_commandstring(cmd)
                # call handler
                rendered_payload, errmsg, retval = helper.call_cmd(cmdlist, stdin=stdin)

                # remove tempfile
                if tempfile_name:
                    os.unlink(tempfile_name)

                if rendered_payload:  # handler had output
                    body_parts.append(string_sanitize(rendered_payload))
    return u'\n\n'.join(body_parts)


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

    # some mailers send out incorrectly escaped headers
    # and double quote the escaped realname part again. remove those
    value = re.sub(r'\"(.*?=\?.*?.*?)\"', r'\1', value)

    # otherwise we interpret RFC2822 encoding escape sequences
    valuelist = email.header.decode_header(value)
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
