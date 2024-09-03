# encoding=utf-8
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2017 Dylan Baker <dylan@pnwbakers.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import email
import email.charset as charset
import email.policy
import email.utils
from email.errors import MessageError
import tempfile
import re
import logging
import mailcap
import io
import base64
import quopri

from .. import crypto
from .. import helper
from ..errors import GPGProblem
from ..settings.const import settings
from ..helper import string_sanitize
from ..helper import string_decode
from ..helper import parse_mailcap_nametemplate
from ..helper import split_commandstring

charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')

X_SIGNATURE_VALID_HEADER = 'X-Alot-OpenPGP-Signature-Valid'
X_SIGNATURE_MESSAGE_HEADER = 'X-Alot-OpenPGP-Signature-Message'

_APP_PGP_SIG = 'application/pgp-signature'
_APP_PGP_ENC = 'application/pgp-encrypted'


def add_signature_headers(mail, sigs, error_msg):
    '''Add pseudo headers to the mail indicating whether the signature
    verification was successful.

    :param mail: :class:`email.message.Message` the message to entitle
    :param sigs: list of :class:`gpg.results.Signature`
    :param error_msg: An error message if there is one, or None
    :type error_msg: :class:`str` or `None`
    '''
    sig_from = ''
    sig_known = True
    uid_trusted = False

    assert error_msg is None or isinstance(error_msg, str)

    if not sigs:
        error_msg = error_msg or 'no signature found'
    elif not error_msg:
        try:
            key = crypto.get_key(sigs[0].fpr)
            for uid in key.uids:
                if crypto.check_uid_validity(key, uid.email):
                    sig_from = uid.uid
                    uid_trusted = True
                    break
            else:
                # No trusted uid found, since we did not break from the loop.
                sig_from = key.uids[0].uid
        except GPGProblem:
            sig_from = sigs[0].fpr
            sig_known = False

    if error_msg:
        msg = 'Invalid: {}'.format(error_msg)
    elif uid_trusted:
        msg = 'Valid: {}'.format(sig_from)
    else:
        msg = 'Untrusted: {}'.format(sig_from)

    mail.add_header(X_SIGNATURE_VALID_HEADER,
                    'False' if (error_msg or not sig_known) else 'True')
    mail.add_header(X_SIGNATURE_MESSAGE_HEADER, msg)


def get_params(mail, failobj=None, header='content-type', unquote=True):
    '''Get Content-Type parameters as dict.

    RFC 2045 specifies that parameter names are case-insensitive, so
    we normalize them here.

    :param mail: :class:`email.message.Message`
    :param failobj: object to return if no such header is found
    :param header: the header to search for parameters, default
    :param unquote: unquote the values
    :returns: a `dict` containing the parameters
    '''
    failobj = failobj or []
    return {k.lower(): v for k, v in mail.get_params(failobj, header, unquote)}


