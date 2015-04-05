# Copyright (C) 2011-2017  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

import urwid


class ANSIText(urwid.WidgetWrap):

    """Selectable Text widget that interprets ANSI color codes"""

    def __init__(self, txt,
                 default_attr=None,
                 default_attr_focus=None,
                 ansi_background=True, **kwds):
        ct, focus_map = parse_escapes_to_urwid(txt, default_attr,
                                               default_attr_focus,
                                               ansi_background)
        t = urwid.Text(ct, **kwds)
        attr_map = { default_attr.background: ''}
        w = urwid.AttrMap(t, attr_map, focus_map)
        urwid.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

ECODES = {
    '1': {'bold': True},
    '4': {'underline': True},
    '7': {'standout': True},
    '30': {'fg': 'black'},
    '31': {'fg': 'dark red'},
    '32': {'fg': 'dark green'},
    '33': {'fg': 'brown'},
    '34': {'fg': 'dark blue'},
    '35': {'fg': 'dark magenta'},
    '36': {'fg': 'dark cyan'},
    '37': {'fg': 'light gray'},
    '40': {'bg': 'black'},
    '41': {'bg': 'dark red'},
    '42': {'bg': 'dark green'},
    '43': {'bg': 'brown'},
    '44': {'bg': 'dark blue'},
    '45': {'bg': 'dark magenta'},
    '46': {'bg': 'dark cyan'},
    '47': {'bg': 'light gray'},
}


def parse_escapes_to_urwid(text, default_attr=None, default_attr_focus=None,
                           parse_background=True):
    """This function converts a text with ANSI escape for terminal
    attributes and returns a list containing each part of text and its
    corresponding Urwid Attributes object, it also returns a dictionary which
    maps all attributes applied here to focused attribute.
    """

    text = text.split("\033[")
    urwid_text = [text[0]]
    urwid_focus = {None: default_attr_focus}

    # Escapes are cumulative so we always keep previous values until it's
    # changed by another escape.
    attr = dict(fg=default_attr._foreground_color, bg=default_attr.background,
                bold=default_attr.bold, underline=default_attr.underline,
                standout=default_attr.underline)
    for part in text[1:]:
        esc_code, esc_substr = part.split('m', 1)
        esc_code = esc_code.split(';')

        if not esc_code:
            attr.update(fg=default_attr._foreground_color,
                        bg=default_attr.background, bold=default_attr.bold,
                        underline=default_attr.underline,
                        standout=default_attr.underline)
        else:
            i = 0
            while i < len(esc_code):
                code = esc_code[i]
                if code is 0:
                    attr.update({'bold': default_attr.bold,
                                 'underline': default_attr.underline,
                                 'standout': default_attr.standout})
                if code in ECODES:
                    attr.update(ECODES[code])
                # 256 codes
                elif code == '38':
                    attr.update(fg='h' + esc_code[i+2])
                    i += 2
                elif code == '48':
                    attr.update(bg='h'+esc_code[i+2])
                    i += 2
                i += 1

        # If there is no string in esc_substr we skip it, the above
        # attributes will accumulate to the next escapes.
        if esc_substr:
            # Construct Urwid attributes
            urwid_fg = attr['fg']
            urwid_bg = default_attr.background
            if attr['bold']:
                urwid_fg += ',bold'
            if attr['underline']:
                urwid_fg += ',underline'
            if attr['standout']:
                urwid_fg += ',standout'
            if parse_background:
                urwid_bg = attr['bg']
            urwid_attr = urwid.AttrSpec(urwid_fg, urwid_bg)
            urwid_focus[urwid_attr] = default_attr_focus
            urwid_text.append((urwid_attr, esc_substr))
    return urwid_text, urwid_focus
