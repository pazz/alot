import imp
import os
import re
import ast
import json
import mailcap
import codecs
import logging
import urwid
from urwid import AttrSpec, AttrSpecError
from configobj import ConfigObj, ConfigObjError, flatten_errors, Section
from validate import Validator

from account import SendmailAccount, MatchSdtoutAddressbook

from collections import OrderedDict
from ConfigParser import SafeConfigParser, ParsingError, NoOptionError

DEFAULTSPATH = os.path.join(os.path.dirname(__file__), 'defaults')


class ConfigError(Exception):
    pass


def read_config(configpath=None, specpath=None):
    """
    get a (validated) config object for given config file path.

    :param configpath: path to config-file
    :type configpath: str
    :param specpath: path to spec-file
    :type specpath: str
    :rtype: `configobj.ConfigObj`
    """
    try:
        config = ConfigObj(infile=configpath, configspec=specpath,
                           file_error=True, encoding='UTF8')
    except (ConfigObjError, IOError), e:
        raise ConfigError('Could not read "%s": %s' % (configpath, e))

    if specpath:
        validator = Validator()
        results = config.validate(validator)

        if results != True:
            error_msg = 'Validation errors occurred:\n'
            for (section_list, key, _) in flatten_errors(config, results):
                if key is not None:
                    msg = 'key "%s" in section "%s" failed validation'
                    msg = msg % (key, ', '.join(section_list))
                else:
                    msg = 'section "%s" is malformed' % ', '.join(section_list)
                error_msg += msg + '\n'
            raise ConfigError(error_msg)
    return config


class Theme(object):
    """Colour theme"""
    def __init__(self, path):
        """
        :param path: path to theme file
        :type path: str
        """
        self._spec = os.path.join(DEFAULTSPATH, 'theme.spec')
        self._config = read_config(path, self._spec)
        self.attributes = self._parse_attributes(self._config)

    def _parse_attributes(self, c):
        """
        parse a (previously validated) valid theme file
        into urwid AttrSpec attributes for internal use.

        :param c: config object for theme file
        :type c: `configobj.ConfigObj`
        :raises: `ConfigError`
        """

        attributes = {}
        for sec in c.sections:
            try:
                colours = int(sec)
            except ValueError:
                err_msg = 'section name %s is not a valid colour mode'
                raise ConfigError(err_msg % sec)
            attributes[colours] = {}
            for mode in c[sec].sections:
                attributes[colours][mode] = {}
                for themable in c[sec][mode].sections:
                    block = c[sec][mode][themable]
                    fg = block['fg']
                    if colours == 1:
                        bg = 'default'
                    else:
                        bg = block['bg']
                    if colours == 256:
                        fg = fg or c['16'][mode][themable][fg]
                        bg = bg or c['16'][mode][themable][bg]
                    try:
                        att = AttrSpec(fg, bg, colours)
                    except AttrSpecError, e:
                        raise ConfigError(e)
                    attributes[colours][mode][themable] = att
        return attributes

    def get_attribute(self, mode, name, colourmode):
        """
        returns requested attribute

        :param mode: ui-mode (e.g. `search`,`thread`...)
        :type mode: str
        :param name: identifier of the atttribute
        :type name: str
        :param colourmode: colour mode; in [1, 16, 256]
        :type colourmode: int
        """
        return self.attributes[colourmode][mode][name]


