#!/usr/bin/python
# Copyright (C) 2013  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.

from example1 import construct_example_tree, palette  # example data
from decoration import CollapsibleIndentedTree  # for Decoration
from widgets import TreeBox
import urwid

if __name__ == "__main__":
    # get some SimpleTree
    stree = construct_example_tree()

    # Use (subclasses of) the wrapper decoration.CollapsibleTree to construct a
    # tree where collapsible subtrees. Apart from the original tree, these take
    # a callable `is_collapsed` that defines initial collapsed-status if a
    # given position.

    # We want all grandchildren collapsed initially
    if_grandchild = lambda pos: stree.depth(pos) > 1

    # We use CollapsibleIndentedTree around the original example tree.
    # This uses Indentation to indicate the tree structure and squeezes in
    # text-icons to indicate the collapsed status.
    # Also try CollapsibleTree or CollapsibleArrowTree..
    tree = CollapsibleIndentedTree(stree,
                                   is_collapsed=if_grandchild,
                                   icon_focussed_att='focus',
                                   # indent=6,
                                   # childbar_offset=1,
                                   # icon_frame_left_char=None,
                                   # icon_frame_right_char=None,
                                   # icon_expanded_char='-',
                                   # icon_collapsed_char='+',
                                   )

    # put the tree into a treebox
    treebox = TreeBox(tree)

    rootwidget = urwid.AttrMap(treebox, 'body')
    urwid.MainLoop(rootwidget, palette).run()  # go
