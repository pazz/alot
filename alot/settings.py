"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import imp
import os
import mailcap
import codecs

from ConfigParser import SafeConfigParser
from account import Account


DEFAULTS = {
    'general': {
        'colourmode': '16',
        'editor_cmd': "/usr/bin/vim -f -c 'set filetype=mail' +",
        'terminal_cmd': 'x-terminal-emulator -e',
        'spawn_editor': 'False',
        'displayed_headers': 'From,To,Cc,Bcc,Subject',
        'authors_maxlength': '30',
        'ask_subject': 'True',
        'notify_timeout': '2',
        'show_statusbar': 'True',
        'flush_retry_timeout': '5',
        'hooksfile': '~/.alot.py',
    },
    'normal-theme': {
        'bufferlist_focus_bg': 'dark gray',
        'bufferlist_focus_fg': 'white',
        'bufferlist_results_even_bg': 'black',
        'bufferlist_results_even_fg': 'light gray',
        'bufferlist_results_odd_bg': 'black',
        'bufferlist_results_odd_fg': 'light gray',
        'footer_bg': 'dark blue',
        'footer_fg': 'light green',
        'header_bg': 'dark blue',
        'header_fg': 'white',
        'message_attachment_bg': 'dark gray',
        'message_attachment_fg': 'light gray',
        'message_attachment_focussed_bg': 'light green',
        'message_attachment_focussed_fg': 'light gray',
        'message_body_bg': 'default',
        'message_body_fg': 'light gray',
        'message_header_bg': 'dark gray',
        'message_header_fg': 'white',
        'message_header_key_bg': 'dark gray',
        'message_header_key_fg': 'white',
        'message_header_value_bg': 'dark gray',
        'message_header_value_fg': 'light gray',
        'messagesummary_even_bg': 'light blue',
        'messagesummary_even_fg': 'white',
        'messagesummary_focus_bg': 'dark cyan',
        'messagesummary_focus_fg': 'white',
        'messagesummary_odd_bg': 'dark blue',
        'messagesummary_odd_fg': 'white',
        'notify_error_bg': 'dark red',
        'notify_error_fg': 'white',
        'notify_normal_bg': 'default',
        'notify_normal_fg': 'default',
        'prompt_bg': 'black',
        'prompt_fg': 'light gray',
        'tag_focus_bg': 'dark cyan',
        'tag_focus_fg': 'white',
        'tag_bg': 'black',
        'tag_fg': 'brown',
        'threadline_authors_bg': 'default',
        'threadline_authors_fg': 'dark green',
        'threadline_authors_focus_bg': 'dark cyan',
        'threadline_authors_focus_fg': 'black,bold',
        'threadline_bg': 'default',
        'threadline_content_bg': 'default',
        'threadline_content_fg': 'dark gray',
        'threadline_date_bg': 'default',
        'threadline_date_fg': 'light gray',
        'threadline_date_focus_bg': 'dark cyan',
        'threadline_date_focus_fg': 'black',
        'threadline_fg': 'default',
        'threadline_focus_bg': 'dark cyan',
        'threadline_focus_fg': 'white',
        'threadline_mailcount_bg': 'default',
        'threadline_mailcount_fg': 'light gray',
        'threadline_mailcount_focus_bg': 'dark cyan',
        'threadline_mailcount_focus_fg': 'black',
        'threadline_subject_bg': 'default',
        'threadline_subject_fg': 'light gray',
        'threadline_subject_focus_bg': 'dark cyan',
        'threadline_subject_focus_fg': 'black',
        'threadline_tags_bg': 'default',
        'threadline_tags_fg': 'brown',
        'threadline_tags_focus_bg': 'dark cyan',
        'threadline_tags_focus_fg': 'yellow,bold',
    },
    'mono-theme': {
        'bufferlist_focus': 'standout',
        'bufferlist_results_even': 'default',
        'bufferlist_results_odd': 'default',
        'footer': 'standout',
        'header': 'standout',
        'message_attachment': 'default',
        'message_attachment_focussed': 'underline',
        'message_body': 'default',
        'message_header': 'default',
        'message_header_key': 'default',
        'message_header_value': 'default',
        'messagesummary_even': '',
        'messagesummary_focus': 'standout',
        'messagesummary_odd': '',
        'notify_error': 'standout',
        'notify_normal': 'default',
        'prompt': '',
        'tag_focus': 'standout',
        'tag': 'default',
        'threadline': 'default',
        'threadline_authors': 'default,underline',
        'threadline_authors_focus': 'standout',
        'threadline_content': 'default',
        'threadline_date': 'default',
        'threadline_date_focus': 'standout',
        'threadline_focus': 'standout',
        'threadline_mailcount': 'default',
        'threadline_mailcount_focus': 'standout',
        'threadline_subject': 'default',
        'threadline_subject_focus': 'standout',
        'threadline_tags': 'bold',
        'threadline_tags_focus': 'standout',
    },
    'highcolour-theme': {
        'bufferlist_focus_bg': 'g38',
        'bufferlist_focus_fg': '#ffa',
        'bufferlist_results_even_bg': 'g3',
        'bufferlist_results_even_fg': 'default',
        'bufferlist_results_odd_bg': 'default',
        'bufferlist_results_odd_fg': 'default',
        'footer_bg': '#006',
        'footer_fg': 'white',
        'header_bg': 'dark blue',
        'header_fg': 'white',
        'message_attachment_bg': 'dark gray',
        'message_attachment_fg': 'light gray',
        'message_attachment_focussed_bg': 'light green',
        'message_attachment_focussed_fg': 'light gray',
        'message_body_bg': 'default',
        'message_body_fg': 'light gray',
        'message_header_bg': 'dark gray',
        'message_header_fg': 'white',
        'message_header_key_bg': 'dark gray',
        'message_header_key_fg': 'white',
        'message_header_value_bg': 'dark gray',
        'message_header_value_fg': 'light gray',
        'messagesummary_even_bg': '#068',
        'messagesummary_even_fg': 'white',
        'messagesummary_focus_bg': 'g58',
        'messagesummary_focus_fg': '#ff8',
        'messagesummary_odd_bg': '#006',
        'messagesummary_odd_fg': 'white',
        'notify_error_bg': 'dark red',
        'notify_error_fg': 'white',
        'notify_normal_bg': 'default',
        'notify_normal_fg': 'default',
        'prompt_bg': 'default',
        'prompt_fg': 'light gray',
        'tag_focus_bg': 'g58',
        'tag_focus_fg': '#ffa',
        'tag_bg': 'default',
        'tag_fg': 'brown',
        'threadline_authors_bg': 'default',
        'threadline_authors_fg': '#6d6',
        'threadline_authors_focus_bg': 'g58',
        'threadline_authors_focus_fg': '#8f6',
        'threadline_bg': 'default',
        'threadline_content_bg': 'default',
        'threadline_content_fg': '#866',
        'threadline_date_bg': 'default',
        'threadline_date_fg': 'g58',
        'threadline_date_focus_bg': 'g58',
        'threadline_date_focus_fg': 'g89',
        'threadline_fg': 'default',
        'threadline_focus_bg': 'g58',
        'threadline_focus_fg': 'white',
        'threadline_mailcount_bg': 'default',
        'threadline_mailcount_fg': 'light gray',
        'threadline_mailcount_focus_bg': 'g58',
        'threadline_mailcount_focus_fg': 'g89',
        'threadline_subject_bg': 'default',
        'threadline_subject_fg': 'g58',
        'threadline_subject_focus_bg': 'g58',
        'threadline_subject_focus_fg': 'g89',
        'threadline_tags_bg': 'default',
        'threadline_tags_fg': '#a86',
        'threadline_tags_focus_bg': 'g58',
        'threadline_tags_focus_fg': '#ff8',
    },
    'global-maps': {
        '@': 'refresh',
        'I': 'search tag:inbox AND NOT tag:killed',
        'U': 'search tag:unread',
        'x': 'close',
        'tab': 'bnext',
        'shift tab': 'bprevious',
        '\\': 'prompt search ',
        'q': 'exit',
        ';': 'bufferlist',
        ':': 'prompt',
        'L': 'taglist',
        's': 'shell',
        '$': 'flush',
        '@': 'refresh',
        'm': 'compose',
    },
    'search-maps': {
        '|': 'refineprompt',
        'enter': 'openthread',
        'l': 'retagprompt',
        'a': 'toggletag inbox',
        '&': 'toggletag killed',
    },
    'thread-maps': {
        'a': 'toggletag inbox',
        'f': 'forward',
        'g': 'groupreply',
        'r': 'reply',
        'C': 'fold --all',
        'E': 'unfold --all',
        'enter': 'select',
    },
    'taglist-maps': {
        'enter': 'select',
    },
    'envelope-maps': {
        'y': 'send',
        'enter': 'reedit',
        't': 'prompt to',
        's': 'prompt subject',
    },
    'bufferlist-maps': {
        'd': 'closefocussed',
        'enter': 'openfocussed',
    },
    'command-aliases': {
        'clo': 'close',
        'bn': 'bnext',
        'bp': 'bprevious',
        'ls': 'bufferlist',
        'quit': 'exit',
    }
}