class SettingsManager(object):
    """Organizes user settings"""
    def __init__(self, alot_rc=None, notmuch_rc=None, theme=None):
        """
        :param alot_rc: path to alot's config file
        :type alot_rc: str
        :param notmuch_rc: path to notmuch's config file
        :type notmuch_rc: str
        :theme: path to initially used theme file
        :type theme: str
        """
        self.hooks = None
        self._mailcaps = mailcap.getcaps()

        theme_path = theme or os.path.join(DEFAULTSPATH, 'default.theme')
        self._theme = Theme(theme_path)
        self._bindings = read_config(os.path.join(DEFAULTSPATH, 'bindings'))

        self._config = ConfigObj()
        self._accounts = None
        self._accountmap = None
        self.read_config(alot_rc)
        self.read_notmuch_config(notmuch_rc)

    def read_notmuch_config(self, path):
        """parse notmuch's config file from path"""
        spec = os.path.join(DEFAULTSPATH, 'notmuch.rc.spec')
        self._notmuchconfig = read_config(path, spec)

    def read_config(self, path):
        """parse alot's config file from path"""
        spec = os.path.join(DEFAULTSPATH, 'alot.rc.spec')
        newconfig = read_config(path, spec)
        self._config.merge(newconfig)

        hooks_path = os.path.expanduser(self._config.get('hooksfile'))
        try:
            self.hooks = imp.load_source('hooks', hooks_path)
        except:
            logging.debug('unable to load hooks file:%s' % hooks_path)
        if 'bindings' in newconfig:
            newbindings = newconfig['bindings']
            if isinstance(newbindings, Section):
                self._bindings.merge(newbindings)

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

                if 'abook_command' in accsec:
                    cmd = accsec['abook_command']
                    regexp = accsec['abook_regexp']
                    args['abook'] = MatchSdtoutAddressbook(cmd, match=regexp)
                    del(args['abook_command'])
                    del(args['abook_regexp'])

                cmd = args['sendmail_command']
                del(args['sendmail_command'])
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

    def get(self, key):
        """
        look up global config values from alot's config

        :param key: key to look up
        :type key: str
        :returns: config value with type as specified in the spec-file
        """
        value = None
        if key in self._config:
            value = self._config[key]
            if isinstance(value, Section):
                value = None
        return value

    def get_notmuch_setting(self, section, key):
        """
        look up config values from notmuch's config

        :param section: key is in
        :type section: str
        :param key: key to look up
        :type key: str
        :returns: config value with type as specified in the spec-file
        """
        value = None
        if key in self._notmuchconfig:
            value = self._notmuchconfig[key]
        return value

    def get_theming_attribute(self, mode, name):
        """
        looks up theming attribute

        :param mode: ui-mode (e.g. `search`,`thread`...)
        :type mode: str
        :param name: identifier of the atttribute
        :type name: str
        """
        colours = int(self._config.get('colourmode'))
        return self._theme.get_attribute(mode, name,  colours)

    def get_tagstring_representation(self, tag):
        """
        looks up user's preferred way to represent a given tagstring

        This returns a dictionary mapping
        'normal' and 'focussed' to `urwid.AttrSpec` sttributes,
        and 'translated' to an alternative string representation
        """
        colours = int(self._config.get('colourmode'))
        # default attributes: normal and focussed
        default = self._theme.get_attribute('global', 'tag', colours)
        default_f = self._theme.get_attribute('global', 'tag_focus', colours)
        if tag in self._config['tags']:
            fg = self._config['tags'][tag]['fg'] or default.foreground
            bg = self._config['tags'][tag]['bg'] or default.background
            normal = urwid.AttrSpec(fg, bg, colours)
            ffg = self._config['tags'][tag]['focus_fg'] or default_f.foreground
            fbg = self._config['tags'][tag]['focus_bg'] or default_f.background
            focussed = urwid.AttrSpec(ffg, fbg, colours)
            translated = self._config['tags'][tag]['translated'] or tag
        else:
            normal = default
            focussed = default_f
            translated = tag

        return {'normal': normal, 'focussed': focussed,
                'translated': translated}

    def get_hook(self, key):
        """return hook (`callable`) identified by `key`"""
        if self.hooks:
            if key in self.hooks.__dict__:
                return self.hooks.__dict__[key]
        return None

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
        if key in bindings[mode]:
            cmdline = bindings[mode][key]
        elif key in bindings['global']:
            cmdline = bindings['global'][key]
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

    def get_mime_handler(self, mime_type, key='view', interactive=True):
        """
        get shellcomand defined in the users `mailcap` as handler for files of
        given `mime_type`.

        :param mime_type: file type
        :type mime_type: str
        :param key: identifies one of possibly many commands for this type by
                    naming the intended usage, e.g. 'edit' or 'view'. Defaults
                    to 'view'.
        :type key: str
        :param interactive: choose the "interactive session" handler rather
                            than the "print to stdout and immediately return"
                            handler
        :type interactive: bool
        """
        if interactive:
            mc_tuple = mailcap.findmatch(self._mailcaps, mime_type, key=key)
        else:
            mc_tuple = mailcap.findmatch(self._mailcaps, mime_type,
                                         key='copiousoutput')
        if mc_tuple:
            if mc_tuple[1]:
                return mc_tuple[1][key]
        else:
            return None


settings = SettingsManager()
