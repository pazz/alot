import imp
import os
import ast
import mailcap
import codecs

from ConfigParser import SafeConfigParser


class FallbackConfigParser(SafeConfigParser):
    def __init__(self):
        SafeConfigParser.__init__(self)
        self.optionxform = lambda x: x

    def get(self, section, option, fallback=None, *args, **kwargs):
        if SafeConfigParser.has_option(self, section, option):
            return SafeConfigParser.get(self, section, option, *args, **kwargs)
        return fallback

    def getstringlist(self, section, option, **kwargs):
        value = self.get(section, option, **kwargs)
        return [s.strip() for s in value.split(',') if s.strip()]


class AlotConfigParser(FallbackConfigParser):
    def __init__(self):
        FallbackConfigParser.__init__(self)
        self.hooks = None

    def read(self, file):
        if not os.path.isfile(file):
            return

        SafeConfigParser.readfp(self, codecs.open(file, "r", "utf8"))
        if self.has_option('general', 'hooksfile'):
            hf = os.path.expanduser(self.get('general', 'hooksfile'))
            if hf is not None:
                try:
                    config.hooks = imp.load_source('hooks', hf)
                except:
                    pass

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
        mode = self.getint('general', 'colourmode')
        base = 'tag_%s' % tag
        if mode == 2:
            if self.get('1c-theme', base):
                return 'tag_%s' % tag
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

    def get_mapping(self, mode, key):
        cmdline = self.get(mode + '-maps', key)
        if not cmdline:
            cmdline = self.get('global-maps', key)
        return cmdline


class HookManager(object):
    def setup(self, hooksfile):
        hf = os.path.expanduser(hooksfile)
        if os.path.isfile(hf):
            try:
                self.module = imp.load_source('hooks', hf)
            except:
                self.module = None
        else:
            self.module = {}

    def get(self, key):
        if self.module:
            if key in self.module.__dict__:
                return self.module.__dict__[key]
        return None


config = AlotConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'defaults', 'alot.rc'))
notmuchconfig = FallbackConfigParser()
notmuchconfig.read(os.path.join(os.path.dirname(__file__),
                   'defaults',
                   'notmuch.rc'))
hooks = HookManager()
mailcaps = mailcap.getcaps()


def get_mime_handler(mime_type, key='view', interactive=True):
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
