# Copyright (C) 2015  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from twisted.internet.defer import inlineCallbacks, returnValue

from ..errors import GPGProblem, GPGCode
from .. import crypto


@inlineCallbacks
def get_keys(ui, encrypt_keyids, block_error=False, signed_only=False):
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
    :returns: the available keys indexed by their key hash
    :rtype: dict(str->gpgme.Key)

    """
    keys = {}
    for keyid in encrypt_keyids:
        try:
            key = crypto.get_key(keyid, validate=True, encrypt=True,
                                 signed_only=signed_only)
        except GPGProblem as e:
            if e.code == GPGCode.AMBIGUOUS_NAME:
                tmp_choices = (k.uids[0].uid for k in
                               crypto.list_keys(hint=keyid))
                choices = {str(i): t for i, t in
                           enumerate(reversed(tmp_choices), 1)}
                keyid = yield ui.choice("ambiguous keyid! Which " +
                                        "key do you want to use?",
                                        choices, cancel=None)
                if keyid:
                    encrypt_keyids.append(keyid)
                continue
            else:
                ui.notify(e.message, priority='error', block=block_error)
                continue
        keys[crypto.hash_key(key)] = key
    returnValue(keys)
