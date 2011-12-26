import imp
import os
import ast
import mailcap
import codecs
import logging

from ConfigParser import SafeConfigParser


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
        return fallback

    def getstringlist(self, section, option, **kwargs):
        """directly parses a config value into a list of strings"""
        value = self.get(section, option, **kwargs)
        return [s.strip() for s in value.split(',') if s.strip()]


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

    def get_palette(self):
        """parse the sections '1c-theme', '16c-theme' and '256c-theme'
        into an urwid compatible colour palette.

        :returns: a palette
        :rtype: list
        """
        mode = self.getint('general', 'colourmode')
        ms = "%dc-theme" % mode
        names = self.options(ms)
        if mode > 2:
            names = set([s[:-3] for s in names])
        p = list()
        for attr in names:
            nf = self.get('16c-theme', attr + '_fg', fallback='default')
            nb = self.get('16c-theme', attr + '_bg', fallback='default')
            m = self.get('1c-theme', attr, fallback='default')
            hf = self.get('256c-theme', attr + '_fg', fallback='default')
            hb = self.get('256c-theme', attr + '_bg', fallback='default')
            p.append((attr, nf, nb, m, hf, hb))
            if attr.startswith('tag_') and attr + '_focus' not in names:
                nb = self.get('16c-theme', 'tag_focus_bg',
                              fallback='default')
                hb = self.get('256c-theme', 'tag_focus_bg',
                              fallback='default')
                p.append((attr + '_focus', nf, nb, m, hf, hb))
        return p

    def get_tagattr(self, tag, focus=False):
        """
        look up attribute string to use for a given tagstring

        :param tag: tagstring to look up
        :type tag: str
        :param focus: return the 'focussed' attribute
        :type focus: bool
        """

        mode = self.getint('general', 'colourmode')
        base = 'tag_%s' % tag
        if mode == 2:
            if self.get('1c-theme', base):
                return base
        elif mode == 16:
            has_fg = self.get('16c-theme', base + '_fg')
            has_bg = self.get('16c-theme', base + '_bg')
            if has_fg or has_bg:
                if focus:
                    return base + '_focus'
                else:
                    return base
        else:  # highcolour
            has_fg = self.get('256c-theme', base + '_fg')
            has_bg = self.get('256c-theme', base + '_bg')
            if has_fg or has_bg:
                if focus:
                    return base + '_focus'
                else:
                    return base
        if focus:
            return 'tag_focus'
        return 'tag'

    def has_theming(self, themeing):
        """
        Return true if the given themeing option exists in the current colour
        theme.

        :param themeing: The themeing option to check for
        :type theming: string
        :return: True if themeing exist, False otherwise
        :rtype: bool
        """
        mode = self.getint('general', 'colourmode')
        if mode == 2:
            theme = '1c-theme'
        else:
            theme = '{colours}c-theme'.format(colours=mode)
        has_fg = self.has_option(theme, themeing + '_fg')
        has_bg = self.has_option(theme, themeing + '_bg')
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
        cmdline = self.get(mode + '-maps', key)
        if not cmdline:
            cmdline = self.get('global-maps', key)
        return cmdline


config = AlotConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'defaults', 'alot.rc'))
notmuchconfig = FallbackConfigParser()
notmuchconfig.read(os.path.join(os.path.dirname(__file__),
                   'defaults',
                   'notmuch.rc'))
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
