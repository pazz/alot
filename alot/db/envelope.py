# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import glob
from datetime import datetime
import logging
import os
import re
import email
import email.policy
from email.encoders import encode_7or8bit
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import email.charset as charset
from email.message import Message
from typing import IO, TYPE_CHECKING, Any

import gpg

from .attachment import Attachment
from .. import __version__
from .. import helper
from .. import crypto
from ..settings.const import settings
from ..errors import GPGProblem, GPGCode

if TYPE_CHECKING:
    from ..account import Account
    from .message import Message as AlotMessage

charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


class Envelope:
    """
    a message that is not yet sent and still editable.

    It holds references to unencoded! body text and mail headers among other
    things.  Envelope implements the python container API for easy access of
    header values.  So `e['To']`, `e['To'] = 'foo@bar.baz'` and
    'e.get_all('To')' would work for an envelope `e`..
    """

    headers: dict[str, list[str]]
    """
    dict containing the mail headers (a list of strings for each header key)
    """
    body_txt: str
    """mail body (plaintext) as unicode string"""
    body_html: str | None = None
    """mail body (html) as unicode string"""
    tmpfile: IO[str] | None = None
    """temporary file the body is edited in"""
    attachments: list[Attachment]
    """list of :class:`Attachments <alot.db.attachment.Attachment>`"""
    tags: list[str]
    """tags to add after successful sendout"""
    account: 'Account | None'
    """account to send from"""

    def __init__(
            self, bodytext: str | None = None,
            headers: dict[str, list[str]] | None = None,
            attachments: list[Attachment] | None = None,
            sign: bool = False, sign_key: Any = None, encrypt: bool = False,
            tags: list[str] | None = None,
            replied: 'AlotMessage | None' = None,
            passed: 'AlotMessage | None' = None,
            account: 'Account | None' = None) -> None:
        """
        :param bodytext: text used as body part
        :param headers: unencoded header values
        :param attachments: file attachments to include
        :param sign_key: the :class:`gpg.gpgme._gpgme_key` to sign with
        :param tags: tags to add after successful sendout and saving this msg
        :param replied: message being replied to
        :param passed: message being passed on
        :param account: account to send from
        """
        self.body_txt = bodytext or ''
        # TODO: if this was as collections.defaultdict a number of methods
        # could be simplified.
        self.headers = headers or {}
        self.attachments = list(attachments) if attachments is not None else []
        self.sign = sign
        self.sign_key = sign_key
        self.encrypt = encrypt
        self.encrypt_keys: dict[str, Any] = {}  # fingerprint -> gpg key
        self.tags = tags or []  # tags to add after successful sendout
        self.replied = replied  # message being replied to
        self.passed = passed  # message being passed on
        self.sent_time: datetime | None = None
        self.modified_since_sent = False
        self.sending = False  # semaphore to avoid accidental double sendout
        self.account = account

    def __str__(self) -> str:
        return "Envelope (%s)\n%s" % (self.headers, self.body_txt)

    def __setitem__(self, name: str, val: str) -> None:
        """setter for header values. This allows adding header like so:
        envelope['Subject'] = 'sm\xf8rebr\xf8d'
        """
        if name not in self.headers:
            self.headers[name] = []
        self.headers[name].append(val)

        if self.sent_time:
            self.modified_since_sent = True

    def __getitem__(self, name: str) -> str:
        """getter for header values.
        :raises: KeyError if undefined
        """
        return self.headers[name][0]

    def __delitem__(self, name: str) -> None:
        del self.headers[name]

        if self.sent_time:
            self.modified_since_sent = True

    def __contains__(self, name: object) -> bool:
        return name in self.headers

    def get(self, key: str, fallback: str | None = None) -> str | None:
        """secure getter for header values that allows specifying a `fallback`
        return string (defaults to None). This returns the first matching value
        and doesn't raise KeyErrors"""
        return self.headers[key][0] if key in self.headers else fallback

    def get_all(self, key: str,
                fallback: list[str] | None = None) -> list[str]:
        """returns all header values for given key"""
        return self.headers.get(key, fallback or [])

    def add(self, key: str, value: str) -> None:
        """add header value"""
        if key not in self.headers:
            self.headers[key] = []
        self.headers[key].append(value)

        if self.sent_time:
            self.modified_since_sent = True

    def attach(self, attachment: Attachment | str, filename: str | None = None,
               ctype: str | None = None) -> None:
        """
        attach a file

        :param attachment: File to attach, given as
            :class:`~alot.db.attachment.Attachment` object or path to a file.
        :param filename: filename to use in content-disposition.
            Will be ignored if `path` matches multiple files
        :param ctype: force content-type to be used for this attachment
        """

        if isinstance(attachment, Attachment):
            self.attachments.append(attachment)
        elif isinstance(attachment, str):
            path = os.path.expanduser(attachment)
            part = helper.mimewrap(path, filename, ctype)
            self.attachments.append(Attachment(part))
        else:
            raise TypeError('attach accepts an Attachment or str')

        if self.sent_time:
            self.modified_since_sent = True

    def construct_mail(self) -> Message:
        """
        Compiles the information contained in this envelope into a
        :class:`email.message.Message`.
        """
        textpart = MIMEText(self.body_txt, 'plain', 'utf-8')
        inner_msg: Message = textpart

        if self.body_html:
            htmlpart = MIMEText(self.body_html, 'html', 'utf-8')
            inner_msg = MIMEMultipart('alternative')
            inner_msg.attach(textpart)
            inner_msg.attach(htmlpart)

        # wrap everything in a multipart container if there are attachments
        if self.attachments:
            msg = MIMEMultipart('mixed')
            msg.attach(inner_msg)
            # add attachments
            for a in self.attachments:
                msg.attach(a.get_mime_representation())
            inner_msg = msg

        if self.sign:
            plaintext = inner_msg.as_bytes(policy=email.policy.SMTP)
            logging.debug('signing plaintext: %s', plaintext)

            try:
                signatures, signature_str = crypto.detached_signature_for(
                    plaintext, [self.sign_key])
                if len(signatures) != 1:
                    raise GPGProblem("Could not sign message (GPGME "
                                     "did not return a signature)",
                                     code=GPGCode.KEY_CANNOT_SIGN)
            except gpg.errors.GPGMEError as e:
                if e.getcode() == gpg.errors.BAD_PASSPHRASE:
                    # If GPG_AGENT_INFO is unset or empty, the user just does
                    # not have gpg-agent running (properly).
                    if os.environ.get('GPG_AGENT_INFO', '').strip() == '':
                        errmsg = "Got invalid passphrase and GPG_AGENT_INFO\
                                not set. Please set up gpg-agent."
                        raise GPGProblem(errmsg, code=GPGCode.BAD_PASSPHRASE)
                    else:
                        raise GPGProblem("Bad passphrase. Is gpg-agent "
                                         "running?",
                                         code=GPGCode.BAD_PASSPHRASE)
                raise GPGProblem(str(e), code=GPGCode.KEY_CANNOT_SIGN)

            micalg = crypto.RFC3156_micalg_from_algo(signatures[0].hash_algo)
            unencrypted_msg: Message = MIMEMultipart(
                'signed', micalg=micalg, protocol='application/pgp-signature')

            # wrap signature in MIMEcontainter
            stype = 'pgp-signature; name="signature.asc"'
            signature_mime = MIMEApplication(
                _data=signature_str.decode('ascii'),
                _subtype=stype,
                _encoder=encode_7or8bit)
            signature_mime['Content-Description'] = 'signature'
            signature_mime.set_charset('us-ascii')

            # add signed message and signature to outer message
            unencrypted_msg.attach(inner_msg)
            unencrypted_msg.attach(signature_mime)
            unencrypted_msg['Content-Disposition'] = 'inline'
        else:
            unencrypted_msg = inner_msg

        if self.encrypt:
            plaintext = unencrypted_msg.as_bytes(policy=email.policy.SMTP)
            logging.debug('encrypting plaintext: %s', plaintext)

            try:
                encrypted_str = crypto.encrypt(
                    plaintext, list(self.encrypt_keys.values()))
            except gpg.errors.GPGMEError as e:
                raise GPGProblem(str(e), code=GPGCode.KEY_CANNOT_ENCRYPT)

            outer_msg: Message = MIMEMultipart(
                'encrypted', protocol='application/pgp-encrypted')

            version_str = 'Version: 1'
            encryption_mime = MIMEApplication(_data=version_str,
                                              _subtype='pgp-encrypted',
                                              _encoder=encode_7or8bit)
            encryption_mime.set_charset('us-ascii')

            encrypted_mime = MIMEApplication(
                _data=encrypted_str.decode('ascii'),
                _subtype='octet-stream',
                _encoder=encode_7or8bit)
            encrypted_mime.set_charset('us-ascii')
            outer_msg.attach(encryption_mime)
            outer_msg.attach(encrypted_mime)

        else:
            outer_msg = unencrypted_msg

        headers = self.headers.copy()

        # add Date header
        if 'Date' not in headers:
            headers['Date'] = [email.utils.formatdate(localtime=True)]

        # add Message-ID
        if 'Message-ID' not in headers:
            domain = self.account.message_id_domain if self.account else None
            headers['Message-ID'] = [email.utils.make_msgid(domain=domain)]

        if 'User-Agent' in headers:
            uastring_format = headers['User-Agent'][0]
        else:
            uastring_format = settings.get('user_agent').strip()
        uastring = uastring_format.format(version=__version__)
        if uastring:
            headers['User-Agent'] = [uastring]

        # set policy on outer_msg to ease encoding headers
        outer_msg.policy = email.policy.default
        # copy headers from envelope to mail, keeping the generated MIME
        # structure headers (Content-Type etc.) rather than duplicating them
        for k, vlist in headers.items():
            if k in outer_msg:
                continue
            for v in vlist:
                outer_msg.add_header(k, v)

        return outer_msg

    def parse_template(self, raw: str, only_body: bool = False,
                       target_body: str = 'plaintext') -> None:
        """Parse a template or user edited string to fills this envelope.

        :param raw: the string to parse.
        :param only_body: do not parse headers
        :param target_body: body text alternative this should be stored in;
            can be 'plaintext' or 'html'
        """
        logging.debug('GoT: """\n%s\n"""', raw)

        if self.sent_time:
            self.modified_since_sent = True

        headerEndPos = 0
        if not only_body:
            # go through multiline, utf-8 encoded headers
            # locally, lines are separated by a simple LF, not CRLF
            # we decode the edited text ourselves here as
            # email.message_from_file can't deal with raw utf8 header values
            headerRe = re.compile(r'^(?P<k>.+?):(?P<v>(.|\n[ \t\r\f\v])+)$',
                                  re.MULTILINE)
            for header in headerRe.finditer(raw):
                if header.start() > headerEndPos + 1:
                    break  # switched to body

                key = header.group('k')
                # simple unfolding as decribed in
                # https://tools.ietf.org/html/rfc2822#section-2.2.3
                unfoldedValue = header.group('v').replace('\n', '')
                self.add(key, unfoldedValue.strip())
                headerEndPos = header.end()

            # interpret 'Attach' pseudo header
            if 'Attach' in self:
                to_attach = []
                for line in self.get_all('Attach'):
                    gpath = os.path.expanduser(line.strip())
                    to_attach += [g for g in glob.glob(gpath)
                                  if os.path.isfile(g)]
                logging.debug('Attaching: %s', to_attach)
                for path in to_attach:
                    self.attach(path)
                del self['Attach']

        body = raw[headerEndPos:].strip()
        if target_body == 'html':
            self.body_html = body
        else:
            self.body_txt = body
