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
    def __init__(self, path):
        self._spec = os.path.join(DEFAULTSPATH, 'theme.spec')
        self._config = read_config(path, self._spec)
        self.attributes = self.parse_attributes(self._config)

    def parse_attributes(self, c):
        attributes = {}
        for sec in c.sections:
            try:
                colours = int(sec)
            except ValueError:
                err_msg='section %s is not an integer indicating a colour mode'
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
        return self.attributes[colourmode][mode][name]


class SettingsManager(object):
    def __init__(self, alot_rc=None, notmuch_rc=None, theme=None):
        self.hooks = None

        theme_path = theme or os.path.join(DEFAULTSPATH, 'default.theme')
        self.theme = Theme(theme_path)
        self._bindings = read_config(os.path.join(DEFAULTSPATH, 'bindings'))

        self._config = ConfigObj()
        self.read_config(alot_rc)
        self.read_notmuch_config(notmuch_rc)

        self._accounts = self.parse_accounts(self._config)


    def read_notmuch_config(self, path):
        spec = os.path.join(DEFAULTSPATH, 'notmuch.rc.spec')
        self._notmuchconfig = read_config(path, spec)

    def read_config(self, path):
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

    def parse_accounts(self, config):
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
                accounts.append(SendmailAccount(cmd, **args))
        return accounts


    def get(self, key):
        """
        look up global config values from alot's config

        :param key: key to look up
        :type key: str
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
        """
        value = None
        if key in self._notmuchconfig:
            value = self._notmuchconfig[key]
        return value

    def get_theming_attribute(self, mode, name):
        colours = int(self._config.get('colourmode'))
        return self.theme.get_attribute(mode, name,  colours)

    def get_tagstring_representation(self, tag):
        colours = int(self._config.get('colourmode'))
        default_att = self.theme.get_attribute('global', 'tag', colours)
        default_focus_att = self.theme.get_attribute('global', 'tag_focus',
                                                     colours)
        if tag in self._config['tags']:
            fg = self._config['tags'][tag]['fg'] or default_att.foreground
            bg = self._config['tags'][tag]['bg'] or default_att.background
            normal = urwid.AttrSpec(fg, bg, colours)
            ffg = self._config['tags'][tag]['focus_fg'] or default_focus_att.foreground
            fbg = self._config['tags'][tag]['focus_bg'] or default_focus_att.background
            focussed = urwid.AttrSpec(ffg, fbg, colours)
            translated = self._config['tags'][tag]['translated'] or tag
        else:
            normal = default_att
            focussed = default_focus_att
            translated = tag

        return {'normal': normal, 'focussed': focussed, 'translated': translated}


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

class FallbackConfigParser(SafeConfigParser):
    """:class:`~ConfigParser.SafeConfigParser` that allows fallback values"""
    def __init__(self):
        SafeConfigParser.__init__(self)
        self.optionxform = lambda x: x

    def get(self, section, option, fallback=None, *args, **kwargs):
        """get a config option

        :param section: section name
        :type section: str
        :param option: option key
        :type option: str
        :param fallback: the value to fall back if option undefined
        :type fallback: str
        """
        if SafeConfigParser.has_option(self, section, option):
            return SafeConfigParser.get(self, section, option, *args, **kwargs)
        elif fallback != None:
            return fallback
        else:
            raise NoOptionError(option, section)

    def getstringlist(self, section, option, **kwargs):
        """directly parses a config value into a list of strings"""
        stringlist = list()
        if self.has_option(section, option):
            value = self.get(section, option, **kwargs)
            stringlist = [s.strip() for s in value.split(',') if s.strip()]
        return stringlist


