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


class ListConfigParser(SafeConfigParser):
    def getstringlist(self, section, option, **kwargs):
        value = SafeConfigParser.get(self, section, option, **kwargs)
        return [s.strip() for s in value.split(',')]

DEFAULTS = {
    'colourmode': '16',
    'editor_cmd': "/usr/bin/vim -f -c 'set filetype=mail' ",
    'pager_cmd': "/usr/bin/view -f -c 'set filetype=mail' ",
    'terminal_cmd': 'urxvt -T notmuch -e',
    'spawn_editor': 'True',
    'spawn_pager': 'True',
    'displayed_headers': 'From,To,Cc,Bcc,Subject',
    'authors_maxlength': '30',
}

config = ListConfigParser(DEFAULTS)
config.add_section('general')

def setup(configfilename):
    config.read(configfilename)

# colour palette.
# id, fg16, bg16, mono, fg256, bg256
# see http://excess.org/urwid/reference.html#AttrSpec
# http://excess.org/urwid/wiki/DisplayAttributes
# interactive test-palette: http://excess.org/urwid/browser/palette_test.py
palette = [
    ('header', 'white', 'dark blue', 'bold', 'white', 'dark blue'),
    ('footer', 'white', 'dark blue', 'bold,standout', 'white', '#006'),
    ('prompt', 'light gray', 'black', 'standout', 'light gray', ''),
    ('threadline', '', '', '', '', ''),
    ('threadline_date', 'light gray', '', '', 'g58', ''),
    ('threadline_mailcount', 'light gray', '', '', 'light gray', ''),
    ('threadline_tags', 'brown', '', '', '#a86', ''),
    ('threadline_authors', 'dark green', '', '', '#6d6', ''),
    ('threadline_subject', 'light gray', '', '', 'g58', ''),
    ('threadline_content', 'dark gray', '', '', '#866', ''),
    ('threadline_focus', 'white', 'dark gray', 'standout', 'white', 'g11'),
    ('threadline_date_linefocus', 'light gray', 'dark gray', 'standout', 'g58', 'g11'),
    ('threadline_mailcount_linefocus', 'light gray', 'dark gray', 'standout', 'light gray', 'g11'),
    ('threadline_tags_linefocus', 'yellow,bold', 'dark gray', 'standout', '#ff8', 'g11'),
    ('threadline_authors_linefocus', 'dark green,bold', 'dark gray', 'standout','#8d6', 'g11'),
    ('threadline_subject_linefocus', 'light gray', 'dark gray', 'standout','g58', 'g11'),

    ('messagesummary_even', 'white', 'light blue', 'standout', 'white', '#068'),
    ('messagesummary_odd', 'white', 'dark blue', 'standout', 'white', '#006'),
    ('messagesummary_focus', 'white', 'dark green', 'standout,bold', '#ff8', 'g58'),
    ('message_header', 'white', 'dark gray', '', 'white', 'dark gray'),
    ('message_body', 'light gray', 'black', '', 'light gray', ''),

    ('bufferlist_results_even', 'light gray', 'black', '', '', 'g3'),
    ('bufferlist_results_odd', 'light gray', 'black', '', '', ''),
    ('bufferlist_focus', 'white', 'dark gray', '', '#ffa', 'g38'),

    ('taglist_tag', 'light gray', 'black', '', '', ''),
    ('taglist_focus', 'white', 'dark gray', '', '#ffa', 'g38'),
]

hooks = {
        'pre-shutdown': lambda ui: ui.logger.info('goodbye!'),
        }
