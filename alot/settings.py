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
from ConfigParser import SafeConfigParser


DEFAULTS = {
    'general': {
        'colourmode': '16',
        'editor_cmd': "/usr/bin/vim -f -c 'set filetype=mail' ",
        'pager_cmd': "/usr/bin/view -f -c 'set filetype=mail' ",
        'terminal_cmd': 'urxvt -T notmuch -e',
        'spawn_editor': 'True',
        'spawn_pager': 'True',
        'displayed_headers': 'From,To,Cc,Bcc,Subject',
        'authors_maxlength': '30',
    },
    'normal-theme': {
        'bufferlist_focus_bg': 'dark gray',
        'bufferlist_focus_fg': 'white',
        'bufferlist_results_even_bg': 'black',
        'bufferlist_results_even_fg': 'light gray',
        'bufferlist_results_odd_bg': 'black',
        'bufferlist_results_odd_fg': 'light gray',
        'footer_bg': 'dark blue',
        'footer_fg': 'white',
        'header_bg': 'dark blue',
        'header_fg': 'white',
        'message_body_bg': 'black',
        'message_body_fg': 'light gray',
        'message_header_bg': 'dark gray',
        'message_header_fg': 'white',
        'messagesummary_even_bg': 'light blue',
        'messagesummary_even_fg': 'white',
        'messagesummary_focus_bg': 'dark green',
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
        'threadline_authors_linefocus_bg': 'dark gray',
        'threadline_authors_linefocus_fg': 'dark green,bold',
        'threadline_bg': 'default',
        'threadline_content_bg': 'default',
        'threadline_content_fg': 'dark gray',
        'threadline_date_bg': 'default',
        'threadline_date_fg': 'light gray',
        'threadline_date_linefocus_bg': 'dark gray',
        'threadline_date_linefocus_fg': 'light gray',
        'threadline_fg': 'default',
        'threadline_focus_bg': 'dark gray',
        'threadline_focus_fg': 'white',
        'threadline_mailcount_bg': 'default',
        'threadline_mailcount_fg': 'light gray',
        'threadline_mailcount_linefocus_bg': 'dark gray',
        'threadline_mailcount_linefocus_fg': 'light gray',
        'threadline_subject_bg': 'default',
        'threadline_subject_fg': 'light gray',
        'threadline_subject_linefocus_bg': 'dark gray',
        'threadline_subject_linefocus_fg': 'light gray',
        'threadline_tags_bg': 'default',
        'threadline_tags_fg': 'brown',
        'threadline_tags_linefocus_bg': 'dark gray',
        'threadline_tags_linefocus_fg': 'yellow,bold',
    },
    'mono-theme': {
        'header': 'bold',
        'footer': 'bold',
        'prompt': 'standout',
        'threadline': 'default',
        'threadline_date': 'default',
        'threadline_mailcount': 'default',
        'threadline_tags': 'default',
        'threadline_authors': 'default',
        'threadline_subject': 'default',
        'threadline_content': 'default',
        'threadline_focus': 'standout',
        'threadline_date_linefocus': 'standout',
        'threadline_mailcount_linefocus': 'standout',
        'threadline_tags_linefocus': 'standout',
        'threadline_authors_linefocus': 'standout',
        'threadline_subject_linefocus': 'standout',
        'messagesummary_even': 'standout',
        'messagesummary_odd': 'standout',
        'messagesummary_focus': 'standout',
        'message_header': 'default',
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
        'message_body_bg': 'default',
        'message_body_fg': 'light gray',
        'message_header_bg': 'dark gray',
        'message_header_fg': 'white',
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
        'threadline_authors_linefocus_bg': 'g11',
        'threadline_authors_linefocus_fg': '#8d6',
        'threadline_bg': 'default',
        'threadline_content_bg': 'default',
        'threadline_content_fg': '#866',
        'threadline_date_bg': 'default',
        'threadline_date_fg': 'g58',
        'threadline_date_linefocus_bg': 'g11',
        'threadline_date_linefocus_fg': 'g58',
        'threadline_fg': 'default',
        'threadline_focus_bg': 'g11',
        'threadline_focus_fg': 'white',
        'threadline_mailcount_bg': 'default',
        'threadline_mailcount_fg': 'light gray',
        'threadline_mailcount_linefocus_bg': 'g11',
        'threadline_mailcount_linefocus_fg': 'light gray',
        'threadline_subject_bg': 'default',
        'threadline_subject_fg': 'g58',
        'threadline_subject_linefocus_bg': 'g11',
        'threadline_subject_linefocus_fg': 'g58',
        'threadline_tags_bg': 'default',
        'threadline_tags_fg': '#a86',
        'threadline_tags_linefocus_bg': 'g11',
        'threadline_tags_linefocus_fg': '#ff8',
    },
}


class CustomConfigParser(SafeConfigParser):
    def __init__(self, defaults):
        self.defaults = defaults
        SafeConfigParser.__init__(self)
        for sec in defaults.keys():
            self.add_section(sec)

    def get(self, section, option, *args, **kwargs):
        if self.has_option(section, option):
            return SafeConfigParser.get(self, section, option, *args, **kwargs)
        else:
            return self.defaults[section][option]

    def getstringlist(self, section, option, **kwargs):
        value = SafeConfigParser.get(self, section, option, **kwargs)
        return [s.strip() for s in value.split(',')]


config = CustomConfigParser(DEFAULTS)


def setup(configfilename):
    config.read(configfilename)


def get_palette():
    p = list()
    for attr in DEFAULTS['mono-theme'].keys():
        p.append((
            attr,
            config.get('normal-theme', attr + '_fg'),
            config.get('normal-theme', attr + '_bg'),
            config.get('mono-theme', attr),
            config.get('highcolour-theme', attr + '_fg'),
            config.get('highcolour-theme', attr + '_bg'),
        ))
    return p

hooks = {
        'pre-shutdown': lambda ui: ui.logger.info('goodbye!'),
        }
