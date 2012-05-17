import imp
import os
import re
import errno
import mailcap
import logging
import urwid
import shutil
from urwid import AttrSpecError
from configobj import ConfigObj, Section

from alot.account import SendmailAccount
from alot.addressbooks import MatchSdtoutAddressbook, AbookAddressBook
from alot.helper import pretty_datetime, string_decode

from errors import ConfigError
from utils import read_config
from checks import force_list
from checks import mail_container
from checks import gpg_key
from theme import Theme


DEFAULTSPATH = os.path.join(os.path.dirname(__file__), '..', 'defaults')


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
        self._bindings = ConfigObj()

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
        newconfig = read_config(path, spec,
                                checks={'mail_container': mail_container,
                                        'force_list': force_list,
                                        'gpg_key_hint': gpg_key})
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
        # themes
        themestring = newconfig['theme']
        themes_dir = self._config.get('themes_dir')
        if themes_dir:
            themes_dir = os.path.expanduser(themes_dir)
        else:
            themes_dir = os.path.join(os.environ.get('XDG_CONFIG_HOME',
                            os.path.expanduser('~/.config')), 'alot', 'themes')
        logging.debug(themes_dir)

        if themestring:
            if not os.path.isdir(themes_dir):
                err_msg = 'cannot find theme %s: themes_dir %s is missing'
                raise ConfigError(err_msg % (themestring, themes_dir))
            else:
                theme_path = os.path.join(themes_dir, themestring)
                self._theme = Theme(theme_path)

        self._accounts = self._parse_accounts(self._config)
        self._accountmap = self._account_table(self._accounts)

    def write_default_config(self, path):
        """write out defaults/config.stub to path"""
        (dir, file) = os.path.split(path)
        try:
            os.makedirs(dir)
        except OSError, e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise
        shutil.copyfile(os.path.join(DEFAULTSPATH, 'config.stub'), path)

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
                logging.debug('abook defined: %s' % abook)
                if abook['type'] == 'shellcommand':
                    cmd = abook['command']
                    regexp = abook['regexp']
                    if cmd is not None and regexp is not None:
                        args['abook'] = MatchSdtoutAddressbook(cmd,
                                                               match=regexp)
                    else:
                        msg = 'underspecified abook of type \'shellcommand\':'
                        msg += '\ncommand: %s\nregexp:%s' % (cmd, regexp)
                        raise ConfigError(msg)
                elif abook['type'] == 'abook':
                    contacts_path = abook['abook_contacts_file']
                    args['abook'] = AbookAddressBook(contacts_path)
                else:
                    del(args['abook'])

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
        if value == None:
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
        if value == None:
            value = fallback
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
        for sec in self._config['tags'].sections:
            if re.match('^' + sec + '$', tag):
                fg = self._config['tags'][sec]['fg'] or default.foreground
                bg = self._config['tags'][sec]['bg'] or default.background
                try:
                    normal = urwid.AttrSpec(fg, bg, colours)
                except AttrSpecError:
                    normal = default
                focus_fg = self._config['tags'][sec]['focus_fg']
                focus_fg = focus_fg or default_f.foreground
                focus_bg = self._config['tags'][sec]['focus_bg']
                focus_bg = focus_bg or default_f.background
                try:
                    focussed = urwid.AttrSpec(focus_fg, focus_bg, colours)
                except AttrSpecError:
                    focussed = default_f

                hidden = self._config['tags'][sec]['hidden'] or False

                translated = self._config['tags'][sec]['translated'] or tag
                translation = self._config['tags'][sec]['translation']
                if translation:
                    translated = re.sub(translation[0], translation[1], tag)
                break
        else:
            normal = default
            focussed = default_f
            hidden = False
            translated = tag

        return {'normal': normal, 'focussed': focussed,
                'hidden': hidden, 'translated': translated}

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
        if key in bindings.scalars:
            cmdline = bindings[key]
        if mode in bindings.sections:
            if key in bindings[mode].scalars:
                cmdline = bindings[mode][key]
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
        3) use :function:`pretty_datetime` as fallback
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

settings = SettingsManager()
