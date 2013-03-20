# Copyright (C) 2013  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
from tree import Tree
from decoration import DecoratedTree, CollapseMixin


class NestedTree(Tree):
    """
    A Tree that wraps around Trees that may contain list walkers or other
    trees.  The wrapped tree may contain normal widgets as well. List walkers
    and subtree contents will be expanded into the tree presented by this
    wrapper.

    This wrapper's positions are tuples of positions of the original and
    subtrees: For example, `(X,Y,Z)` points at position Z in tree/list at
    position Y in tree/list at position X in the original tree.

    NestedTree transparently behaves like a collapsible DecoratedTree.
    """
    @property
    def root(self):
        root = (self._tree.root,)
        rcontent = self._tree[self._tree.root]
        if isinstance(rcontent, Tree):
            root = root + (rcontent.root,)
        return root

    def _sanitize_position(self, pos, tree=None):
        """
        Ensure a position tuple until the result does not
        point to a :class:`Tree` any more.
        """
        if pos is not None:
            tree = tree or self._tree
            entry = self._lookup_entry(tree, pos)
            if isinstance(entry, Tree):
                pos = pos + self._sanitize_position((entry.root,), tree=entry)
        return pos

    def __init__(self, tree, interpret_covered=False):
        self._tree = tree
        self._interpret_covered = interpret_covered

    def _lookup_entry(self, tree, pos):
        if len(pos) == 0:
            entry = tree[tree.root]
        else:
            entry = tree[pos[0]]
            if len(pos) > 1 and isinstance(entry, Tree):
                subtree = entry
                entry = self._lookup_entry(subtree, pos[1:])
        return entry

    def _depth(self, tree, pos, outmost_only=True):
        depth = self._tree.depth(pos[1:])
        if not outmost_only:
            entry = self._tree[pos[0]]
            if isinstance(entry, Tree) and len(pos) > 1:
                depth += self._depth(entry, pos[1:], outmost_only=False)
        return depth

    def depth(self, pos, outmost=True):
        return self._depth(self._tree, pos)

    def __getitem__(self, pos):
        return self._lookup_entry(self._tree, pos)

    # DecoratedTree API
    def _get_decorated_entry(self, tree, pos, widget=None, is_first=True):
        entry = tree[pos[0]]
        if len(pos) > 1 and isinstance(entry, Tree):
            subtree = entry
            entry = self._get_decorated_entry(
                subtree, pos[1:], widget, is_first)
        else:
            entry = widget or entry
        if isinstance(tree, (DecoratedTree, NestedTree)):  # has decorate-API
            isf = len(pos) < 2
            if not isf and isinstance(tree[pos[0]], Tree):
                isf = (tree[pos[0]].parent_position(pos[1])
                       is None) or not is_first
            entry = tree.decorate(pos[0], entry, is_first=isf)
        return entry

    def get_decorated(self, pos):
        return self._get_decorated_entry(self._tree, pos)

    def decorate(self, pos, widget, is_first=True):
        return self._get_decorated_entry(self._tree, pos, widget, is_first)

    # Collapse API
    def _get_subtree_for(self, pos):
        """returns Tree that manages pos[-1]"""
        res = self._tree
        candidate = self._lookup_entry(self._tree, pos[:-1])
        if isinstance(candidate, Tree):
            res = candidate
        return res

    def collapsible(self, pos):
        res = False
        subtree = self._get_subtree_for(pos)
        if isinstance(subtree, (CollapseMixin, NestedTree)):
            res = subtree.collapsible(pos[-1])
        return res

    def is_collapsed(self, pos):
        res = False
        subtree = self._get_subtree_for(pos)
        if isinstance(subtree, (CollapseMixin, NestedTree)):
            res = subtree.is_collapsed(pos[-1])
        return res

    def toggle_collapsed(self, pos):
        subtree = self._get_subtree_for(pos)
        if isinstance(subtree, (CollapseMixin, NestedTree)):
            subtree.toggle_collapsed(pos)

    def collapse(self, pos):
        subtree = self._get_subtree_for(pos)
        if isinstance(subtree, (CollapseMixin, NestedTree)):
            subtree.collapse(pos[-1])

    def collapse_all(self):
        self._collapse_all(self._tree, self.root)

    def _collapse_all(self, tree, pos=None):
        if pos is not None:
            if isinstance(tree, (CollapseMixin, NestedTree)):
                tree.expand_all()

            if len(pos) > 1:
                self._collapse_all(tree[pos[0]], pos[1:])
            nextpos = tree.next_position(pos[0])
            if nextpos is not None:
                nentry = tree[nextpos]
                if isinstance(nentry, Tree):
                    self._collapse_all(nentry, (nentry.root,))
                self._collapse_all(tree, (nextpos,))
            if isinstance(tree, (CollapseMixin, NestedTree)):
                tree.collapse_all()

    def expand(self, pos):
        subtree = self._get_subtree_for(pos)
        if isinstance(subtree, (CollapseMixin, NestedTree)):
            subtree.expand(pos[-1])

    def expand_all(self):
        self._expand_all(self._tree, self.root)

    def _expand_all(self, tree, pos=None):
        if pos is not None:
            if isinstance(tree, (CollapseMixin, NestedTree)):
                tree.expand_all()
            if len(pos) > 1:
                self._expand_all(tree[pos[0]], pos[1:])
            nextpos = tree.next_position(pos[0])
            if nextpos is not None:
                nentry = tree[nextpos]
                if isinstance(nentry, Tree):
                    self._expand_all(nentry, (nentry.root,))
                self._expand_all(tree, (nextpos,))
            if isinstance(tree, (CollapseMixin, NestedTree)):
                tree.expand_all()

    def is_leaf(self, pos, outmost_only=False):
        return self.first_child_position(pos, outmost_only) is None

    ################################################
    # Tree API
    ################################################
    def parent_position(self, pos):
        candidate_pos = self._parent_position(self._tree, pos)
        # return sanitized path (ensure it points to content, not a subtree)
        return self._sanitize_position(candidate_pos)

    def _parent_position(self, tree, pos):
        candidate_pos = None
        if len(pos) > 1:
            # get the deepest subtree
            subtree_pos = pos[:-1]
            subtree = self._lookup_entry(tree, subtree_pos)
            # get parent for our position in this subtree
            least_pos = pos[-1]
            subparent_pos = subtree.parent_position(least_pos)
            if subparent_pos is not None:
                # in case there is one, we are done, the position we look for
                # is the path up to the subtree plus the local parent position.
                candidate_pos = subtree_pos + (subparent_pos,)
            else:
                # otherwise we recur and look for subtree's parent in the next
                # outer tree
                candidate_pos = self._parent_position(self._tree, subtree_pos)
        else:
            # there is only one position in the path, we return its parent in
            # the outmost tree
            outer_parent = self._tree.parent_position(pos[0])
            if outer_parent is not None:
                # result needs to be valid position (tuple of local positions)
                candidate_pos = outer_parent,
        return candidate_pos

    def first_child_position(self, pos, outmost_only=False):
        childpos = self._first_child_position(self._tree, pos, outmost_only)
        return self._sanitize_position(childpos, self._tree)

    def _first_child_position(self, tree, pos, outmost_only=False):
        childpos = None
        # get content at first path element in outmost tree
        entry = tree[pos[0]]
        if isinstance(entry, Tree) and not outmost_only and len(pos) > 1:
            # this points to a tree and we don't check the outmost tree only
            # recur: get first child in the subtree for remaining path
            subchild = self._first_child_position(entry, pos[1:])
            if subchild is not None:
                # found a childposition, re-append the path up to this subtree
                childpos = (pos[0],) + subchild
                return childpos
            else:
                # continue in the next outer tree only if we do not drop
                # "covered" parts and the position path points to a parent-less
                # position in the subtree.
                if (entry.parent_position(pos[1]) is not None or not
                        self._interpret_covered):
                    return None

        # return the first child of the outmost tree
        outerchild = tree.first_child_position(pos[0])
        if outerchild is not None:
            childpos = outerchild,
        return childpos

    def last_child_position(self, pos, outmost_only=False):
        childpos = self._last_child_position(self._tree, pos, outmost_only)
        return self._sanitize_position(childpos, self._tree)

    def _last_child_position(self, tree, pos, outmost_only=False):
        childpos = None
        # get content at first path element in outmost tree
        entry = tree[pos[0]]
        if isinstance(entry, Tree) and not outmost_only and len(pos) > 1:
            # this points to a tree and we don't check the outmost tree only

            # get last child in the outmost tree if we do not drop "covered"
            # parts and the position path points to a root of the subtree.
            if self._interpret_covered:
                if entry.parent_position(pos[1]) is None:
                    # return the last child of the outmost tree
                    outerchild = tree.last_child_position(pos[0])
                    if outerchild is not None:
                        childpos = outerchild,

            # continue as if we have not found anything yet
            if childpos is None:
                # recur: get last child in the subtree for remaining path
                subchild = self._last_child_position(entry, pos[1:])
                if subchild is not None:
                    # found a childposition, re-prepend path up to this subtree
                    childpos = (pos[0],) + subchild
        else:
            # outmost position element does not point to a tree:
            # return the last child of the outmost tree
            outerchild = tree.last_child_position(pos[0])
            if outerchild is not None:
                childpos = outerchild,
        return childpos

    def _next_sibling_position(self, tree, pos):
        candidate = None
        if len(pos) > 1:
            # if position path does not point to position in outmost tree,
            # first get the subtree as pointed out by first dimension, recur
            # and check if some inner tree already returns a sibling
            subtree = tree[pos[0]]
            subsibling_pos = self._next_sibling_position(subtree, pos[1:])
            if subsibling_pos is not None:
                # we found our sibling, prepend the path up to the subtree
                candidate = pos[:1] + subsibling_pos
            else:
                # no deeper tree has sibling. If inner position is root node
                # the sibling in the outer tree is a valid candidate
                subparent = subtree.parent_position(pos[1])
                if subparent is None:
                    # check if outer tree defines sibling
                    next_sib = tree.next_sibling_position(pos[0])
                    if next_sib is not None:
                        # it has, we found our candidate
                        candidate = next_sib,
                # if the inner position has depth 1, then the first child
                # of its parent in the outer tree can be seen as candidate for
                # this position next sibling. Those live in the shadow of the
                # inner tree and are hidden unless requested otherwise
                elif subtree.parent_position(subparent) is None and \
                        self._interpret_covered:
                    # we respect "covered" stuff and inner position has depth 1
                    # get (possibly nested) first child in outer tree
                    candidate = self._first_child_position(tree, pos[:1])

        else:
            # the position path points to the outmost tree
            # just return its next sibling in the outmost tree
            next_sib = tree.next_sibling_position(pos[0])
            if next_sib is not None:
                candidate = next_sib,
        return candidate

    def next_sibling_position(self, pos):
        candidate = self._next_sibling_position(self._tree, pos)
        return self._sanitize_position(candidate, self._tree)

    def _prev_sibling_position(self, tree, pos):
        candidate = None
        if len(pos) > 1:
            # if position path does not point to position in outmost tree,
            # first get the subtree as pointed out by first dimension, recur
            # and check if some inner tree already returns a sibling
            subtree = tree[pos[0]]
            subsibling_pos = self._prev_sibling_position(subtree, pos[1:])
            if subsibling_pos is not None:
                # we found our sibling, prepend the path up to the subtree
                candidate = pos[:1] + subsibling_pos
            else:
                # no deeper tree has sibling. If inner position is root node
                # the sibling in the outer tree is a valid candidate
                subparent = subtree.parent_position(pos[1])
                if subparent is None:
                    prev_sib = tree.prev_sibling_position(pos[0])
                    if prev_sib is not None:
                        candidate = prev_sib,
                        return candidate
            # my position could be "hidden" by being child of a
            # position pointing to a Tree object (which is then unfolded).
            if self._interpret_covered:
                # we respect "covered" stuff:
                # if parent is Tree, return last child of its (last) root
                parent_pos = self._parent_position(tree, pos)
                if parent_pos is not None:
                    parent = self._lookup_entry(self._tree, parent_pos)
                    if isinstance(parent, Tree):
                        sib = parent.last_sibling_position(parent.root)
                        candidate = parent.last_child_position(sib)
                        if candidate is not None:
                            candidate = parent_pos + (candidate,)
        else:
            # pos points to position in outmost tree
            prev_sib = tree.prev_sibling_position(pos[0])
            if prev_sib is not None:
                candidate = prev_sib,
        # In case our new candidate points to a Tree, pick its last root node
        if candidate is not None:
            entry = self._lookup_entry(tree, candidate)
            if isinstance(entry, Tree):
                candidate = (candidate) + (entry.last_sibling_position(entry.root),)
        return candidate

    def prev_sibling_position(self, pos):
        candidate = self._prev_sibling_position(self._tree, pos)
        return self._sanitize_position(candidate, self._tree)

    def last_decendant(self, pos):
        def lastd(pos):
            c = self.last_child_position(pos)
            if c is not None:
                c = self.last_sibling_position(c)
            return c
        return self._last_in_direction(pos, lastd)
