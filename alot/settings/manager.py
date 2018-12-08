# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import importlib.util
import itertools
import logging
import mailcap
import os
import re
import email
from configobj import ConfigObj, Section

from ..account import SendmailAccount
from ..addressbook.abook import AbookAddressBook
from ..addressbook.external import ExternalAddressbook
from ..helper import pretty_datetime, string_decode, get_xdg_env
from ..utils import configobj as checks

from .errors import ConfigError, NoMatchingAccount
from .utils import read_config
from .utils import resolve_att
from .theme import Theme


DEFAULTSPATH = os.path.join(os.path.dirname(__file__), '..', 'defaults')
DATA_DIRS = get_xdg_env('XDG_DATA_DIRS',
                        '/usr/local/share:/usr/share').split(':')


class SettingsManager(object):
    """Organizes user settings"""
    def __init__(self):
        self.hooks = None
        self._mailcaps = mailcap.getcaps()
        self._notmuchconfig = None
        self._theme = None
        self._accounts = None
        self._accountmap = None
        self._notmuchconfig = None
        self._config = ConfigObj()
        self._bindings = None

    def reload(self):
        """Reload notmuch and alot config files"""
        self.read_notmuch_config(self._notmuchconfig.filename)
        self.read_config(self._config.filename)

    def read_notmuch_config(self, path):
        """
        parse notmuch's config file
        :param path: path to notmuch's config file
        :type path: str
        """
        spec = os.path.join(DEFAULTSPATH, 'notmuch.rc.spec')
        self._notmuchconfig = read_config(path, spec)

    def _update_bindings(self, newbindings):
        assert isinstance(newbindings, Section)

        self._bindings = ConfigObj(os.path.join(DEFAULTSPATH,
                                                'default.bindings'))
        self._bindings.merge(newbindings)

    def read_config(self, path):
        """
        parse alot's config file
        :param path: path to alot's config file
        :type path: str
        """
        spec = os.path.join(DEFAULTSPATH, 'alot.rc.spec')
        newconfig = read_config(path, spec, report_extra=True, checks={
                'mail_container': checks.mail_container,
                'force_list': checks.force_list,
                'align': checks.align_mode,
                'attrtriple': checks.attr_triple,
                'gpg_key_hint': checks.gpg_key})
        self._config.merge(newconfig)
        self._config.walk(self._expand_config_values)

        hooks_path = os.path.expanduser(self._config.get('hooksfile'))
        try:
            spec = importlib.util.spec_from_file_location('hooks', hooks_path)
            self.hooks = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.hooks)
        except:
            logging.exception('unable to load hooks file:%s', hooks_path)
        if 'bindings' in newconfig:
            self._update_bindings(newconfig['bindings'])

        tempdir = self._config.get('template_dir')
        logging.debug('template directory: `%s`' % tempdir)

        # themes
        themestring = newconfig['theme']
        themes_dir = self._config.get('themes_dir')
        logging.debug('themes directory: `%s`' % themes_dir)

        # if config contains theme string use that
        data_dirs = [os.path.join(d, 'alot/themes') for d in DATA_DIRS]
        if themestring:
            # This is a python for/else loop
            # https://docs.python.org/3/reference/compound_stmts.html#for
            #
            # tl/dr; If the loop loads a theme it breaks. If it doesn't break,
            # then it raises a ConfigError.
            for dir_ in itertools.chain([themes_dir], data_dirs):
                theme_path = os.path.join(dir_, themestring)
                if not os.path.exists(os.path.expanduser(theme_path)):
                    logging.warning('Theme `%s` does not exist.', theme_path)
                else:
                    try:
                        self._theme = Theme(theme_path)
                    except ConfigError as e:
                        raise ConfigError('Theme file `%s` failed '
                                          'validation:\n%s' % (theme_path, e))
                    else:
                        break
            else:
                raise ConfigError('Could not find theme {}, see log for more '
                                  'information'.format(themestring))

        # if still no theme is set, resort to default
        if self._theme is None:
            theme_path = os.path.join(DEFAULTSPATH, 'default.theme')
            self._theme = Theme(theme_path)

        self._accounts = self._parse_accounts(self._config)
        self._accountmap = self._account_table(self._accounts)

    @staticmethod
    def _expand_config_values(section, key):
        """
        Walker function for ConfigObj.walk

        Applies expand_environment_and_home to all configuration values that
        are strings (or strings that are elements of tuples/lists)

        :param section: as passed by ConfigObj.walk
        :param key: as passed by ConfigObj.walk
        """

        def expand_environment_and_home(value):
            """
            Expands environment variables and the home directory (~).

            $FOO and ${FOO}-style environment variables are expanded, if they
            exist. If they do not exist, they are left unchanged.
            The exception are the following $XDG_* variables that are
            expanded to fallback values, if they are empty or not set:
            $XDG_CONFIG_HOME
            $XDG_CACHE_HOME

            :param value: configuration string
            :type value: str
            """
            xdg_vars = {'XDG_CONFIG_HOME': '~/.config',
                        'XDG_CACHE_HOME': '~/.cache'}

            for xdg_name, fallback in xdg_vars.items():
                if xdg_name in value:
                    xdg_value = get_xdg_env(xdg_name, fallback)
                    value = value.replace('$%s' % xdg_name, xdg_value)\
                                 .replace('${%s}' % xdg_name, xdg_value)
            return os.path.expanduser(os.path.expandvars(value))

        value = section[key]

        if isinstance(value, str):
            section[key] = expand_environment_and_home(value)
        elif isinstance(value, (list, tuple)):
            new = list()
            for item in value:
                if isinstance(item, str):
                    new.append(expand_environment_and_home(item))
                else:
                    new.append(item)
            section[key] = new

    @staticmethod
    def _parse_accounts(config):
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
                args = dict(config['accounts'][acc].items())

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

    @staticmethod
    def _account_table(accounts):
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

        :param key: config option identifies
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
            if re.match('^{}$'.format(re.escape(sec)), tag):
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
            return getattr(self.hooks, key, None)
        return None

    def get_mapped_input_keysequences(self, mode='global', prefix=u''):
        # get all bindings in this mode
        globalmaps, modemaps = self.get_keybindings(mode)
        candidates = list(globalmaps.keys()) + list(modemaps.keys())
        if prefix is not None:
            prefixes = prefix + ' '
            cand = [c for c in candidates if c.startswith(prefixes)]
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
        for k, v in list(modemaps.items()):
            if not v:
                del modemaps[k]

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

    def account_matching_address(self, address, return_default=False):
        """returns :class:`Account` for a given email address (str)

        :param str address: address to look up. A realname part will be ignored.
        :param bool return_default: If True and no address can be found, then
            the default account wil be returned.
        :rtype: :class:`Account`
        :raises ~alot.settings.errors.NoMatchingAccount: If no account can be
            found. This includes if return_default is True and there are no
            accounts defined.
        """
        _, address = email.utils.parseaddr(address)
        for account in self.get_accounts():
            if account.matches_address(address):
                return account
        if return_default:
            try:
                return self.get_accounts()[0]
            except IndexError:
                # Fall through
                pass
        raise NoMatchingAccount

    def get_main_addresses(self):
        """returns addresses of known accounts without its aliases"""
        return [a.address for a in self._accounts]

    def get_addressbooks(self, order=None, append_remaining=True):
        """returns list of all defined :class:`AddressBook` objects"""
        order = order or []
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
        turns a given datetime obj into a string representation.
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