def _handle_signatures(original_bytes, original, message, params):
    """Shared code for handling message signatures.

    RFC 3156 is quite strict:
    * exactly two messages
    * the second is of type 'application/pgp-signature'
    * the second contains the detached signature

    :param original_bytes: the original top-level mail raw bytes,
        containing the segments against which signatures will be verified.
        Necessary because parsing and re-serialising a Message isn't
        byte-perfect, which interferes with signature validation.
    :type original_bytes: bytes
    :param original: The original top-level mail. This is required to attache
        special headers to
    :type original: :class:`email.message.Message`
    :param message: The multipart/signed payload to verify
    :type message: :class:`email.message.Message`
    :param params: the message parameters as returned by :func:`get_params`
    :type params: dict[str, str]
    """
    try:
        nb_parts = len(message.get_payload()) if message.is_multipart() else 1
        if nb_parts != 2:
            raise MessageError(
                f'expected exactly two messages, got {nb_parts}')

        signature_part = message.get_payload(1)
        ct = signature_part.get_content_type()
        if ct != _APP_PGP_SIG:
            raise MessageError(
               f'expected Content-Type: {_APP_PGP_SIG}, got: {ct}')

        # TODO[dcbaker]: RFC 3156 says the alg has to be lower case, but I've
        #  seen a message with 'PGP-'. maybe we should be more permissive here,
        #  or maybe not, this is crypto stuff...
        mic_alg = params.get('micalg', 'nothing')
        if not mic_alg.startswith('pgp-'):
            raise MessageError(f'expected micalg=pgp-..., got: {mic_alg}')

        # RFC 3156 section 5 says that "signed message and transmitted message
        # MUST be identical". We therefore need to validate against the message
        # as it was originally sent.

        # The transmitted content and therefore the signed content are using
        # CRLF as line delimiter, but our eml file has most likely been
        # converted to UNIX LF line ending in the local storage.
        if b'\r\n' not in original_bytes:
            original_bytes = original_bytes.replace(b'\n', b'\r\n')

        # The sender's signed canonical form often differs from the one
        # produced by Python's standard lib (in the number of blank lines
        # between multipart segments...). We therefore need to extract the
        # signed part directly from the original byte string.
        signed_boundary = b'\r\n--' + message.get_boundary().encode()
        original_chunks = original_bytes.split(signed_boundary)
        nb_chunks = len(original_chunks)
        if nb_chunks != 4:
            raise MessageError(
                f'unexpected number of multipart chunks, got {nb_chunks}')

        signed_chunk = original_chunks[1]
        if len(signed_chunk) < len(b'\r\n'):
            raise MessageError('signed chunk has an invalid length')

        sigs = crypto.verify_detached(
            signed_chunk[len(b'\r\n'):],
            signature_part.get_payload(decode=True))

        add_signature_headers(original, sigs, None)

    except (GPGProblem, MessageError) as error:
        add_signature_headers(original, [], str(error))


def _handle_encrypted(original, message, session_keys=None):
    """Handle encrypted messages helper.

    RFC 3156 is quite strict:
    * exactly two messages
    * the first is of type 'application/pgp-encrypted'
    * the first contains 'Version: 1'
    * the second is of type 'application/octet-stream'
    * the second contains the encrypted and possibly signed data

    :param original: The original top-level mail. This is required to attache
        special headers to
    :type original: :class:`email.message.Message`
    :param message: The multipart/signed payload to verify
    :type message: :class:`email.message.Message`
    :param session_keys: a list OpenPGP session keys
    :type session_keys: [str]
    """
    malformed = False

    ct = message.get_payload(0).get_content_type()
    if ct != _APP_PGP_ENC:
        malformed = 'expected Content-Type: {0}, got: {1}'.format(
            _APP_PGP_ENC, ct)

    want = 'application/octet-stream'
    ct = message.get_payload(1).get_content_type()
    if ct != want:
        malformed = 'expected Content-Type: {0}, got: {1}'.format(want, ct)

    if not malformed:
        # This should be safe because PGP uses US-ASCII characters only
        payload = message.get_payload(1).get_payload().encode('ascii')
        try:
            sigs, d = crypto.decrypt_verify(payload, session_keys)
        except GPGProblem as e:
            # signature verification failures end up here too if the combined
            # method is used, currently this prevents the interpretation of the
            # recovered plain text mail. maybe that's a feature.
            malformed = str(e)
        else:
            n = decrypted_message_from_bytes(d, session_keys)

            # add the decrypted message to message. note that n contains all
            # the attachments, no need to walk over n here.
            original.attach(n)

            original.defects.extend(n.defects)

            # there are two methods for both signed and encrypted data, one is
            # called 'RFC 1847 Encapsulation' by RFC 3156, and one is the
            # 'Combined method'.
            if not sigs:
                # 'RFC 1847 Encapsulation', the signature is a detached
                # signature found in the recovered mime message of type
                # multipart/signed.
                if X_SIGNATURE_VALID_HEADER in n:
                    for k in (X_SIGNATURE_VALID_HEADER,
                              X_SIGNATURE_MESSAGE_HEADER):
                        original[k] = n[k]
            else:
                # 'Combined method', the signatures are returned by the
                # decrypt_verify function.

                # note that if we reached this point, we know the signatures
                # are valid. if they were not valid, the else block of the
                # current try would not have been executed
                add_signature_headers(original, sigs, '')

    if malformed:
        msg = 'Malformed OpenPGP message: {0}'.format(malformed)
        content = email.message_from_string(msg,
                                            _class=email.message.EmailMessage,
                                            policy=email.policy.SMTP)
        content.set_charset('utf-8')
        original.attach(content)


