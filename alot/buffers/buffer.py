# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file


class Buffer(object):
    """Abstract base class for buffers."""

    modename = None  # mode identifier for subclasses

    def __init__(self, ui, widget):
        self.ui = ui
        self.body = widget

    def __str__(self):
        return '[%s]' % self.modename

    def render(self, size, focus=False):
        return self.body.render(size, focus)

    def selectable(self):
        return self.body.selectable()

    def rebuild(self):
        """tells the buffer to (re)construct its visible content."""
        pass

    def keypress(self, size, key):
        return self.body.keypress(size, key)

    def cleanup(self):
        """called before buffer is closed"""
        pass

    def get_info(self):
        """
        return dict of meta infos about this buffer.
        This can be requested to be displayed in the statusbar.
        """
        return {}
