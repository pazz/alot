# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from typing import Any


class GPGCode:
    AMBIGUOUS_NAME: int = 1
    NOT_FOUND: int = 2
    BAD_PASSPHRASE: int = 3
    KEY_REVOKED: int = 4
    KEY_EXPIRED: int = 5
    KEY_INVALID: int = 6
    KEY_CANNOT_ENCRYPT: int = 7
    KEY_CANNOT_SIGN: int = 8
    INVALID_HASH: int = 9
    INVALID_HASH_ALGORITHM: int = 10
    BAD_SIGNATURE: int = 11


class GPGProblem(Exception):
    """GPG Error"""

    def __init__(self, message: str, code: int) -> None:
        self.code = code
        super(GPGProblem, self).__init__(message)


class CompletionError(Exception):
    pass


class ConversionError(Exception):
    pass
