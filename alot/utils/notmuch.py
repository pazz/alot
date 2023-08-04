# encoding=utf-8

# SPDX-FileCopyrightText: 2020 Kirill Elagin <https://kir.elagin.me/>
# SPDX-License-Identifier: GPL-3.0-or-later

from os import environ
import os.path


# Replicate the logic for locating the notmuch database:
#
# * Can be absolute or relative to $HOME.
# * Default: $MAILDIR variable if set, otherwise $HOME/mail.
def find_db(settings):
    path_from_settings = settings.get_notmuch_setting('database', 'path')
    if path_from_settings is None:
        maildir = environ.get('MAILDIR')
        if maildir is not None:
            return maildir
        else:
            return os.path.join(environ.get('HOME'), 'mail')
    else:
        if not os.path.isabs(path_from_settings):
            return os.path.join(environ.get('HOME'), path_from_settings)
        else:
            return path_from_settings