def _decrypted_message_from_message(original_bytes, m, session_keys=None):
    '''Detect and decrypt OpenPGP encrypted data in an email object. If this
    succeeds, any mime messages found in the recovered plaintext
    message are added to the returned message object.

    :param original_bytes: the original top-level mail raw bytes,
        containing the segments against which signatures will be verified.
        Necessary because parsing and re-serialising a Message isn't
        byte-perfect, which interferes with signature validation.
    :type original_bytes: bytes
    :param m: an email object
    :param session_keys: a list OpenPGP session keys
    :returns: :class:`email.message.Message` possibly augmented with
              decrypted data
    '''
    # make sure no one smuggles a token in (data from m is untrusted)
    del m[X_SIGNATURE_VALID_HEADER]
    del m[X_SIGNATURE_MESSAGE_HEADER]

    if m.is_multipart():
        p = get_params(m)

        # handle OpenPGP signed data
        if (m.get_content_subtype() == 'signed' and
                p.get('protocol') == _APP_PGP_SIG):
            _handle_signatures(original_bytes, m, m, p)

        # handle OpenPGP encrypted data
        elif (m.get_content_subtype() == 'encrypted' and
              p.get('protocol') == _APP_PGP_ENC and
              'Version: 1' in m.get_payload(0).get_payload()):
            _handle_encrypted(m, m, session_keys)

        # It is also possible to put either of the abov into a multipart/mixed
        # segment
        elif m.get_content_subtype() == 'mixed':
            sub = m.get_payload(0)

            if sub.is_multipart():
                p = get_params(sub)

                if (sub.get_content_subtype() == 'signed' and
                        p.get('protocol') == _APP_PGP_SIG):
                    _handle_signatures(original_bytes, m, sub, p)
                elif (sub.get_content_subtype() == 'encrypted' and
                      p.get('protocol') == _APP_PGP_ENC):
                    _handle_encrypted(m, sub, session_keys)

    return m


def decrypted_message_from_bytes(bytestring, session_keys=None):
    """Create a Message from bytes.

    :param bytes bytestring: an email message as raw bytes
    :param session_keys: a list OpenPGP session keys
    """
    return _decrypted_message_from_message(
        bytestring,
        email.message_from_bytes(bytestring,
                                 _class=email.message.EmailMessage,
                                 policy=email.policy.SMTP),
        session_keys)


def extract_headers(mail, headers=None):
    """
    returns subset of this messages headers as human-readable format:
    all header values are decoded, the resulting string has
    one line "KEY: VALUE" for each requested header present in the mail.

    :param mail: the mail to use
    :type mail: :class:`email.message.EmailMessage`
    :param headers: headers to extract
    :type headers: list of str
    """
    headertext = ''
    if headers is None:
        headers = mail.keys()
    for key in headers:
        value = ''
        if key in mail:
            value = decode_header(mail.get(key, ''))
        headertext += '%s: %s\n' % (key, value)
    return headertext


