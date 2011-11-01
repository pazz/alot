from twisted.internet.defer import inlineCallbacks, returnValue
import pyme
from pyme import core, callbacks
from pyme.constants.sig import mode

from cStringIO import StringIO
import os
import re
#import GnuPGInterface # Maybe should use this instead of subprocess
import sys
import types

import logging

from email import Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.encoders import encode_7or8bit
from email.generator import Generator
from email.parser import Parser
from email.utils import getaddresses
import email

class GPGManager:
    def __init__(self, ui):
        self.ui = ui
		## set GPGHOME environment - this should be used by pyme
        os.environ["GNUPGHOME"] = '/home/pazz/.gnupg'
        ## we _must_ import pyme after configuring the GNUPGHOME setting
        import pyme.core
        self.pyme = pyme
        self.context = self.pyme.core.Context()
        self.context.set_armor(1)

    @inlineCallbacks
    def _defer_wrap(self, fun, *args, **kwargs):
        try:
            hint = ''
            desc = ''
            times = 3
            self.ui.logger.debug(args)
            self.ui.logger.debug(kwargs)

            def constant_callback(pwd):
                def g(x,y,z, hook=None):
                    hint = x
                    desc = y
                    return pwd
                return g
            f = constant_callback('')
            for i in range(times):
                try:
                    v = yield fun(*args, **kwargs)
                    #self.ui.logger.debug('RESULT: %s' % v)
                    returnValue(v)
                except pyme.errors.GPGMEError, e:
                    #self.ui.notify(e.getstring(), priority='error')
                    if 'Bad passphrase' in e.getstring():
                        msg = "Please supply %s' password%s>" % (hint, desc)
                        pwd = yield self.ui.prompt(prefix=msg)
                        #self.ui.notify('PASSWORD %s' % pwd)
                        f = constant_callback(pwd)
                        self.context.set_passphrase_cb(f)
                    else:
                        raise e
        except Exception,e:
            self.ui.logger.exception(e)


    def encrypt_block(self, plain, keylist):
        """encrypts a plaintext string to a list of recipients keys,
        as indicated by `keylist`"""
        plaindata = self.pyme.core.Data(plain)
        cipher = self.pyme.core.Data(plain)
        self.context.op_encrypt(keylist, 1, plaindata, cipher)
        cipher.seek(0, 0)
        return cipher.read()

    def sign_block(self, tosign, keyhint):
        """signs a plaintext with private key as indicated by `keyhint`"""
        plain = core.Data(tosign)
        sig = core.Data()

        self.context.signers_clear()
        for sigkey in self.context.op_keylist_all(keyhint, 1):
            if sigkey.can_sign:
                self.context.signers_add(sigkey)
        #if not c.signers_enum(0):
            # todo: raise err
         #   ui.notify("No secret %s's keys suitable for signing!" % user)
        self.context.op_sign(plain, sig, mode.DETACH)
        sig.seek(0,0)
        r = sig.read()
        #self.ui.logger.debug(r)
        return r #returnValue(r)

    def decrypt_block(self, text):
        """tries to decode ciphertext"""
        cipher = self.pyme.core.Data(text)
        plain = self.pyme.core.Data()
        try:
            self.context.op_decrypt(cipher, plain)
        except self.pyme.errors.GPGMEError:
            ## decryption failed - we do not do anything
            plain = self.pyme.core.Data(DECRYPT_ERROR)
        plain.seek(0, 0)
        return plain.read()

    @inlineCallbacks
    def sign(self, *args, **kwargs):
        r = yield self._defer_wrap(self.sign_block, *args, **kwargs)
        returnValue(r)

    def get_valid_keys(self, pattern=""):
		return [ key for key in self.context.op_keylist_all(pattern, 0)
				if (key.can_encrypt != 0) ]

    def is_encrypted(self, text):
		return text.find("-----BEGIN PGP MESSAGE-----") != -1

    def canonical_form(self, string):
        """normalises string to canonical form (cf rfc2015)"""
        cf = string.replace('\\t', ' '*4)
        cf = re.sub("\r?\n", "\r\n", cf)
        return cf

    @inlineCallbacks
    def sign_mail(self, mail, keyhint):
        """
        returns mail signed and wrapped in a multipart/signed email
        """
        try:
            tosign = self.canonical_form(mail.as_string())
            boundary = mail.get_boundary()
            mail = email.message_from_string(tosign)
            mail.set_boundary(boundary)
            signature = yield self._defer_wrap(self.sign_block, tosign, keyhint)

            sig = MIMEApplication(_data=signature,
                                  _subtype='pgp-signature; name="signature.asc"',
                                  _encoder=encode_7or8bit)
            sig['Content-Description'] = 'signature'
            sig.set_charset('us-ascii')

            msg = MIMEMultipart('signed', micalg='pgp-sha1',
                                protocol='application/pgp-signature')
            msg.attach(mail)
            msg.attach(sig)

            msg['Content-Disposition'] = 'inline'
            returnValue(msg)
        except Exception, e:
            logging.exception(e)


    def encrypt(self, header, passphrase=None):
        """
        multipart/encrypted
         +-> application/pgp-encrypted  (control information)
         +-> application/octet-stream   (body)
        """
        body = self.clearBodyPart()
        toenc = flatten(body)

        recipients = []
        #TODO magic
        encrypted = output

        enc = MIMEApplication(_data=encrypted, _subtype='octet-stream',
                              _encoder=encode_7or8bit)
        enc.set_charset('us-ascii')

        control = MIMEApplication(_data='Version: 1\n', _subtype='pgp-encrypted',
                                  _encoder=encode_7or8bit)

        msg = MIMEMultipart('encrypted', micalg='pgp-sha1',
                            protocol='application/pgp-encrypted')
        msg.attach(control)
        msg.attach(enc)

        msg['Content-Disposition'] = 'inline'
        return msg
    def signAndEncrypt(self, header, passphrase=None):
        """
        multipart/encrypted
         +-> application/pgp-encrypted  (control information)
         +-> application/octet-stream   (body)
        """
        body = self.sign(header, passphrase)
        body.__delitem__('Bcc')
        original = flatten(body)
        return self.encrypt(original)
