# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re
import os

from email.generator import Generator
from cStringIO import StringIO
from alot.errors import GPGProblem, GPGCode
from email.mime.multipart import MIMEMultipart
import gpgme


def email_as_string(mail):
    """
    Converts the given message to a string, without mangling "From" lines
    (like as_string() does).

    :param mail: email to convert to string
    :rtype: str
    """
    fp = StringIO()
    g = Generator(fp, mangle_from_=False, maxheaderlen=78)
    g.flatten(mail)
    as_string = RFC3156_canonicalize(fp.getvalue())

    if isinstance(mail, MIMEMultipart):
        # Get the boundary for later
        boundary = mail.get_boundary()

        # Workaround for http://bugs.python.org/issue14983:
        # Insert a newline before the outer mail boundary so that other mail
        # clients can verify the signature when sending an email which contains
        # attachments.
        as_string = re.sub(r'--(\r\n)--' + boundary,
                           '--\g<1>\g<1>--' + boundary,
                           as_string, flags=re.MULTILINE)

    return as_string


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
                          " Please report this as a bug in alot."),
                         code=GPGCode.INVALID_HASH)


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


def get_key(keyid, validate=False, encrypt=False, sign=False):
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
        if validate:
            validate_key(key, encrypt=encrypt, sign=sign)
    except gpgme.GpgmeError as e:
        if e.code == gpgme.ERR_AMBIGUOUS_NAME:
            keys = list_keys(hint=keyid)
            valid_key = None
            for k in keys:
                try:
                    validate_key(k, encrypt=encrypt, sign=sign)
                except GPGProblem:
                    # if the key is invalid for given action skip it
                    continue

                if valid_key:
                    # we have already found one valid key and now we find
                    # another?
                    raise GPGProblem(("More than one key found matching " +
                                      "this filter. Please be more " +
                                      "specific (use a key ID like " +
                                      "4AC8EE1D)."),
                                     code=GPGCode.AMBIGUOUS_NAME)
                valid_key = k

            if not valid_key:
                # there were multiple keys found but none of them are valid for
                # given action
                raise GPGProblem("Can not find usable key for \'" + keyid + "\'.",
                                 code=GPGCode.NOT_FOUND)
            return valid_key
        elif e.code == gpgme.ERR_INV_VALUE or e.code == gpgme.ERR_EOF:
            raise GPGProblem("Can not find key for \'" + keyid + "\'.",
                             code=GPGCode.NOT_FOUND)
        else:
            raise e
    return key


def list_keys(hint=None, private=False):
    """
    Returns a list of all keys containing keyid.

    :param keyid: The part we search for
    :param private: Whether secret keys are listed
    :rtype: list
    """
    ctx = gpgme.Context()
    return ctx.keylist(hint, private)


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
    signature_data.seek(0, os.SEEK_SET)
    signature = signature_data.read()
    return sigs, signature


def encrypt(plaintext_str, keys=None):
    """
    Encrypts the given plaintext string and returns a PGP/MIME compatible
    string

    :param plaintext_str: the mail to encrypt
    :param key: gpgme_key_t object representing the key to use
    :rtype: a string holding the encrypted mail
    """
    plaintext_data = StringIO(plaintext_str)
    encrypted_data = StringIO()
    ctx = gpgme.Context()
    ctx.armor = True
    ctx.encrypt(keys, gpgme.ENCRYPT_ALWAYS_TRUST, plaintext_data,
                encrypted_data)
    encrypted_data.seek(0, os.SEEK_SET)
    encrypted = encrypted_data.read()
    return encrypted


def verify_detached(message, signature):
    '''Verifies whether the message is authentic by checking the
    signature.

    :param message: the message as `str`
    :param signature: a `str` containing an OpenPGP signature
    :returns: a list of :class:`gpgme.Signature`
    :raises: :class:`~alot.errors.GPGProblem` if the verification fails
    '''
    message_data = StringIO(message)
    signature_data = StringIO(signature)
    ctx = gpgme.Context()
    try:
        return ctx.verify(signature_data, message_data, None)
    except gpgme.GpgmeError as e:
        raise GPGProblem(e.message, code=e.code)


def decrypt_verify(encrypted):
    '''Decrypts the given ciphertext string and returns both the
    signatures (if any) and the plaintext.

    :param encrypted: the mail to decrypt
    :returns: a tuple (sigs, plaintext) with sigs being a list of a
              :class:`gpgme.Signature` and plaintext is a `str` holding
              the decrypted mail
    :raises: :class:`~alot.errors.GPGProblem` if the decryption fails
    '''
    encrypted_data = StringIO(encrypted)
    plaintext_data = StringIO()
    ctx = gpgme.Context()
    try:
        sigs = ctx.decrypt_verify(encrypted_data, plaintext_data)
    except gpgme.GpgmeError as e:
        raise GPGProblem(e.message, code=e.code)

    plaintext_data.seek(0, os.SEEK_SET)
    return sigs, plaintext_data.read()


def hash_key(key):
    """
    Returns a hash of the given key. This is a workaround for
    https://bugs.launchpad.net/pygpgme/+bug/1089865
    and can be removed if the missing feature is added to pygpgme

    :param key: the key we want a hash of
    :rtype: a has of the key as string
    """
    hash_str = ""
    for tmp_key in key.subkeys:
        hash_str += tmp_key.keyid
    return hash_str


def validate_key(key, sign=False, encrypt=False):
    if key.revoked:
        raise GPGProblem("The key \"" + key.uids[0].uid + "\" is revoked.",
                         code=GPGCode.KEY_REVOKED)
    elif key.expired:
        raise GPGProblem("The key \"" + key.uids[0].uid + "\" is expired.",
                         code=GPGCode.KEY_EXPIRED)
    elif key.invalid:
        raise GPGProblem("The key \"" + key.uids[0].uid + "\" is invalid.",
                         code=GPGCode.KEY_INVALID)
    if encrypt and not key.can_encrypt:
        raise GPGProblem("The key \"" + key.uids[0].uid + "\" can not " +
                         "encrypt.", code=GPGCode.KEY_CANNOT_ENCRYPT)
    if sign and not key.can_sign:
        raise GPGProblem("The key \"" + key.uids[0].uid + "\" can not sign.",
                         code=GPGCode.KEY_CANNOT_SIGN)
