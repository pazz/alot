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

from ConfigParser import SafeConfigParser
from account import Account


DEFAULTS = {
    'general': {
        'colourmode': '16',
        'editor_cmd': "/usr/bin/vim -f -c 'set filetype=mail' +",
        'terminal_cmd': 'urxvt -T notmuch -e',
        'spawn_editor': 'False',
        'displayed_headers': 'From,To,Cc,Bcc,Subject',
        'authors_maxlength': '30',
        'ask_subject': 'True',
        'notify_timeout': '2',
        'show_notificationbar': 'False',
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
        'message_body_bg': 'default',
        'message_body_fg': 'light gray',
        'message_header_bg': 'dark gray',
        'message_header_fg': 'white',
        'message_header_key_fg': 'white',
        'message_header_key_bg': 'dark gray',
        'message_header_value_fg': 'light gray',
        'message_header_value_bg': 'dark gray',
        'messagesummary_even_bg': 'light blue',
        'messagesummary_even_fg': 'white',
        'messagesummary_focus_bg': 'dark cyan',
        'messagesummary_focus_fg': 'white',
        'messagesummary_odd_bg': 'dark blue',
        'messagesummary_odd_fg': 'white',
        'prompt_bg': 'black',
        'prompt_fg': 'light gray',
        'taglist_focus_bg': 'dark gray',
        'taglist_focus_fg': 'white',
        'taglist_tag_bg': 'black',
        'taglist_tag_fg': 'light gray',
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
        'header': 'standout',
        'footer': 'standout',
        'prompt': '',
        'threadline': 'default',
        'threadline_date': 'default',
        'threadline_mailcount': 'default',
        'threadline_tags': 'bold',
        'threadline_authors': 'default,underline',
        'threadline_subject': 'default',
        'threadline_content': 'default',
        'threadline_focus': 'standout',
        'threadline_date_focus': 'standout',
        'threadline_mailcount_focus': 'standout',
        'threadline_tags_focus': 'standout',
        'threadline_authors_focus': 'standout',
        'threadline_subject_focus': 'standout',
        'messagesummary_even': '',
        'messagesummary_odd': '',
        'messagesummary_focus': 'standout',
        'message_attachment': 'default',
        'message_header': 'default',
        'message_header_key': 'default',
        'message_header_value': 'default',
        'message_body': 'default',
        'bufferlist_results_even': 'default',
        'bufferlist_results_odd': 'default',
        'bufferlist_focus': 'standout',
        'taglist_tag': 'default',
        'taglist_focus': 'standout',
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
        'message_body_bg': 'default',
        'message_body_fg': 'light gray',
        'message_header_bg': 'dark gray',
        'message_header_fg': 'white',
        'message_header_key_fg': 'white',
        'message_header_key_bg': 'dark gray',
        'message_header_value_fg': 'light gray',
        'message_header_value_bg': 'dark gray',
        'messagesummary_even_bg': '#068',
        'messagesummary_even_fg': 'white',
        'messagesummary_focus_bg': 'g58',
        'messagesummary_focus_fg': '#ff8',
        'messagesummary_odd_bg': '#006',
        'messagesummary_odd_fg': 'white',
        'prompt_bg': 'default',
        'prompt_fg': 'light gray',
        'taglist_focus_bg': 'g38',
        'taglist_focus_fg': '#ffa',
        'taglist_tag_bg': 'default',
        'taglist_tag_fg': 'default',
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
        'r': 'reply',
        'g': 'groupreply',
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
    }
}


class CustomConfigParser(SafeConfigParser):
    def __init__(self, defaults):
        self.defaults = defaults
        self.hooks = None
        SafeConfigParser.__init__(self)
        self.optionxform = str
        for sec in defaults.keys():
            self.add_section(sec)

    def get(self, section, option, *args, **kwargs):
        if self.has_option(section, option):
            return SafeConfigParser.get(self, section, option, *args, **kwargs)
        elif section in self.defaults:
            if option in self.defaults[section]:
                return self.defaults[section][option]
        else:
            return None

    def getstringlist(self, section, option, **kwargs):
        value = self.get(section, option, **kwargs)
        return [s.strip() for s in value.split(',')]

    def read(self, *args):
        SafeConfigParser.read(self, *args)
        if self.has_option('general', 'hooksfile'):
            hf = os.path.expanduser(config.get('general', 'hooksfile'))
            if hf is not None:
                try:
                    config.hooks = imp.load_source('hooks', hf)
                except:
                    pass

    def get_palette(self):
        p = list()
        for attr in DEFAULTS['mono-theme'].keys():
            p.append((
                attr,
                self.get('normal-theme', attr + '_fg'),
                self.get('normal-theme', attr + '_bg'),
                self.get('mono-theme', attr),
                self.get('highcolour-theme', attr + '_fg'),
                self.get('highcolour-theme', attr + '_bg'),
            ))
        return p

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


def get_mime_handler(mime_type, key, interactive=True):
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