def render_part(part, field_key='copiousoutput'):
    """
    renders a non-multipart email part into displayable plaintext by piping its
    payload through an external script. The handler itself is determined by
    the mailcap entry for this part's ctype.
    """
    ctype = part.get_content_type()
    raw_payload = remove_cte(part)
    rendered_payload = None
    # get mime handler
    _, entry = settings.mailcap_find_match(ctype, key=field_key)
    if entry is not None:
        tempfile_name = None
        stdin = None
        handler_raw_commandstring = entry['view']
        # in case the mailcap defined command contains no '%s',
        # we pipe the files content to the handling command via stdin
        if '%s' in handler_raw_commandstring:
            # open tempfile, respect mailcaps nametemplate
            nametemplate = entry.get('nametemplate', '%s')
            prefix, suffix = parse_mailcap_nametemplate(nametemplate)
            with tempfile.NamedTemporaryFile(
                    delete=False, prefix=prefix, suffix=suffix) \
                    as tmpfile:
                tmpfile.write(raw_payload)
                tempfile_name = tmpfile.name
        else:
            stdin = raw_payload

        # read parameter, create handler command
        parms = tuple('='.join(p) for p in part.get_params(failobj=[]))

        # create and call external command
        cmd = mailcap.subst(entry['view'], ctype,
                            filename=tempfile_name, plist=parms)
        logging.debug('command: %s', cmd)
        logging.debug('parms: %s', str(parms))
        cmdlist = split_commandstring(cmd)
        # call handler
        stdout, _, _ = helper.call_cmd(cmdlist, stdin=stdin)
        if stdout:
            rendered_payload = stdout

        # remove tempfile
        if tempfile_name:
            os.unlink(tempfile_name)

    return rendered_payload


def remove_cte(part, as_string=False):
    """Interpret MIME-part according to it's Content-Transfer-Encodings.

    This returns the payload of `part` as string or bytestring for display, or
    to be passed to an external program. In the raw file the payload may be
    encoded, e.g. in base64, quoted-printable, 7bit, or 8bit. This method will
    look for one of the above Content-Transfer-Encoding header and interpret
    the payload accordingly.

    Incorrect header values (common in spam messages) will be interpreted as
    lenient as possible and will result in INFO-level debug messages.

    ..Note:: All this may be depricated in favour of
             `email.contentmanager.raw_data_manager` (v3.6+)

    :param email.message.EmailMessage part: The part to decode
    :param bool as_string: If true return a str, otherwise return bytes
    :returns: The mail with any Content-Transfer-Encoding removed
    :rtype: Union[str, bytes]
    """
    enc = part.get_content_charset() or 'ascii'
    cte = str(part.get('content-transfer-encoding', '7bit')).lower().strip()
    payload = part.get_payload()
    sp = ''  # string variant of return value
    bp = b''  # bytestring variant

    logging.debug('Content-Transfer-Encoding: "{}"'.format(cte))
    if cte not in ['quoted-printable', 'base64', '7bit', '8bit', 'binary']:
        logging.info('Unknown Content-Transfer-Encoding: "{}"'.format(cte))

    # switch through all sensible cases
    # starting with those where payload is already a str
    if '7bit' in cte or 'binary' in cte:
        logging.debug('assuming Content-Transfer-Encoding: 7bit')
        sp = payload
        if as_string:
            return sp
        bp = payload.encode('utf-8')
        return bp

    # the remaining cases need decoding and define only bt;
    # decoding into a str is done at the end if requested
    elif '8bit' in cte:
        logging.debug('assuming Content-Transfer-Encoding: 8bit')
        bp = payload.encode('utf8')

    elif 'quoted-printable' in cte:
        logging.debug('assuming Content-Transfer-Encoding: quoted-printable')
        bp = quopri.decodestring(payload.encode('ascii'))

    elif 'base64' in cte:
        logging.debug('assuming Content-Transfer-Encoding: base64')
        bp = base64.b64decode(payload)

    else:
        logging.debug('failed to interpret Content-Transfer-Encoding: '
                      '"{}"'.format(cte))

    # by now, bp is defined, sp is not.
    if as_string:
        try:
            sp = bp.decode(enc)
        except LookupError:
            # enc is unknown;
            # fall back to guessing the correct encoding using libmagic
            sp = helper.try_decode(bp)
        except UnicodeDecodeError as emsg:
            # the mail contains chars that are not enc-encoded.
            # libmagic works better than just ignoring those
            logging.debug('Decoding failure: {}'.format(emsg))
            sp = helper.try_decode(bp)
        return sp
    return bp


