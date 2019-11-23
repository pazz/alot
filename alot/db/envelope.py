# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import glob
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
import gpg

from .attachment import Attachment
from .. import __version__
from .. import helper
from .. import crypto
from ..settings.const import settings
from ..errors import GPGProblem, GPGCode

charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


class Envelope:
    """
    a message that is not yet sent and still editable.

    It holds references to unencoded! body text and mail headers among other
    things.  Envelope implements the python container API for easy access of
    header values.  So `e['To']`, `e['To'] = 'foo@bar.baz'` and
    'e.get_all('To')' would work for an envelope `e`..
    """

    headers = None
    """
    dict containing the mail headers (a list of strings for each header key)
    """
    body_txt = None
    """mail body (plaintext) as unicode string"""
    body_html = None
    """mail body (html) as unicode string"""
    tmpfile = None
    """template text for initial content"""
    attachments = None
    """list of :class:`Attachments <alot.db.attachment.Attachment>`"""
    tags = []
    """tags to add after successful sendout"""
    account = None
    """account to send from"""

    def __init__(
            self, template=None, bodytext=None, headers=None, attachments=None,
            sign=False, sign_key=None, encrypt=False, tags=None, replied=None,
            passed=None, account=None):
        """
        :param template: if not None, the envelope will be initialised by
                         :meth:`parsing <parse_template>` this string before
                         setting any other values given to this constructor.
        :type template: str
        :param bodytext: text used as body part
        :type bodytext: str
        :param headers: unencoded header values
        :type headers: dict (str -> [unicode])
        :param attachments: file attachments to include
        :type attachments: list of :class:`~alot.db.attachment.Attachment`
        :param tags: tags to add after successful sendout and saving this msg
        :type tags: list of str
        :param replied: message being replied to
        :type replied: :class:`~alot.db.message.Message`
        :param passed: message being passed on
        :type replied: :class:`~alot.db.message.Message`
        :param account: account to send from
        :type account: :class:`Account`
        """
        logging.debug('TEMPLATE: %s', template)
        if template:
            self.parse_template(template)
            logging.debug('PARSED TEMPLATE: %s', template)
            logging.debug('BODY: %s', self.body_txt)
        self.body_txt = bodytext or ''
        # TODO: if this was as collections.defaultdict a number of methods
        # could be simplified.
        self.headers = headers or {}
        self.attachments = list(attachments) if attachments is not None else []
        self.sign = sign
        self.sign_key = sign_key
        self.encrypt = encrypt
        self.encrypt_keys = {}
        self.tags = tags or []  # tags to add after successful sendout
        self.replied = replied  # message being replied to
        self.passed = passed  # message being passed on
        self.sent_time = None
        self.modified_since_sent = False
        self.sending = False  # semaphore to avoid accidental double sendout
        self.account = account

    def __str__(self):
        return "Envelope (%s)\n%s" % (self.headers, self.body_txt)

    def __setitem__(self, name, val):
        """setter for header values. This allows adding header like so:
        envelope['Subject'] = 'sm\xf8rebr\xf8d'
        """
        if name not in self.headers:
            self.headers[name] = []
        self.headers[name].append(val)

        if self.sent_time:
            self.modified_since_sent = True

    def __getitem__(self, name):
        """getter for header values.
        :raises: KeyError if undefined
        """
        return self.headers[name][0]

    def __delitem__(self, name):
        del self.headers[name]

        if self.sent_time:
            self.modified_since_sent = True

    def __contains__(self, name):
        return name in self.headers

    def get(self, key, fallback=None):
        """secure getter for header values that allows specifying a `fallback`
        return string (defaults to None). This returns the first matching value
        and doesn't raise KeyErrors"""
        if key in self.headers:
            value = self.headers[key][0]
        else:
            value = fallback
        return value

    def get_all(self, key, fallback=None):
        """returns all header values for given key"""
        if key in self.headers:
            value = self.headers[key]
        else:
            value = fallback or []
        return value

    def add(self, key, value):
        """add header value"""
        if key not in self.headers:
            self.headers[key] = []
        self.headers[key].append(value)

        if self.sent_time:
            self.modified_since_sent = True

    def attach(self, attachment, filename=None, ctype=None):
        """
        attach a file

        :param attachment: File to attach, given as
            :class:`~alot.db.attachment.Attachment` object or path to a file.
        :type attachment: :class:`~alot.db.attachment.Attachment` or str
        :param filename: filename to use in content-disposition.
            Will be ignored if `path` matches multiple files
        :param ctype: force content-type to be used for this attachment
        :type ctype: str
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

    def construct_mail(self):
        """
        compiles the information contained in this envelope into a
        :class:`email.Message`.
        """
        # Build body text part. To properly sign/encrypt messages later on, we
        # convert the text to its canonical format (as per RFC 2015).
        canonical_format = self.body_txt.encode('utf-8')
        textpart = MIMEText(canonical_format, 'plain', 'utf-8')

        # wrap it in a multipart container if necessary
        if self.attachments:
            inner_msg = MIMEMultipart()
            inner_msg.attach(textpart)
            # add attachments
            for a in self.attachments:
                inner_msg.attach(a.get_mime_representation())
        else:
            inner_msg = textpart

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
                        msg = "Got invalid passphrase and GPG_AGENT_INFO\
                                not set. Please set up gpg-agent."
                        raise GPGProblem(msg, code=GPGCode.BAD_PASSPHRASE)
                    else:
                        raise GPGProblem("Bad passphrase. Is gpg-agent "
                                         "running?",
                                         code=GPGCode.BAD_PASSPHRASE)
                raise GPGProblem(str(e), code=GPGCode.KEY_CANNOT_SIGN)

            micalg = crypto.RFC3156_micalg_from_algo(signatures[0].hash_algo)
            unencrypted_msg = MIMEMultipart(
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

            outer_msg = MIMEMultipart('encrypted',
                                      protocol='application/pgp-encrypted')

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
            domain = settings.get('message_id_domain')
            headers['Message-ID'] = [email.utils.make_msgid(domain=domain)]

        if 'User-Agent' in headers:
            uastring_format = headers['User-Agent'][0]
        else:
            uastring_format = settings.get('user_agent').strip()
        uastring = uastring_format.format(version=__version__)
        if uastring:
            headers['User-Agent'] = [uastring]

        # copy headers from envelope to mail
        for k, vlist in headers.items():
            for v in vlist:
                outer_msg.add_header(k, v)

        return outer_msg

    def parse_template(self, raw, reset=False, only_body=False):
        """parses a template or user edited string to fills this envelope.

        :param raw: the string to parse.
        :type raw: str
        :param reset: remove previous envelope content
        :type reset: bool
        :param only_body: do not parse headers
        :type only_body: bool
        """
        logging.debug('GoT: """\n%s\n"""', raw)

        if self.sent_time:
            self.modified_since_sent = True

        if reset:
            self.headers = {}

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

        self.body = raw[headerEndPos:].strip()