class AlotConfigParser(FallbackConfigParser):
    """:class:`FallbackConfigParser` for alots config."""
    def __init__(self):
        FallbackConfigParser.__init__(self)
        self.hooks = None

    def get_hook(self, key):
        """return hook (`callable`) identified by `key`"""
        if self.hooks:
            if key in self.hooks.__dict__:
                return self.hooks.__dict__[key]
        return None

    def read(self, file):
        if not os.path.isfile(file):
            return

        SafeConfigParser.readfp(self, codecs.open(file, "r", "utf8"))
        if self.has_option('general', 'hooksfile'):
            hf = os.path.expanduser(self.get('general', 'hooksfile'))
            if hf is not None:
                try:
                    self.hooks = imp.load_source('hooks', hf)
                except:
                    logging.debug('unable to load hooks file:%s' % hf)

        # fix quoted keys / values
        for section in self.sections():
            for key, value in self.items(section):
                if value and value[0] in "\"'":
                    value = ast.literal_eval(value)

                transformed_key = False
                if key[0] in "\"'":
                    transformed_key = ast.literal_eval(key)
                elif key == 'colon':
                    transformed_key = ':'

                if transformed_key:
                    self.remove_option(section, key)
                    self.set(section, transformed_key, value)
                else:
                    self.set(section, key, value)

        # parse highlighting rules
        self._highlighting_rules = self._parse_highlighting_rules()

    def get_palette(self):
        """parse the sections '1c-theme', '16c-theme' and '256c-theme'
        into an urwid compatible colour palette.

        :returns: a palette
        :rtype: list
        """
        mode = self.getint('general', 'colourmode')
        ms = "%dc-theme" % mode
        names = self.options(ms)
        if mode != 1:  # truncate '_fg'/'_bg' suffixes for multi-colour themes
            names = set([s[:-3] for s in names])
        p = list()
        for attr in names:
            nf = self._get_theming_option('16c-theme', attr + '_fg')
            nb = self._get_theming_option('16c-theme', attr + '_bg')
            m = self._get_theming_option('1c-theme', attr)
            hf = self._get_theming_option('256c-theme', attr + '_fg')
            hb = self._get_theming_option('256c-theme', attr + '_bg')
            p.append((attr, nf, nb, m, hf, hb))
            if attr.startswith('tag_') and attr + '_focus' not in names:
                nb = self.get('16c-theme', 'tag_focus_bg',
                              fallback='default')
                hb = self.get('256c-theme', 'tag_focus_bg',
                              fallback='default')
                p.append((attr + '_focus', nf, nb, m, hf, hb))
        return p

    def _get_theming_option(self, section, option, default='default'):
        """
        Retrieve the value of the given option from the given section of the
        config file.

        If the option does not exist, try its parent options before falling
        back to the specified default. The parent of an option is the name of
        the option itself minus the last section enclosed in underscores;
        so the parent of the option `aaa_bbb_ccc_fg` is of the form
        `aaa_bbb_fg`.

        :param section: the section of the config file to search for the given
                        option
        :type section: string
        :param option: the option to lookup
        :type option: string
        :param default: the value that is to be returned if neither the
                        requested option nor a parent exists
        :type default: string
        :return: the value of the given option, or the specified default
        :rtype: string
        """
        result = ''
        if 'focus' in option:
            parent_option_re = '(.+)_[^_]+_(focus_(?:fg|bg))'
        else:
            parent_option_re = '(.+)_[^_]+_(fg|bg)'

        if self.has_option(section, option):
            result = self.get(section, option)
        else:
            has_parent_option = re.search(parent_option_re, option)
            if has_parent_option:
                parent_option = '{0}_{1}'.format(has_parent_option.group(1),
                                                 has_parent_option.group(2))
                result = self._get_theming_option(section, parent_option)
            else:
                result = default
        return result

    def _parse_highlighting_rules(self):
        """
        Parse the highlighting rules from the config file.

        :returns: The highlighting rules
        :rtype: :py:class:`collections.OrderedDict`
        """
        rules = OrderedDict()
        config_string = self.get('highlighting', 'rules')
        try:
            rules = json.loads(config_string, object_pairs_hook=OrderedDict)
        except ValueError as err:
            raise ParsingError("Could not parse config option" \
                               " 'rules' in section 'highlighting':" \
                               " {reason}".format(reason=err))
        return rules

    def get_highlight_rules(self):
        """
        Getter for the highlighting rules.

        :returns: The highlighting rules
        :rtype: :py:class:`collections.OrderedDict`
        """
        return self._highlighting_rules

    def get_tag_theme(self, tag, focus=False, highlight=''):
        """
        look up attribute string to use for a given tagstring

        :param tag: tagstring to look up
        :type tag: str
        :param focus: return the 'focussed' attribute
        :type focus: bool
        :param highlight: suffix of highlight theme
        :type highlight: str
        """
        themes = self._select_tag_themes(tag, focus, highlight)
        selected_theme = themes[-1]
        for theme in themes:
            if self.has_theming(theme):
                selected_theme = theme
                break
        return selected_theme

    def _select_tag_themes(self, tag, focus=False, highlight=''):
        """
        Select tag themes based on tag name, focus and highlighting.

        :param tag: the name of the tag to theme
        :type tag: str
        :param focus: True if this tag is focussed, False otherwise
        :type focus: bool
        :param highlight: the suffix of the highlighting theme
        :type highlight: str
        :return: the selected themes, highest priority first
        :rtype: list
        """
        base = 'tag'
        themes = [base, base + '_{}'.format(tag)]
        if (highlight and
            'tags' in self.getstringlist('highlighting', 'components')):
            themes.insert(1, base + '_{}'.format(highlight))
            themes.insert(3, base + '_{}_{}'.format(tag, highlight))
        if focus:
            themes = [theme + '_focus' for theme in themes]
        themes.reverse()
        return themes

    def has_theming(self, theming):
        """
        Return true if the given theming option exists in the current colour
        theme.

        :param theming: The theming option to check for
        :type theming: string
        :return: True if theming exist, False otherwise
        :rtype: bool
        """
        mode = self.getint('general', 'colourmode')
        theme = '{colours}c-theme'.format(colours=mode)
        has_fg = self.has_option(theme, theming + '_fg')
        has_bg = self.has_option(theme, theming + '_bg')
        return (has_fg or has_bg)

    def get_mapping(self, mode, key):
        """look up keybinding from `MODE-maps` sections

        :param mode: mode identifier
        :type mode: str
        :param key: urwid-style key identifier
        :type key: str
        :returns: a command line to be applied upon keypress
        :rtype: str
        """
        cmdline = None
        if self.has_option(mode + '-maps', key):
            cmdline = self.get(mode + '-maps', key)
        elif self.has_option('global-maps', key):
            cmdline = self.get('global-maps', key)
        return cmdline


