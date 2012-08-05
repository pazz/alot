# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""
Utility Widgets not specific to alot
"""
import urwid
import logging


class AttrFlipWidget(urwid.AttrMap):
    """
    An AttrMap that can remember attributes to set
    """
    def __init__(self, w, maps, init_map='normal'):
        self.maps = maps
        urwid.AttrMap.__init__(self, w, maps[init_map])

    def set_map(self, attrstring):
        self.set_attr_map({None: self.maps[attrstring]})


class DialogBox(urwid.WidgetWrap):
    def __init__(self, body, title, bodyattr=None, titleattr=None):
        self.body = urwid.LineBox(body)
        self.title = urwid.Text(title)
        if titleattr is not None:
            self.title = urwid.AttrMap(self.title, titleattr)
        if bodyattr is not None:
            self.body = urwid.AttrMap(self.body, bodyattr)

        box = urwid.Overlay(self.title, self.body,
                            align='center',
                            valign='top',
                            width=len(title),
                            height=None,
                            )
        urwid.WidgetWrap.__init__(self, box)

    def selectable(self):
        return self.body.selectable()

    def keypress(self, size, key):
        return self.body.keypress(size, key)


class CatchKeyWidgetWrap(urwid.WidgetWrap):
    def __init__(self, widget, key, on_catch, relay_rest=True):
        urwid.WidgetWrap.__init__(self, widget)
        self.key = key
        self.relay = relay_rest
        self.on_catch = on_catch

    def selectable(self):
        return True

    def keypress(self, size, key):
        logging.debug('CATCH KEY: %s' % key)
        logging.debug('relay: %s' % self.relay)
        if key == self.key:
            self.on_catch()
        elif self._w.selectable() and self.relay:
            return self._w.keypress(size, key)
