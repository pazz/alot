# vim:ts=4:sw=4:expandtab
import os
import email
import re
import email.charset as charset
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
from email.encoders import encode_7or8bit
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import pyme.core
import pyme.constants
import pyme.errors

from alot import __version__
import logging
import alot.helper as helper
import alot.crypto as crypto
from alot.settings import settings
from alot.errors import GPGProblem

from attachment import Attachment
from utils import encode_header


class Envelope(object):
    """a message that is not yet sent and still editable"""
    def __init__(self, template=None, bodytext=u'', headers={}, attachments=[],
            sign=False, sign_key=None, encrypt=False):
        """
        :param template: if not None, the envelope will be initialised by
                         :meth:`parsing <parse_template>` this string before
                         setting any other values given to this constructor.
        :type template: str
        :param bodytext: text used as body part
        :type bodytext: str
        :param headers: unencoded header values
        :type headers: dict (str -> unicode)
        :param attachments: file attachments to include
        :type attachments: list of :class:`~alot.db.attachment.Attachment`
        """
        assert isinstance(bodytext, unicode)
        self.headers = {}
        self.body = None
        logging.debug('TEMPLATE: %s' % template)
        if template:
            self.parse_template(template)
            logging.debug('PARSED TEMPLATE: %s' % template)
            logging.debug('BODY: %s' % self.body)
        if self.body == None:
            self.body = bodytext
        self.headers.update(headers)
        self.attachments = list(attachments)
        self.sign = sign
        self.sign_key = sign_key
        self.encrypt = encrypt
        self.sent_time = None
        self.modified_since_sent = False

    def __str__(self):
        return "Envelope (%s)\n%s" % (self.headers, self.body)

    def __setitem__(self, name, val):
        """setter for header values. this allows adding header like so:

        >>> envelope['Subject'] = u'sm\xf8rebr\xf8d'
        """
        self.headers[name] = val

        if self.sent_time:
            self.modified_since_sent = True

    def __getitem__(self, name):
        """getter for header values.
        :raises: KeyError if undefined
        """
        return self.headers[name]

    def __delitem__(self, name):
        del(self.headers[name])

        if self.sent_time:
            self.modified_since_sent = True

    def __contains__(self, name):
        return self.headers.__contains__(name)

    def get(self, key, fallback=None):
        """secure getter for header values that allows specifying a `fallback`
        return string (defaults to None). This returns the first matching value
        and doesn't raise KeyErrors"""
        if key in self.headers:
            value = self.headers[key][0]
        else:
            value = fallback
        return value

    def get_all(self, key, fallback=[]):
        """returns all header values for given key"""
        if key in self.headers:
            value = self.headers[key]
        else:
            value = fallback
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
        elif isinstance(attachment, basestring):
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
        canonical_format = self.body.encode('utf-8')
        canonical_format = canonical_format.replace('\\t', ' '*4)
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
            context = crypto.CryptoContext()

            plaintext = crypto.email_as_string(inner_msg)
            logging.info('signing plaintext: ' + plaintext)

            try:
                result, signature_str = context.detached_signature_for(
                        plaintext, self.sign_key)
                if len(result.signatures) != 1:
                    raise GPGProblem(("Could not sign message "
                            "(GPGME did not return a signature)"))
            except pyme.errors.GPGMEError as e:
                # 11 == GPG_ERR_BAD_PASSPHRASE
                if e.getcode() == 11:
                    # If GPG_AGENT_INFO is unset or empty, the user just does
                    # not have gpg-agent running (properly).
                    if os.environ.get('GPG_AGENT_INFO', '').strip() == '':
                        raise GPGProblem(("Bad passphrase and "
                                "GPG_AGENT_INFO not set. Please setup "
                                "gpg-agent."))
                    else:
                        raise GPGProblem(("Bad passphrase. Is "
                                "gpg-agent running?"))
                raise GPGProblem(str(e))

            micalg = crypto.RFC3156_micalg_from_result(result)
            outer_msg = MIMEMultipart('signed', micalg=micalg,
                            protocol='application/pgp-signature')

            # wrap signature in MIMEcontainter
            signature_mime = MIMEApplication(_data=signature_str,
                _subtype='pgp-signature; name="signature.asc"',
                _encoder=encode_7or8bit)
            signature_mime['Content-Description'] = 'signature'
            signature_mime.set_charset('us-ascii')

            # add signed message and signature to outer message
            outer_msg.attach(inner_msg)
            outer_msg.attach(signature_mime)
            outer_msg['Content-Disposition'] = 'inline'
        else:
            outer_msg = inner_msg

        headers = self.headers.copy()
        # add Message-ID
        if 'Message-ID' not in headers:
            headers['Message-ID'] = [email.Utils.make_msgid()]

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
                outer_msg[k] = encode_header(k, v)

        return outer_msg

    def parse_template(self, tmp, reset=False, only_body=False):
        """parses a template or user edited string to fills this envelope.

        :param tmp: the string to parse.
        :type tmp: str
        :param reset: remove previous envelope content
        :type reset: bool
        """
        logging.debug('GoT: """\n%s\n"""' % tmp)

        if self.sent_time:
            self.modified_since_sent = True

        if only_body:
            self.body = tmp
        else:
            m = re.match('(?P<h>([a-zA-Z0-9_-]+:.+\n)*)\n?(?P<b>(\s*.*)*)',
                         tmp)
            assert m

            d = m.groupdict()
            headertext = d['h']
            self.body = d['b']

            # remove existing content
            if reset:
                self.headers = {}

            # go through multiline, utf-8 encoded headers
            # we decode the edited text ourselves here as
            # email.message_from_file can't deal with raw utf8 header values
            key = value = None
            for line in headertext.splitlines():
                if re.match('[a-zA-Z0-9_-]+: ', line):  # new k/v pair
                    if key and value:  # save old one from stack
                        self.add(key, value)  # save
                    key, value = line.strip().split(': ', 1)  # parse new pair
                elif key and value:  # append new line without key prefix
                    value += line
            if key and value:  # save last one if present
                self.add(key, value)
