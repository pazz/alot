#!/usr/bin/python
# Copyright (C) 2013  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.

import urwid
import os
from example1 import palette  # example data
from widgets import TreeBox
from tree import Tree
from decoration import CollapsibleArrowTree


# define selectable urwid.Text widgets to display paths
class FocusableText(urwid.WidgetWrap):
    """Widget to display paths lines"""
    def __init__(self, txt):
        t = urwid.Text(txt)
        w = urwid.AttrMap(t, 'body', 'focus')
        urwid.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

# define Tree that can walk your filesystem


class DirectoryTree(Tree):
    """
    A custom Tree representing our filesystem structure.
    This implementation is rather inefficient: basically every position-lookup
    will call `os.listdir`.. This makes navigation in the tree quite slow.
    In real life you'd want to do some caching.

    As positions we use absolute path strings.
    """
    # determine dir separator and form of root node
    pathsep = os.path.sep
    drive, _ = os.path.splitdrive(pathsep)

    # define root node This is part of the Tree API!
    root = drive + pathsep

    def __getitem__(self, pos):
        return FocusableText(pos)

    # generic helper
    def _list_dir(self, path):
        """returns absolute paths for all entries in a directory"""
        try:
            elements = [os.path.join(
                path, x) for x in os.listdir(path) if os.path.isdir(path)]
            elements.sort()
        except OSError:
            elements = None
        return elements

    def _get_siblings(self, pos):
        """lists the parent directory of pos """
        parent = self.parent_position(pos)
        siblings = [pos]
        if parent is not None:
            siblings = self._list_dir(parent)
        return siblings

    # Tree API
    def parent_position(self, pos):
        parent = None
        if pos != '/':
            parent = os.path.split(pos)[0]
        return parent

    def first_child_position(self, pos):
        candidate = None
        if os.path.isdir(pos):
            children = self._list_dir(pos)
            if children:
                candidate = children[0]
        return candidate

    def last_child_position(self, pos):
        candidate = None
        if os.path.isdir(pos):
            children = self._list_dir(pos)
            if children:
                candidate = children[-1]
        return candidate

    def next_sibling_position(self, pos):
        candidate = None
        siblings = self._get_siblings(pos)
        myindex = siblings.index(pos)
        if myindex + 1 < len(siblings):  # pos is not the last entry
            candidate = siblings[myindex + 1]
        return candidate

    def prev_sibling_position(self, pos):
        candidate = None
        siblings = self._get_siblings(pos)
        myindex = siblings.index(pos)
        if myindex > 0:  # pos is not the first entry
            candidate = siblings[myindex - 1]
        return candidate

if __name__ == "__main__":
    cwd = os.getcwd()  # get current working directory
    dtree = DirectoryTree()  # get a directory walker

    # Use CollapsibleArrowTree for decoration.
    # define initial collapse:
    as_deep_as_cwd = lambda pos: dtree.depth(pos) >= dtree.depth(cwd)

    # We hide the usual arrow tip and use a customized collapse-icon.
    decorated_tree = CollapsibleArrowTree(dtree,
                                          is_collapsed=as_deep_as_cwd,
                                          arrow_tip_char=None,
                                          icon_frame_left_char=None,
                                          icon_frame_right_char=None,
                                          icon_collapsed_char=u'\u25B6',
                                          icon_expanded_char=u'\u25B7',)

    # stick it into a TreeBox and use 'body' color attribute for gaps
    tb = TreeBox(decorated_tree, focus=cwd)
    root_widget = urwid.AttrMap(tb, 'body')
    urwid.MainLoop(root_widget, palette).run()  # go
