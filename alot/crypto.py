# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re

from email.generator import Generator
from cStringIO import StringIO
from alot.errors import GPGProblem
import gpgme


def email_as_string(mail):
    """
    Converts the given message to a string, without mangling "From" lines
    (like as_string() does).

    :param mail: email to convert to string
    :rtype: str
    """
    fp = StringIO()
    g = Generator(fp, mangle_from_=False)
    g.flatten(mail)
    return RFC3156_canonicalize(fp.getvalue())


def _hash_algo_name(hash_algo):
    """
    Re-implements GPGME's hash_algo_name as long as pygpgme doesn't wrap that
    function.

    :param hash_algo: GPGME hash_algo
    :rtype: str
    """
    mapping = {
        gpgme.MD_MD5: "MD5",
        gpgme.MD_SHA1: "SHA1",
        gpgme.MD_RMD160: "RIPEMD160",
        gpgme.MD_MD2: "MD2",
        gpgme.MD_TIGER: "TIGER192",
        gpgme.MD_HAVAL: "HAVAL",
        gpgme.MD_SHA256: "SHA256",
        gpgme.MD_SHA384: "SHA384",
        gpgme.MD_SHA512: "SHA512",
        gpgme.MD_MD4: "MD4",
        gpgme.MD_CRC32: "CRC32",
        gpgme.MD_CRC32_RFC1510: "CRC32RFC1510",
        gpgme.MD_CRC24_RFC2440: "CRC24RFC2440",
    }
    if hash_algo in mapping:
        return mapping[hash_algo]
    else:
        raise GPGProblem(("Invalid hash_algo passed to hash_algo_name."
            " Please report this as a bug in alot."))


def RFC3156_micalg_from_algo(hash_algo):
    """
    Converts a GPGME hash algorithm name to one conforming to RFC3156.

    GPGME returns hash algorithm names such as "SHA256", but RFC3156 says that
    programs need to use names such as "pgp-sha256" instead.

    :param hash_algo: GPGME hash_algo
    :rtype: str
    """
    # hash_algo will be something like SHA256, but we need pgp-sha256.
    hash_algo = _hash_algo_name(hash_algo)
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


def get_key(keyid):
    """
    Gets a key from the keyring by filtering for the specified keyid, but
    only if the given keyid is specific enough (if it matches multiple
    keys, an exception will be thrown).

    :param keyid: filter term for the keyring (usually a key ID)
    :rtype: gpgme.Key
    """
    ctx = gpgme.Context()
    try:
        key = ctx.get_key(keyid)
    except gpgme.GpgmeError as e:
        if e.code == gpgme.ERR_AMBIGUOUS_NAME:
            # Deferred import to avoid a circular import dependency
            from alot.db.errors import GPGProblem
            raise GPGProblem(("More than one key found matching this filter."
                " Please be more specific (use a key ID like 4AC8EE1D)."))
        else:
            raise e
    return key


def detached_signature_for(plaintext_str, key=None):
    """
    Signs the given plaintext string and returns the detached signature.

    A detached signature in GPG speak is a separate blob of data containing
    a signature for the specified plaintext.

    :param plaintext_str: text to sign
    :param key: gpgme_key_t object representing the key to use
    :rtype: tuple of gpgme.NewSignature array and str
    """
    ctx = gpgme.Context()
    ctx.armor = True
    if key is not None:
        ctx.signers = [key]
    plaintext_data = StringIO(plaintext_str)
    signature_data = StringIO()
    sigs = ctx.sign(plaintext_data, signature_data, gpgme.SIG_MODE_DETACH)
    signature_data.seek(0, 0)
    signature = signature_data.read()
    return sigs, signature
