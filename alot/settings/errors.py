# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file


class ConfigError(Exception):
    """could not parse user config"""
    pass


class NoMatchingAccount(ConfigError):
    """No account matching requirements found."""
    pass


class NoMailcapEntry(ConfigError):
    """No mailcap entry found."""
    def __init__(self, ctype):

        msg = "Could not render content of type \"{}\" " \
              "due to a missing mailcap entry.".format(ctype)
        if ctype == 'text/html':
            msg += " Please check out item 5 in our FAQ."

        super(NoMailcapEntry, self).__init__(msg)
