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
from twisted.internet import defer
from twisted.internet.threads import deferToThread

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
    if headers is None:
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
    In case mail has a `text/html` part, it is prefered over
    `text/plain` parts.

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
        if ctype == 'text/plain' and not drop_plaintext:
            raw_payload = string_decode(raw_payload, enc)
            body_parts.append(string_sanitize(raw_payload))
        else:
            #get mime handler
            key = 'copiousoutput'
            handler, entry = settings.mailcap_find_match(ctype, key=key)

            if entry:
                # open tempfile, respect mailcaps nametemplate
                nametemplate = entry.get('nametemplate', '%s')
                prefix, suffix = parse_mailcap_nametemplate(nametemplate)
                tmpfile = tempfile.NamedTemporaryFile(delete=False,
                                                      prefix=prefix,
                                                      suffix=suffix)
                # write payload to tmpfile
                tmpfile.write(raw_payload)
                tmpfile.close()

                # read parameter, create handler command
                parms = tuple(map('='.join, part.get_params()))

                # create and call external command
                cmd = mailcap.subst(entry['view'], ctype,
                                    filename=tmpfile.name, plist=parms)
                logging.debug('command: %s' % cmd)
                logging.debug('parms: %s' % str(parms))
                cmdlist = split_commandstring(cmd)
                # call handler
                rendered_payload, errmsg, retval = helper.call_cmd(cmdlist)
                # remove tempfile
                os.unlink(tmpfile.name)
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


def interpret(part):
    ctype = part.get_content_type()
    enc = part.get_content_charset() or 'ascii'
    raw_payload = part.get_payload(decode=True)
    #get mime handler
    key = 'copiousoutput'
    handler, entry = settings.mailcap_find_match(ctype, key=key)

    if entry:
        # open tempfile, respect mailcaps nametemplate
        nametemplate = entry.get('nametemplate', '%s')
        prefix, suffix = parse_mailcap_nametemplate(nametemplate)
        tmpfile = tempfile.NamedTemporaryFile(delete=False, prefix=prefix,
                                              suffix=suffix)
        # write payload to tmpfile
        tmpfile.write(raw_payload)
        tmpfile.close()

        # read parameter, create handler command
        parms = tuple(map('='.join, part.get_params()))

        # create and call external command
        cmd = mailcap.subst(entry['view'], ctype,
                            filename=tmpfile.name, plist=parms)
        logging.debug('command: %s' % cmd)
        logging.debug('parms: %s' % str(parms))
        cmdlist = split_commandstring(cmd)
        # call handler
        rendered_payload, errmsg, retval = helper.call_cmd(cmdlist)
        # remove tempfile
        os.unlink(tmpfile.name)
        if rendered_payload:  # handler had output
            return string_decode(rendered_payload, enc)


def mimeparse(part):
    ctype = part.get_content_type()
    maintype = part.get_content_maintype()
    subtype = part.get_content_subtype()
    cdisp = part.get('Content-Disposition', '')
    logging.debug('read part: %s' % ctype)
    tree = {
        'ctype': ctype,
        'children': [],
        'email': part,
        'attachment': cdisp.startswith('attachment')
    }
    d = defer.Deferred()
    dlist = []

    def addchild(child):
        tree['children'].append(child)

    if ctype == 'multipart/encrypted':
        # A multipart/encrypted message has two parts. The first part has
        # control information that is needed to decrypt the
        # application/octet-stream second part. Similar to signed messages,
        # there are different implementations which are identified by their
        # separate content types for the control part. The most common types
        # are "application/pgp-encrypted" (RFC 3156) and
        # "application/pkcs7-mime" (S/MIME). Defined in RFC 1847, Section
        # 2.2
        # TODO: decrypt here, parse plaintext to email.Message, recur on that.
        pass
    elif ctype == 'multipart/signed':
        # A multipart/signed message is used to attach a digital signature
        # to a message. It has two parts, a body part and a signature part.
        # The whole of the body part, including mime headers, is used to
        # create the signature part. Many signature types are possible, like
        # application/pgp-signature (RFC 3156) and
        # application/pkcs7-signature (S/MIME). Defined in RFC 1847,
        # Section 2.1
        # TODO: define function that verifies sig and stores result, call it in thread and recur
        for subpart in part.get_payload():
            mimeparse(subpart).addCallback(addchild)
    elif ctype == 'message/rfc822':
        logging.debug('rfc822')
        # A message/rfc822 part contains an email message, including any
        # headers. This is used for digests as well as for email
        # forwarding. Defined in RFC 2046.
        pass

    elif maintype == 'multipart':
        for subpart in part.get_payload():
            ld = mimeparse(subpart)
            ld.addCallback(addchild)
            dlist.append(ld)
    else:
        enc = part.get_content_charset() or 'ascii'
        raw_payload = part.get_payload(decode=True)
        raw_payload = string_decode(raw_payload, enc)

        if ctype == 'text/plain':
            tree['content'] = raw_payload
        else:
            dl = deferToThread(interpret, part)

            def add_content(data):
                tree['content'] = data

            dl.addCallback(add_content)
            dlist.append(dl)

    def ret(foo):
        d.callback(tree)
    dl = defer.DeferredList(dlist)
    dl.addCallback(ret)
    return d