class CustomConfigParser(SafeConfigParser):
    def __init__(self, defaults):
        self.defaults = defaults
        self.hooks = None
        SafeConfigParser.__init__(self)
        self.optionxform = lambda x: x
        for sec in defaults.keys():
            self.add_section(sec)

    def get(self, section, option, fallback=None, *args, **kwargs):
        if SafeConfigParser.has_option(self, section, option):
            return SafeConfigParser.get(self, section, option, *args, **kwargs)
        elif section in self.defaults:
            if option in self.defaults[section]:
                return self.defaults[section][option]
        return fallback

    def has_option(self, section, option, *args, **kwargs):
        if SafeConfigParser.has_option(self, section, option):
            return True
        elif section in self.defaults:
            if option in self.defaults[section]:
                return True
        return False

    def getstringlist(self, section, option, **kwargs):
        value = self.get(section, option, **kwargs)
        return [s.strip() for s in value.split(',')]

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

    def get_modestring(self):
        mode = self.getint('general', 'colourmode')
        if mode == 2:
            return 'mono-theme'
        elif mode == 16:
            return 'normal-theme'
        else:
            return 'highcolour-theme'

    def get_palette(self):
        mode = self.getint('general', 'colourmode')
        ms = self.get_modestring()
        names = self.options(ms) + DEFAULTS[ms].keys()
        if mode > 2:
            names = set([s[:-3] for s in names])
        p = list()
        for attr in names:
            nf = self.get('normal-theme', attr + '_fg', fallback='default')
            nb = self.get('normal-theme', attr + '_bg', fallback='default')
            m = self.get('mono-theme', attr, fallback='default')
            hf = self.get('highcolour-theme', attr + '_fg', fallback='default')
            hb = self.get('highcolour-theme', attr + '_bg', fallback='default')
            p.append((attr, nf, nb, m, hf, hb))
            if attr.startswith('tag_') and attr + '_focus' not in names:
                nb = self.get('normal-theme', 'threadline_focus_bg', fallback='default')
                hb = self.get('highcolour-theme', 'threadline_focus_bg', fallback='default')
                p.append((attr + '_focus', nf, nb, m, hf, hb))
        return p

    def get_tagattr(self, tag, focus=False):
        mode = self.getint('general', 'colourmode')
        base = 'tag_%s' % tag
        if mode == 2:
            if self.get('mono-theme', base):
                return 'tag_%s' % tag
        elif mode == 16:
            has_fg = self.get('normal-theme', base + '_fg')
            has_bg = self.get('normal-theme', base + '_bg')
            if has_fg or has_bg:
                if focus:
                    return base + '_focus'
                else:
                    return base
        else:  # highcolour
            has_fg = self.get('highcolour-theme', base + '_fg')
            has_bg = self.get('highcolour-theme', base + '_bg')
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


class HookManager:
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

        def f(*args, **kwargs):
            msg = 'called undefined hook: %s with arguments'
        return f

    def call(self, hookname, *args, **kwargs):
        hook = self.get_hook(hookname)
        try:
            hook(*args, **kwargs)
        except:
            msg = 'exception occured while calling hook:' \
                    '%s with arguments %s,  %s'


config = CustomConfigParser(DEFAULTS)
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
