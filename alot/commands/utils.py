# Copyright (C) 2015  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import re
import logging

from twisted.internet.defer import inlineCallbacks, returnValue

from ..errors import GPGProblem, GPGCode
from ..settings.const import settings
from ..settings.errors import NoMatchingAccount
from .. import crypto


@inlineCallbacks
def set_encrypt(ui, envelope, block_error=False, signed_only=False):
    """Find and set the encryption keys in an envolope.

    :param ui: the main user interface object
    :type ui: alot.ui.UI
    :param envolope: the envolope buffer object
    :type envolope: alot.buffers.EnvelopeBuffer
    :param block_error: wether error messages for the user should expire
        automatically or block the ui
    :type block_error: bool
    :param signed_only: only use keys whose uid is signed (trusted to belong
        to the key)
    :type signed_only: bool
    """
    encrypt_keys = []
    for header in ('To', 'Cc'):
        if header not in envelope.headers:
            continue

        for recipient in envelope.headers[header][0].split(','):
            if not recipient:
                continue
            match = re.search("<(.*@.*)>", recipient)
            if match:
                recipient = match.group(1)
            encrypt_keys.append(recipient)

    logging.debug("encryption keys: " + str(encrypt_keys))
    keys = yield _get_keys(ui, encrypt_keys, block_error=block_error,
                           signed_only=signed_only)
    if keys:
        envelope.encrypt_keys = keys
        envelope.encrypt = True

        if 'From' in envelope.headers:
            try:
                acc = settings.get_account_by_address(envelope['From'])
                if acc.encrypt_to_self:
                    if acc.gpg_key:
                        logging.debug('encrypt to self: %s', acc.gpg_key.fpr)
                        envelope.encrypt_keys[acc.gpg_key.fpr] = acc.gpg_key
                    else:
                        logging.debug('encrypt to self: no gpg_key in account')
            except NoMatchingAccount:
                logging.debug('encrypt to self: no account found')

    else:
        envelope.encrypt = False


@inlineCallbacks
def _get_keys(ui, encrypt_keyids, block_error=False, signed_only=False):
    """Get several keys from the GPG keyring.  The keys are selected by keyid
    and are checked if they can be used for encryption.

    :param ui: the main user interface object
    :type ui: alot.ui.UI
    :param encrypt_keyids: the key ids of the keys to get
    :type encrypt_keyids: list(str)
    :param block_error: wether error messages for the user should expire
        automatically or block the ui
    :type block_error: bool
    :param signed_only: only return keys whose uid is signed (trusted to belong
        to the key)
    :type signed_only: bool
    :returns: the available keys indexed by their OpenPGP fingerprint
    :rtype: dict(str->gpg key object)
    """
    keys = {}
    for keyid in encrypt_keyids:
        try:
            key = crypto.get_key(keyid, validate=True, encrypt=True,
                                 signed_only=signed_only)
        except GPGProblem as e:
            if e.code == GPGCode.AMBIGUOUS_NAME:
                tmp_choices = ['{} ({})'.format(k.uids[0].uid, k.fpr) for k in
                               crypto.list_keys(hint=keyid)]
                choices = {str(i): t for i, t in enumerate(tmp_choices, 1)}
                keys_to_return = {str(i): t for i, t in enumerate([k for k in
                                  crypto.list_keys(hint=keyid)], 1)}
                choosen_key = yield ui.choice("ambiguous keyid! Which " +
                                              "key do you want to use?",
                                              choices=choices,
                                              choices_to_return=keys_to_return)
                if choosen_key:
                    keys[choosen_key.fpr] = choosen_key
                continue
            else:
                ui.notify(str(e), priority='error', block=block_error)
                continue
        keys[key.fpr] = key
    returnValue(keys)
