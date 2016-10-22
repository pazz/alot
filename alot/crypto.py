# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os

from cStringIO import StringIO
from alot.errors import GPGProblem, GPGCode
import gpgme


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


def get_key(keyid, validate=False, encrypt=False, sign=False,
            signed_only=False):
    """
    Gets a key from the keyring by filtering for the specified keyid, but
    only if the given keyid is specific enough (if it matches multiple
    keys, an exception will be thrown).

    If validate is True also make sure that returned key is not invalid,
    revoked or expired. In addition if encrypt or sign is True also validate
    that key is valid for that action. For example only keys with private key
    can sign. If signed_only is True make sure that the user id can be trusted
    to belong to the key (is signed). This last check will only work if the
    keyid is part of the user id associated with the key, not if it is part of
    the key fingerprint.

    :param keyid: filter term for the keyring (usually a key ID)
    :type keyid: str
    :param validate: validate that returned keyid is valid
    :type validate: bool
    :param encrypt: when validating confirm that returned key can encrypt
    :type encrypt: bool
    :param sign: when validating confirm that returned key can sign
    :type sign: bool
    :param signed_only: only return keys  whose uid is signed (trusted to
        belong to the key)
    :type signed_only: bool
    :rtype: gpgme.Key
    """
    ctx = gpgme.Context()
    try:
        key = ctx.get_key(keyid)
        if validate:
            validate_key(key, encrypt=encrypt, sign=sign)
    except gpgme.GpgmeError as e:
        if e.code == gpgme.ERR_AMBIGUOUS_NAME:
            # When we get here it means there were multiple keys returned by
            # gpg for given keyid. Unfortunately gpgme returns invalid and
            # expired keys together with valid keys. If only one key is valid
            # for given operation maybe we can still return it instead of
            # raising exception
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
                    # another? We really received an ambiguous keyid
                    raise GPGProblem(("More than one key found matching " +
                                      "this filter. Please be more " +
                                      "specific (use a key ID like " +
                                      "4AC8EE1D)."),
                                     code=GPGCode.AMBIGUOUS_NAME)
                valid_key = k

            if not valid_key:
                # there were multiple keys found but none of them are valid for
                # given action (we don't have private key, they are expired
                # etc)
                raise GPGProblem(
                    "Can not find usable key for \'" +
                    keyid +
                    "\'.",
                    code=GPGCode.NOT_FOUND)
            return valid_key
        elif e.code == gpgme.ERR_INV_VALUE or e.code == gpgme.ERR_EOF:
            raise GPGProblem("Can not find key for \'" + keyid + "\'.",
                             code=GPGCode.NOT_FOUND)
        else:
            raise e
    if signed_only and not check_uid_validity(key, keyid):
        raise GPGProblem("Can not find a trusworthy key for '" + keyid + "'.",
                         code=GPGCode.NOT_FOUND)
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
    and can be removed if the missing feature is added to pygpgme.

    :param key: the key we want a hash of
    :type key: gpgme.Key
    :returns: a hash of the key
    :rtype: str
    """
    hash_str = ""
    for tmp_key in key.subkeys:
        hash_str += tmp_key.keyid
    return hash_str


def validate_key(key, sign=False, encrypt=False):
    """Assert that a key is valide and optionally that it can be used for
    signing or encrypting.  Raise GPGProblem otherwise.

    :param key: the GPG key to check
    :type key: gpgme.Key
    :param sign: whether the key should be able to sign
    :type sign: bool
    :param encrypt: whether the key should be able to encrypt
    :type encrypt: bool

    """
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


def check_uid_validity(key, email):
    """Check that a the email belongs to the given key.  Also check the trust
    level of this connection.  Only if the trust level is high enough (>=4) the
    email is assumed to belong to the key.

    :param key: the GPG key to which the email should belong
    :type key: gpgme.Key
    :param email: the email address that should belong to the key
    :type email: str
    :returns: whether the key can be assumed to belong to the given email
    :rtype: bool

    """
    for key_uid in key.uids:
        if email == key_uid.email and not key_uid.revoked and \
                not key_uid.invalid and key_uid.validity >= 4:
            return True
    return False
