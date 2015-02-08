# Copyright (C) 2013  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.

import logging


class Tree(object):
    """
    Base class for a tree strucures that can be displayed by :class:`TreeBox`
    widgets. An instance defines a structure by defining local transformations
    on positions. That is, by overwriting

     * `next_sibling_position`
     * `prev_sibling_position`
     * `parent_position`
     * `first_child_position`
     * `last_child_position`

    that compute the next position in the respective direction. Also, they need
    to implement method `__getitem__` that returns a :class:`Widget` for a
    given position.

    The type of objects used as positions may vary in subclasses and is
    deliberately unspecified for the base class.

    This base class already implements methods based on the local
    transformations above. These include :meth:`depth`, :meth:`last_decendant`
    and :meth:`[next|prev]_position <next_position>` that computes
    next/previous positions in depth-first order.
    """
    root = None

    # local helper
    def _get(self, pos):
        """loads widget at given position; handling invalid arguments"""
        res = None, None
        if pos is not None:
            try:
                res = self[pos], pos
            except (IndexError, KeyError):
                pass
        return res

    def _next_of_kin(self, pos):
        """
        looks up the next sibling of the closest ancestor with not-None next
        siblings.
        """
        candidate = None
        parent = self.parent_position(pos)
        if parent is not None:
            candidate = self.next_sibling_position(parent)
            if candidate is None:
                candidate = self._next_of_kin(parent)
        return candidate

    def _last_in_direction(self, starting_pos, direction):
        """
        move in the tree in given direction and return the last position.

        :param starting_pos: position to start at
        :param direction: callable that transforms a position into a position.
        """
        cur_pos = None
        next_pos = starting_pos
        while next_pos is not None:
            cur_pos = next_pos
            next_pos = direction(cur_pos)
        return cur_pos

    def depth(self, pos):
        """determine depth of node at pos"""
        parent = self.parent_position(pos)
        if parent is None:
            return 0
        else:
            return self.depth(parent) + 1

    def is_leaf(self, pos):
        """checks if given position has no children"""
        return self.first_child_position(pos) is None

    def first_ancestor(self, pos):
        """
        position of pos's ancestor with depth 0. Usually, this should return
        the root node, but a :class:`Tree` might represent a forrest - have
        multiple nodes without parent.
        """
        return self._last_in_direction(pos, self.parent_position)

    def last_decendant(self, pos):
        """position of last (in DFO) decendant of pos"""
        return self._last_in_direction(pos, self.last_child_position)

    def last_sibling_position(self, pos):
        """position of last sibling of pos"""
        return self._last_in_direction(pos, self.next_sibling_position)

    def first_sibling_position(self, pos):
        """position of first sibling of pos"""
        return self._last_in_direction(pos, self.prev_sibling_position)

    def next_position(self, pos):
        """returns the next position in depth-first order"""
        candidate = None
        if pos is not None:
            candidate = self.first_child_position(pos)
            if candidate is None:
                candidate = self.next_sibling_position(pos)
                if candidate is None:
                    candidate = self._next_of_kin(pos)
        return candidate

    def prev_position(self, pos):
        """returns the previous position in depth-first order"""
        candidate = None
        if pos is not None:
            prevsib = self.prev_sibling_position(pos)  # is None if first
            if prevsib is not None:
                candidate = self.last_decendant(prevsib)
            else:
                parent = self.parent_position(pos)
                if parent is not None:
                    candidate = parent
        return candidate

    def positions(self, reverse=False):
        """returns a generator that walks the positions of this tree in DFO"""
        def Posgen(reverse):
            if reverse:
                lastrootsib = self.last_sibling_position(self.root)
                current = self.last_decendant(lastrootsib)
                while current is not None:
                    yield current
                    current = self.prev_position(current)
            else:
                current = self.root
                while current is not None:
                    yield current
                    current = self.next_position(current)
        return Posgen(reverse)

    ####################################################################
    # End of high-level helper implementation. The following need to be
    # overwritten by subclasses
    ####################################################################
    def parent_position(self, pos):
        """returns the position of the parent node of the node at `pos`
        or `None` if none exists."""
        return None

    def first_child_position(self, pos):
        """returns the position of the first child of the node at `pos`,
        or `None` if none exists."""
        return None

    def last_child_position(self, pos):
        """returns the position of the last child of the node at `pos`,
        or `None` if none exists."""
        return None

    def next_sibling_position(self, pos):
        """returns the position of the next sibling of the node at `pos`,
        or `None` if none exists."""
        return None

    def prev_sibling_position(self, pos):
        """returns the position of the previous sibling of the node at `pos`,
        or `None` if none exists."""
        return None


class SimpleTree(Tree):
    """
    Walks on a given fixed acyclic structure given as a list of nodes; every
    node is a tuple `(content, children)`, where `content` is a `urwid.Widget`
    to be displayed at that position and `children` is either `None` or a list
    of nodes.

    Positions are lists of integers determining a path from the root node with
    position `(0,)`.
    """
    def __init__(self, treelist):
        self._treelist = treelist
        self.root = (0,) if treelist else None
        Tree.__init__(self)

    # a few local helper methods
    def _get_substructure(self, treelist, pos):
        """recursive helper to look up node-tuple for `pos` in `treelist`"""
        subtree = None
        if len(pos) > 1:
            subtree = self._get_substructure(treelist[pos[0]][1], pos[1:])
        else:
            try:
                subtree = treelist[pos[0]]
            except (IndexError, TypeError):
                pass
        return subtree

    def _get_node(self, treelist, pos):
        """
        look up widget at `pos` of `treelist`; default to None if
        nonexistent.
        """
        node = None
        if pos is not None:
            subtree = self._get_substructure(treelist, pos)
            if subtree is not None:
                node = subtree[0]
        return node

    def _confirm_pos(self, pos):
        """look up widget for pos and default to None"""
        candidate = None
        if self._get_node(self._treelist, pos) is not None:
            candidate = pos
        return candidate

    # Tree API
    def __getitem__(self, pos):
        return self._get_node(self._treelist, pos)

    def parent_position(self, pos):
        parent = None
        if pos is not None:
            if len(pos) > 1:
                parent = pos[:-1]
        return parent

    def first_child_position(self, pos):
        return self._confirm_pos(pos + (0,))

    def last_child_position(self, pos):
        candidate = None
        subtree = self._get_substructure(self._treelist, pos)
        if subtree is not None:
            children = subtree[1]
            if children is not None:
                candidate = pos + (len(children) - 1,)
        return candidate

    def next_sibling_position(self, pos):
        return self._confirm_pos(pos[:-1] + (pos[-1] + 1,))

    def prev_sibling_position(self, pos):
        return pos[:-1] + (pos[-1] - 1,) if (pos[-1] > 0) else None

    # optimizations
    def depth(self, pos):
        """more performant implementation due to specific structure of pos"""
        return len(pos) - 1