MISSING_HTML_MSG = ("This message contains a text/html part that was not "
                    "rendered due to a missing mailcap entry. "
                    "Please refer to item 1 in our FAQ: "
                    "https://alot.rtfd.io/en/latest/faq.html")


def get_body_part(mail, mimetype=None):
    """Returns an EmailMessage.

    This consults :ref:`prefer_plaintext <prefer-plaintext>`
    to determine if a "text/plain" alternative is preferred over a "text/html"
    part.

    :param mail: the mail to use
    :type mail: :class:`email.message.EmailMessage`
    :returns: The combined text of any parts to be used
    :rtype: str
    """

    if not mimetype:
        mimetype = 'plain' if settings.get('prefer_plaintext') else 'html'
    preferencelist = {
        'plain': ('plain', 'html'), 'html': ('html', 'plain')}[mimetype]

    body_part = mail.get_body(preferencelist)
    if body_part is None:  # if no part matching preferredlist was found
        return ""

    return body_part


def extract_body_part(body_part, render=True):
    """
    Returns a string view of a Message.

    :param render: If true (the default), try to render the content with
                   `render_part`; otherwise skip rendering.
    :type render: bool
    """
    displaystring = ""
    if render:
        rendered_payload = render_part(
            body_part,
            **{'field_key': 'view'} if body_part.get_content_type() == 'text/plain'
            else {})
    else:
        rendered_payload = None

    if rendered_payload:  # handler had output
        displaystring = string_sanitize(rendered_payload)
    elif body_part.get_content_type() == 'text/plain':
        displaystring = string_sanitize(remove_cte(body_part, as_string=True))
    else:
        if body_part.get_content_type() == 'text/html':
            displaystring = MISSING_HTML_MSG
    return displaystring


def formataddr(pair):
    """ this is the inverse of email.utils.parseaddr:
    other than email.utils.formataddr, this
    - *will not* re-encode unicode strings, and
    - *will* re-introduce quotes around real names containing commas
    """
    name, address = pair
    if not name:
        return address
    elif ',' in name:
        name = "\"" + name + "\""
    return "{0} <{1}>".format(name, address)


def decode_header(header, normalize=False):
    """
    decode a header value to a unicode string

    values are usually a mixture of different substrings
    encoded in quoted printable using different encodings.
    This turns it into a single unicode string

    :param header: the header value
    :type header: str
    :param normalize: replace trailing spaces after newlines
    :type normalize: bool
    :rtype: str
    """
    logging.debug("unquoted header: |%s|", header)

    valuelist = email.header.decode_header(header)
    decoded_list = []
    for v, enc in valuelist:
        v = string_decode(v, enc)
        decoded_list.append(string_sanitize(v))
    value = ''.join(decoded_list)
    if normalize:
        value = re.sub(r'\n\s+', r' ', value)
    return value


def is_subdir_of(subpath, superpath):
    # make both absolute
    superpath = os.path.realpath(superpath)
    subpath = os.path.realpath(subpath)

    # return true, if the common prefix of both is equal to directory
    # e.g. /a/b/c/d.rst and directory is /a/b, the common prefix is /a/b
    return os.path.commonprefix([subpath, superpath]) == superpath


def clear_my_address(my_account, value):
    """return recipient header without the addresses in my_account

    :param my_account: my account
    :type my_account: :class:`Account`
    :param value: a list of recipient or sender strings (with or without
        real names as taken from email headers)
    :type value: list(str)
    :returns: a new, potentially shortend list
    :rtype: list(str)
    """
    new_value = []
    for name, address in email.utils.getaddresses(value):
        if not my_account.matches_address(address):
            new_value.append(formataddr((name, address)))
    return new_value


def ensure_unique_address(recipients):
    """
    clean up a list of name,address pairs so that
    no address appears multiple times.
    """
    res = dict()
    for name, address in email.utils.getaddresses(recipients):
        res[address] = name
    logging.debug(res)
    urecipients = [formataddr((n, a)) for a, n in res.items()]
    return sorted(urecipients)
