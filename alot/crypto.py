import sys, os, re
from twisted.internet.defer import inlineCallbacks, returnValue
import pyme
from pyme import core, callbacks
from pyme.constants.sig import mode


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

    def _sign(self, tosign, keyhint):
        plain = core.Data(tosign)
        sig = core.Data()

        self.context.signers_clear()
        for sigkey in self.context.op_keylist_all(keyhint, 1):
            if sigkey.can_sign:
                self.context.signers_add(sigkey)
        #if not c.signers_enum(0):
         #   ui.notify("No secret %s's keys suitable for signing!" % user)
        self.context.op_sign(plain, sig, mode.CLEAR)
        sig.seek(0,0)
        r = sig.read()
        #self.ui.logger.debug(r)
        return r #returnValue(r)

    @inlineCallbacks
    def sign(self, *args, **kwargs):
        r = yield self._defer_wrap(self._sign, *args, **kwargs)
        returnValue(r)

    def get_valid_keys(self, pattern=""):
		return [ key for key in self.context.op_keylist_all(pattern, 0)
				if (key.can_encrypt != 0) ]

    def encrypt_to_keys(self, plain, keylist):
		plaindata = self.pyme.core.Data(plain)
		cipher = self.pyme.core.Data(plain)
		self.context.op_encrypt(keylist, 1, plaindata, cipher)
		cipher.seek(0, 0)
		return cipher.read()


#	def reencrypt_mail(self, mail, keys):
#		if mail.is_multipart():
#			payloads = mail.get_payload()
#			index = 0
#			while index < len(payloads):
#				if self.is_encrypted(payloads[index].get_payload()):
#					decrypted_part = email.message_from_string(
#							self.decrypt_block(payloads[index].get_payload()))
#					if keys:
#						payloads[index].set_payload(self.encrypt_to_keys(
#								decrypted_part.as_string(), keys))
#				index += 1
#		else:
#			if self.is_encrypted(mail.get_payload()):
#				if keys:
#					mail.set_payload(self.encrypt_to_keys(
#							self.decrypt_block(mail.get_payload()), keys))
#
    def is_encrypted(self, text):
		return text.find("-----BEGIN PGP MESSAGE-----") != -1


    def decrypt_block(self, text):
        cipher = self.pyme.core.Data(text)
        plain = self.pyme.core.Data()
        try:
            self.context.op_decrypt(cipher, plain)
        except self.pyme.errors.GPGMEError:
            ## decryption failed - we do not do anything
            plain = self.pyme.core.Data(DECRYPT_ERROR)
        plain.seek(0, 0)
        return plain.read()
