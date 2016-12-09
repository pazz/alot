# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import imp
import os
import re
import mailcap
import logging
from configobj import ConfigObj, Section

from ..account import SendmailAccount
from ..addressbook.abook import AbookAddressBook
from ..addressbook.external import ExternalAddressbook
from ..helper import pretty_datetime, string_decode

from .errors import ConfigError
from .utils import read_config
from .utils import resolve_att
from .checks import force_list
from .checks import mail_container
from .checks import gpg_key
from .checks import attr_triple
from .checks import align_mode
from .theme import Theme


DEFAULTSPATH = os.path.join(os.path.dirname(__file__), '..', 'defaults')


class SettingsManager(object):
    """Organizes user settings"""
    def __init__(self, alot_rc=None, notmuch_rc=None):
        """
        :param alot_rc: path to alot's config file
        :type alot_rc: str
        :param notmuch_rc: path to notmuch's config file
        :type notmuch_rc: str
        """
        self.hooks = None
        self._mailcaps = mailcap.getcaps()
        self._config = ConfigObj()
        self._notmuchconfig = None
        self._theme = None
        self._accounts = None
        self._accountmap = None
        bindings_path = os.path.join(DEFAULTSPATH, 'default.bindings')
        self._bindings = ConfigObj(bindings_path)
        if alot_rc is not None:
            self.read_config(alot_rc)
        if notmuch_rc is not None:
            self.read_notmuch_config(notmuch_rc)

    def read_notmuch_config(self, path):
        """parse notmuch's config file from path"""
        spec = os.path.join(DEFAULTSPATH, 'notmuch.rc.spec')
        self._notmuchconfig = read_config(path, spec)

    def read_config(self, path):
        """parse alot's config file from path"""
        spec = os.path.join(DEFAULTSPATH, 'alot.rc.spec')
        newconfig = read_config(path, spec,
                                checks={'mail_container': mail_container,
                                        'force_list': force_list,
                                        'align': align_mode,
                                        'attrtriple': attr_triple,
                                        'gpg_key_hint': gpg_key})
        self._config.merge(newconfig)

        hooks_path = os.path.expanduser(self._config.get('hooksfile'))
        try:
            self.hooks = imp.load_source('hooks', hooks_path)
        except:
            logging.debug('unable to load hooks file:%s', hooks_path)
        if 'bindings' in newconfig:
            newbindings = newconfig['bindings']
            if isinstance(newbindings, Section):
                self._bindings.merge(newbindings)
        # themes
        themestring = newconfig['theme']
        themes_dir = self._config.get('themes_dir')
        if themes_dir:
            themes_dir = os.path.expanduser(themes_dir)
        else:
            configdir = os.environ.get('XDG_CONFIG_HOME',
                                       os.path.expanduser('~/.config'))
            themes_dir = os.path.join(configdir, 'alot', 'themes')
        logging.debug(themes_dir)

        # if config contains theme string use that
        if themestring:
            if not os.path.isdir(themes_dir):
                err_msg = 'cannot find theme %s: themes_dir %s is missing'
                raise ConfigError(err_msg % (themestring, themes_dir))
            else:
                theme_path = os.path.join(themes_dir, themestring)
                try:
                    self._theme = Theme(theme_path)
                except ConfigError as e:
                    err_msg = 'Theme file %s failed validation:\n'
                    raise ConfigError((err_msg % themestring) + str(e.message))

        # if still no theme is set, resort to default
        if self._theme is None:
            theme_path = os.path.join(DEFAULTSPATH, 'default.theme')
            self._theme = Theme(theme_path)

        self._accounts = self._parse_accounts(self._config)
        self._accountmap = self._account_table(self._accounts)

    def _parse_accounts(self, config):
        """
        read accounts information from config

        :param config: valit alot config
        :type config: `configobj.ConfigObj`
        :returns: list of accounts
        """
        accounts = []
        if 'accounts' in config:
            for acc in config['accounts'].sections:
                accsec = config['accounts'][acc]
                args = dict(config['accounts'][acc])

                # create abook for this account
                abook = accsec['abook']
                logging.debug('abook defined: %s', abook)
                if abook['type'] == 'shellcommand':
                    cmd = abook['command']
                    regexp = abook['regexp']
                    if cmd is not None and regexp is not None:
                        ef = abook['shellcommand_external_filtering']
                        args['abook'] = ExternalAddressbook(
                            cmd, regexp, external_filtering=ef)
                    else:
                        msg = 'underspecified abook of type \'shellcommand\':'
                        msg += '\ncommand: %s\nregexp:%s' % (cmd, regexp)
                        raise ConfigError(msg)
                elif abook['type'] == 'abook':
                    contacts_path = abook['abook_contacts_file']
                    args['abook'] = AbookAddressBook(
                        contacts_path, ignorecase=abook['ignorecase'])
                else:
                    del args['abook']

                cmd = args['sendmail_command']
                del args['sendmail_command']
                newacc = SendmailAccount(cmd, **args)
                accounts.append(newacc)
        return accounts

    def _account_table(self, accounts):
        """
        creates a lookup table (emailaddress -> account) for a given list of
        accounts

        :param accounts: list of accounts
        :type accounts: list of `alot.account.Account`
        :returns: hashtable
        :rvalue: dict (str -> `alot.account.Account`)
        """
        accountmap = {}
        for acc in accounts:
            accountmap[acc.address] = acc
            for alias in acc.aliases:
                accountmap[alias] = acc
        return accountmap

    def get(self, key, fallback=None):
        """
        look up global config values from alot's config

        :param key: key to look up
        :type key: str
        :param fallback: fallback returned if key is not present
        :type fallback: str
        :returns: config value with type as specified in the spec-file
        """
        value = None
        if key in self._config:
            value = self._config[key]
            if isinstance(value, Section):
                value = None
        if value is None:
            value = fallback
        return value

    def set(self, key, value):
        """
        setter for global config values

        :param key: config option identifise
        :type key: str
        :param value: option to set
        :type value: depends on the specfile :file:`alot.rc.spec`
        """
        self._config[key] = value

    def get_notmuch_setting(self, section, key, fallback=None):
        """
        look up config values from notmuch's config

        :param section: key is in
        :type section: str
        :param key: key to look up
        :type key: str
        :param fallback: fallback returned if key is not present
        :type fallback: str
        :returns: config value with type as specified in the spec-file
        """
        value = None
        if section in self._notmuchconfig:
            if key in self._notmuchconfig[section]:
                value = self._notmuchconfig[section][key]
        if value is None:
            value = fallback
        return value

    def get_theming_attribute(self, mode, name, part=None):
        """
        looks up theming attribute

        :param mode: ui-mode (e.g. `search`,`thread`...)
        :type mode: str
        :param name: identifier of the atttribute
        :type name: str
        :rtype: urwid.AttrSpec
        """
        colours = int(self._config.get('colourmode'))
        return self._theme.get_attribute(colours, mode, name, part)

    def get_threadline_theming(self, thread):
        """
        looks up theming info a threadline displaying a given thread. This
        wraps around :meth:`~alot.settings.theme.Theme.get_threadline_theming`,
        filling in the current colour mode.

        :param thread: thread to theme
        :type thread: alot.db.thread.Thread
        """
        colours = int(self._config.get('colourmode'))
        return self._theme.get_threadline_theming(thread, colours)

    def get_tagstring_representation(self, tag, onebelow_normal=None,
                                     onebelow_focus=None):
        """
        looks up user's preferred way to represent a given tagstring.

        :param tag: tagstring
        :type tag: str
        :param onebelow_normal: attribute that shines through if unfocussed
        :type onebelow_normal: urwid.AttrSpec
        :param onebelow_focus: attribute that shines through if focussed
        :type onebelow_focus: urwid.AttrSpec

        If `onebelow_normal` or `onebelow_focus` is given these attributes will
        be used as fallbacks for fg/bg values '' and 'default'.

        This returns a dictionary mapping
            :normal: to :class:`urwid.AttrSpec` used if unfocussed
            :focussed: to :class:`urwid.AttrSpec` used if focussed
            :translated: to an alternative string representation
        """
        colourmode = int(self._config.get('colourmode'))
        theme = self._theme
        cfg = self._config
        colours = [1, 16, 256]

        def colourpick(triple):
            """ pick attribute from triple (mono,16c,256c) according to current
            colourmode"""
            if triple is None:
                return None
            return triple[colours.index(colourmode)]

        # global default attributes for tagstrings.
        # These could contain values '' and 'default' which we interpret as
        # "use the values from the widget below"
        default_normal = theme.get_attribute(colourmode, 'global', 'tag')
        default_focus = theme.get_attribute(colourmode, 'global', 'tag_focus')

        # local defaults for tagstring attributes. depend on next lower widget
        fallback_normal = resolve_att(onebelow_normal, default_normal)
        fallback_focus = resolve_att(onebelow_focus, default_focus)

        for sec in cfg['tags'].sections:
            if re.match('^' + sec + '$', tag):
                normal = resolve_att(colourpick(cfg['tags'][sec]['normal']),
                                     fallback_normal)
                focus = resolve_att(colourpick(cfg['tags'][sec]['focus']),
                                    fallback_focus)

                translated = cfg['tags'][sec]['translated']
                translated = string_decode(translated, 'UTF-8')
                if translated is None:
                    translated = tag
                translation = cfg['tags'][sec]['translation']
                if translation:
                    translated = re.sub(translation[0], translation[1], tag)
                break
        else:
            normal = fallback_normal
            focus = fallback_focus
            translated = tag

        return {'normal': normal, 'focussed': focus, 'translated': translated}

    def get_hook(self, key):
        """return hook (`callable`) identified by `key`"""
        if self.hooks:
            if key in self.hooks.__dict__:
                return self.hooks.__dict__[key]
        return None

    def get_mapped_input_keysequences(self, mode='global', prefix=u''):
        # get all bindings in this mode
        globalmaps, modemaps = self.get_keybindings(mode)
        candidates = globalmaps.keys() + modemaps.keys()
        if prefix is not None:
            prefixs = prefix + ' '
            cand = filter(lambda x: x.startswith(prefixs), candidates)
            if prefix in candidates:
                candidates = cand + [prefix]
            else:
                candidates = cand
        return candidates

    def get_keybindings(self, mode):
        """look up keybindings from `MODE-maps` sections

        :param mode: mode identifier
        :type mode: str
        :returns: dictionaries of key-cmd for global and specific mode
        :rtype: 2-tuple of dicts
        """
        globalmaps, modemaps = {}, {}
        bindings = self._bindings
        # get bindings for mode `mode`
        # retain empty assignations to silence corresponding global mappings
        if mode in bindings.sections:
            for key in bindings[mode].scalars:
                value = bindings[mode][key]
                if isinstance(value, list):
                    value = ','.join(value)
                modemaps[key] = value
        # get global bindings
        # ignore the ones already mapped in mode bindings
        for key in bindings.scalars:
            if key not in modemaps:
                value = bindings[key]
                if isinstance(value, list):
                    value = ','.join(value)
                if value and value != '':
                    globalmaps[key] = value
        # get rid of empty commands left in mode bindings
        for key in [k for k, v in modemaps.items() if not v or v == '']:
            del modemaps[key]

        return globalmaps, modemaps

    def get_keybinding(self, mode, key):
        """look up keybinding from `MODE-maps` sections

        :param mode: mode identifier
        :type mode: str
        :param key: urwid-style key identifier
        :type key: str
        :returns: a command line to be applied upon keypress
        :rtype: str
        """
        cmdline = None
        bindings = self._bindings
        if key in bindings.scalars:
            cmdline = bindings[key]
        if mode in bindings.sections:
            if key in bindings[mode].scalars:
                value = bindings[mode][key]
                if value:
                    cmdline = value
                else:
                    # to be sure it isn't mapped globally
                    cmdline = None
        # Workaround for ConfigObj misbehaviour. cf issue #500
        # this ensures that we get at least strings only as commandlines
        if isinstance(cmdline, list):
            cmdline = ','.join(cmdline)
        return cmdline

    def get_accounts(self):
        """
        returns known accounts

        :rtype: list of :class:`Account`
        """
        return self._accounts

    def get_account_by_address(self, address):
        """
        returns :class:`Account` for a given email address (str)

        :param address: address to look up
        :type address: string
        :rtype:  :class:`Account` or None
        """

        for myad in self.get_addresses():
            if myad in address:
                return self._accountmap[myad]
        return None

    def get_main_addresses(self):
        """returns addresses of known accounts without its aliases"""
        return [a.address for a in self._accounts]

    def get_addresses(self):
        """returns addresses of known accounts including all their aliases"""
        return self._accountmap.keys()

    def get_addressbooks(self, order=[], append_remaining=True):
        """returns list of all defined :class:`AddressBook` objects"""
        abooks = []
        for a in order:
            if a:
                if a.abook:
                    abooks.append(a.abook)
        if append_remaining:
            for a in self._accounts:
                if a.abook and a.abook not in abooks:
                    abooks.append(a.abook)
        return abooks

    def mailcap_find_match(self, *args, **kwargs):
        """
        Propagates :func:`mailcap.find_match` but caches the mailcap (first
        argument)
        """
        return mailcap.findmatch(self._mailcaps, *args, **kwargs)

    def represent_datetime(self, d):
        """
        turns a given datetime obj into a unicode string representation.
        This will:

        1) look if a fixed 'timestamp_format' is given in the config
        2) check if a 'timestamp_format' hook is defined
        3) use :func:`~alot.helper.pretty_datetime` as fallback
        """

        fixed_format = self.get('timestamp_format')
        if fixed_format:
            rep = string_decode(d.strftime(fixed_format), 'UTF-8')
        else:
            format_hook = self.get_hook('timestamp_format')
            if format_hook:
                rep = string_decode(format_hook(d), 'UTF-8')
            else:
                rep = pretty_datetime(d)
        return rep
