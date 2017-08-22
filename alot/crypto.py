# encoding=utf-8
# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2017 Dylan Baker <dylan@pnwbakers.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import gpg

from .errors import GPGProblem, GPGCode


def RFC3156_micalg_from_algo(hash_algo):
    """
    Converts a GPGME hash algorithm name to one conforming to RFC3156.

    GPGME returns hash algorithm names such as "SHA256", but RFC3156 says that
    programs need to use names such as "pgp-sha256" instead.

    :param str hash_algo: GPGME hash_algo
    :returns: the lowercase name of of the algorithm with "pgp-" prepended
    :rtype: str
    """
    # hash_algo will be something like SHA256, but we need pgp-sha256.
    algo = gpg.core.hash_algo_name(hash_algo)
    if algo is None:
        raise GPGProblem('Unknown hash algorithm {}'.format(algo),
                         code=GPGCode.INVALID_HASH_ALGORITHM)
    return 'pgp-' + algo.lower()


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
    :returns: A gpg key matching the given parameters
    :rtype: gpg.gpgme._gpgme_key
    :raises ~alot.errors.GPGProblem: if the keyid is ambiguous
    :raises ~alot.errors.GPGProblem: if there is no key that matches the
        parameters
    :raises ~alot.errors.GPGProblem: if a key is found, but signed_only is true
        and the key is unused
    """
    ctx = gpg.core.Context()
    try:
        key = ctx.get_key(keyid)
        if validate:
            validate_key(key, encrypt=encrypt, sign=sign)
    except gpg.errors.KeyNotFound:
        raise GPGProblem('Cannot find key for "{}".'.format(keyid),
                         code=GPGCode.NOT_FOUND)
    except gpg.errors.GPGMEError as e:
        if e.getcode() == gpg.errors.AMBIGUOUS_NAME:
            # When we get here it means there were multiple keys returned by
            # gpg for given keyid. Unfortunately gpgme returns invalid and
            # expired keys together with valid keys. If only one key is valid
            # for given operation maybe we can still return it instead of
            # raising exception

            valid_key = None

            for k in list_keys(hint=keyid):
                try:
                    validate_key(k, encrypt=encrypt, sign=sign)
                except GPGProblem:
                    # if the key is invalid for given action skip it
                    continue

                if valid_key:
                    # we have already found one valid key and now we find
                    # another? We really received an ambiguous keyid
                    raise GPGProblem(
                        "More than one key found matching this filter. "
                        "Please be more specific "
                        "(use a key ID like 4AC8EE1D).",
                        code=GPGCode.AMBIGUOUS_NAME)
                valid_key = k

            if not valid_key:
                # there were multiple keys found but none of them are valid for
                # given action (we don't have private key, they are expired
                # etc), or there was no key at all
                raise GPGProblem(
                    'Can not find usable key for "{}".'.format(keyid),
                    code=GPGCode.NOT_FOUND)
            return valid_key
        elif e.getcode() == gpg.errors.INV_VALUE:
            raise GPGProblem(
                'Can not find usable key for "{}".'.format(keyid),
                code=GPGCode.NOT_FOUND)
        else:
            raise e  # pragma: nocover
    if signed_only and not check_uid_validity(key, keyid):
        raise GPGProblem('Cannot find a trusworthy key for "{}".'.format(keyid),
                         code=GPGCode.NOT_FOUND)
    return key


def list_keys(hint=None, private=False):
    """
    Returns a generator of all keys containing the fingerprint, or all keys if
    hint is None.

    The generator may raise exceptions of :class:gpg.errors.GPGMEError, and it
    is the caller's responsibility to handle them.

    :param hint: Part of a fingerprint to usee to search
    :type hint: str or None
    :param private: Whether to return public keys or secret keys
    :type private: bool
    :returns: A generator that yields keys.
    :rtype: Generator[gpg.gpgme.gpgme_key_t, None, None]
    """
    ctx = gpg.core.Context()
    return ctx.keylist(hint, private)


def detached_signature_for(plaintext_str, keys):
    """
    Signs the given plaintext string and returns the detached signature.

    A detached signature in GPG speak is a separate blob of data containing
    a signature for the specified plaintext.

    :param str plaintext_str: text to sign
    :param keys: list of one or more key to sign with.
    :type keys: list[gpg.gpgme._gpgme_key]
    :returns: A list of signature and the signed blob of data
    :rtype: tuple[list[gpg.results.NewSignature], str]
    """
    ctx = gpg.core.Context(armor=True)
    ctx.signers = keys
    (sigblob, sign_result) = ctx.sign(plaintext_str, mode=gpg.constants.SIG_MODE_DETACH)
    return sign_result.signatures, sigblob


def encrypt(plaintext_str, keys=None):
    """Encrypt data and return the encrypted form.

    :param str plaintext_str: the mail to encrypt
    :param key: optionally, a list of keys to encrypt with
    :type key: list[gpg.gpgme.gpgme_key_t] or None
    :returns: encrypted mail
    :rtype: str
    """
    ctx = gpg.core.Context(armor=True)
    out = ctx.encrypt(plaintext_str, recipients=keys, sign=False,
                      always_trust=True)[0]
    return out


def verify_detached(message, signature):
    """Verifies whether the message is authentic by checking the signature.

    :param str message: The message to be verified, in canonical form.
    :param str signature: the OpenPGP signature to verify
    :returns: a list of signatures
    :rtype: list[gpg.results.Signature]
    :raises: :class:`~alot.errors.GPGProblem` if the verification fails
    """
    ctx = gpg.core.Context()
    try:
        verify_results = ctx.verify(message, signature)[1]
        return verify_results.signatures
    except gpg.errors.BadSignatures as e:
        raise GPGProblem(str(e), code=GPGCode.BAD_SIGNATURE)
    except gpg.errors.GPGMEError as e:
        raise GPGProblem(str(e), code=e.getcode())


def decrypt_verify(encrypted):
    """Decrypts the given ciphertext string and returns both the
    signatures (if any) and the plaintext.

    :param str encrypted: the mail to decrypt
    :returns: the signatures and decrypted plaintext data
    :rtype: tuple[list[gpg.resuit.Signature], str]
    :raises: :class:`~alot.errors.GPGProblem` if the decryption fails
    """
    ctx = gpg.core.Context()
    try:
        (plaintext, _, verify_result) = ctx.decrypt(encrypted, verify=True)
    except gpg.errors.GPGMEError as e:
        raise GPGProblem(str(e), code=e.getcode())
    # what if the signature is bad?

    return verify_result.signatures, plaintext


def validate_key(key, sign=False, encrypt=False):
    """Assert that a key is valide and optionally that it can be used for
    signing or encrypting.  Raise GPGProblem otherwise.

    :param key: the GPG key to check
    :type key: gpg.gpgme._gpgme_key
    :param sign: whether the key should be able to sign
    :type sign: bool
    :param encrypt: whether the key should be able to encrypt
    :type encrypt: bool
    :raises ~alot.errors.GPGProblem: If the key is revoked, expired, or invalid
    :raises ~alot.errors.GPGProblem: If encrypt is true and the key cannot be
        used to encrypt
    :raises ~alot.errors.GPGProblem: If sign is true and th key cannot be used
        to encrypt
    """
    if key.revoked:
        raise GPGProblem('The key "{}" is revoked.'.format(key.uids[0].uid),
                         code=GPGCode.KEY_REVOKED)
    elif key.expired:
        raise GPGProblem('The key "{}" is expired.'.format(key.uids[0].uid),
                         code=GPGCode.KEY_EXPIRED)
    elif key.invalid:
        raise GPGProblem('The key "{}" is invalid.'.format(key.uids[0].uid),
                         code=GPGCode.KEY_INVALID)
    if encrypt and not key.can_encrypt:
        raise GPGProblem(
            'The key "{}" cannot be used to encrypt'.format(key.uids[0].uid),
            code=GPGCode.KEY_CANNOT_ENCRYPT)
    if sign and not key.can_sign:
        raise GPGProblem(
            'The key "{}" cannot be used to sign'.format(key.uids[0].uid),
            code=GPGCode.KEY_CANNOT_SIGN)


def check_uid_validity(key, email):
    """Check that a the email belongs to the given key.  Also check the trust
    level of this connection.  Only if the trust level is high enough (>=4) the
    email is assumed to belong to the key.

    :param key: the GPG key to which the email should belong
    :type key: gpg.gpgme._gpgme_key
    :param email: the email address that should belong to the key
    :type email: str
    :returns: whether the key can be assumed to belong to the given email
    :rtype: bool
    """
    def check(key_uid):
        return (email == key_uid.email and
                not key_uid.revoked and
                not key_uid.invalid and
                key_uid.validity >= gpg.constants.validity.FULL)

    return any(check(u) for u in key.uids)