defaultconfig = os.path.join(DEFAULTSPATH, 'alot.rc')
defaultnotmuchconfig = os.path.join(DEFAULTSPATH, 'notmuch.rc')
config = AlotConfigParser()
config.read(defaultconfig)
notmuchconfig = FallbackConfigParser()
notmuchconfig.read(defaultnotmuchconfig)
settings = SettingsManager(os.path.join(DEFAULTSPATH, 'alot.rc.new'), defaultnotmuchconfig)
mailcaps = mailcap.getcaps()


def get_mime_handler(mime_type, key='view', interactive=True):
    """
    get shellcomand defined in the users `mailcap` as handler for files of
    given `mime_type`.

    :param mime_type: file type
    :type mime_type: str
    :param key: identifies one of possibly many commands for this type by
                naming the intended usage, e.g. 'edit' or 'view'. Defaults
                to 'view'.
    :type key: str
    :param interactive: choose the "interactive session" handler rather than
                        the "print to stdout and immediately return" handler
    :type interactive: bool
    """
    if interactive:
        mc_tuple = mailcap.findmatch(mailcaps,
                                     mime_type,
                                     key=key)
    else:
        mc_tuple = mailcap.findmatch(mailcaps,
                                     mime_type,
                                     key='copiousoutput')
    if mc_tuple:
        if mc_tuple[1]:
            return mc_tuple[1][key]
    else:
        return None
