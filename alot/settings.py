import imp
import os
import re
import mailcap
import logging
import urwid
from urwid import AttrSpec, AttrSpecError
from configobj import ConfigObj, Section

from account import SendmailAccount, MatchSdtoutAddressbook, AbookAddressBook

from alot.errors import ConfigError
from alot.helper import read_config

DEFAULTSPATH = os.path.join(os.path.dirname(__file__), 'defaults')


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

    def set(self, key, value):
        """
        setter for global config values

        :param key: config option identifise
        :type key: str
        :param value: option to set
        :type value: depends on the specfile :file:`alot.rc.spec`
        """
        self._config[key] = value

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
        if section in self._notmuchconfig:
            if key in self._notmuchconfig[section]:
                value = self._notmuchconfig[section][key]
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
