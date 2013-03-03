#!/usr/bin/python
# Copyright (C) 2013  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.

from example1 import construct_example_tree, palette  # example data
from decoration import ArrowTree  # for Decoration
from widgets import TreeBox
import urwid

if __name__ == "__main__":
    # get example tree
    stree = construct_example_tree()
    # Here, we add some decoration by wrapping the tree using ArrowTree.
    atree = ArrowTree(stree,
                      # customize at will..
                      # arrow_hbar_char=u'\u2550',
                      # arrow_vbar_char=u'\u2551',
                      # arrow_tip_char=u'\u25B7',
                      # arrow_connector_tchar=u'\u2560',
                      # arrow_connector_lchar=u'\u255A',
                      )

    # put the into a treebox
    treebox = TreeBox(atree)

    rootwidget = urwid.AttrMap(treebox, 'body')
    urwid.MainLoop(rootwidget, palette).run()  # go
