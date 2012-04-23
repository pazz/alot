# vim:ts=4:sw=4:expandtab
import re

from email.generator import Generator
from cStringIO import StringIO
import pyme.core
import pyme.constants


def email_as_string(mail):
    # Converting inner_msg to text with as_string() mangles lines
    # beginning with "From", therefore we do it the hard way.
    fp = StringIO()
    g = Generator(fp, mangle_from_=False)
    g.flatten(mail)
    return RFC3156_canonicalize(fp.getvalue())


def _engine_file_name_by_protocol(engines, protocol):
    for engine in engines:
        if engine.protocol == protocol:
            return engine.file_name
    return None


def RFC3156_micalg_from_result(result):
    """
    Converts a GPGME hash algorithm name to one conforming to RFC3156.

    GPGME returns hash algorithm names such as "SHA256", but RFC3156 says that
    programs need to use names such as "pgp-sha256" instead.

    :param result: GPGME op_sign_result() return value
    :rtype: str
    """
    # hash_algo will be something like SHA256, but we need pgp-sha256.
    hash_algo = pyme.core.hash_algo_name(result.signatures[0].hash_algo)
    return 'pgp-' + hash_algo.lower()


def RFC3156_canonicalize(text):
    """
    Canonicalizes plain text (MIME-encoded usually) according to RFC3156.

    This function works as follows (in that order):

    1. Convert all line endings to \\\\r\\\\n (DOS line endings).
    2. Ensure the text ends with a newline (\\\\r\\\\n).
    3. Encode all occurences of "From " at the beginning of a line
       to "From=20" in order to prevent other mail programs to replace
       this with "> From" (to avoid MBox conflicts) and thus invalidate
       the signature.

    :param text: text to canonicalize (already encoded as quoted-printable)
    :rtype: str
    """
    text = re.sub("\r?\n", "\r\n", text)
    if not text.endswith("\r\n"):
        text += "\r\n"
    text = re.sub("^From ", "From=20", text, flags=re.MULTILINE)
    return text


class CryptoContext(pyme.core.Context):
    """
    This is a wrapper around pyme.core.Context which simplifies the pyme API.
    """
    def __init__(self):
        pyme.core.Context.__init__(self)
        gpg_path = _engine_file_name_by_protocol(pyme.core.get_engine_info(),
                pyme.constants.PROTOCOL_OpenPGP)
        if not gpg_path:
            # TODO: proper exception
            raise "no GPG engine found"

        self.set_engine_info(pyme.constants.PROTOCOL_OpenPGP, gpg_path)
        self.set_armor(1)

    def detached_signature_for(self, plaintext_str):
        """
        Signs the given plaintext string and returns the detached signature.

        A detached signature in GPG speak is a separate blob of data containing
        a signature for the specified plaintext.

        .. note:: You should use #set_passphrase_cb before calling this method
                  if gpg-agent is not running.
        ::

            context = crypto.CryptoContext()
            def gpg_passphrase_cb(hint, desc, prev_bad):
                return raw_input("Passphrase for key " + hint + ":")
            context.set_passphrase_cb(gpg_passphrase_cb)
            result, signature = context.detached_signature_for('Hello World')
            if result is None:
                return

        :param plaintext_str: text to sign
        :rtype: tuple of pyme.pygpgme._gpgme_op_sign_result and str
        """
        plaintext_data = pyme.core.Data(plaintext_str)
        signature_data = pyme.core.Data()
        self.op_sign(plaintext_data, signature_data,
            pyme.pygpgme.GPGME_SIG_MODE_DETACH)
        result = self.op_sign_result()
        signature_data.seek(0, 0)
        signature = signature_data.read()
        return result, signature
