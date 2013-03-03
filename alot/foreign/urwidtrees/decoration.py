# Copyright (C) 2013  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
from tree import Tree, SimpleTree
import urwid
import logging

NO_SPACE_MSG = 'too little space for requested decoration'


class TreeDecorationError(Exception):
    pass


class DecoratedTree(Tree):
    """
    :class:`Tree` that wraps around another :class:`Tree` and allows to read
    original content as well as decorated versions thereof.
    """
    def __init__(self, content):
        if not isinstance(content, Tree):
            # do we need this?
            content = SimpleTree(content)
        self._tree = content
        self.root = self._tree.root

    def get_decorated(self, pos):
        """
        return widget that consists of the content of original tree at given
        position plus its decoration.
        """
        return self.decorate(pos, self[pos])

    def decorate(self, pos, widget, is_first=True):
        """
        decorate `widget` according to a position `pos` in the original tree.
        setting `is_first` to False indicates that we are decorating a line
        that is *part* of the (multi-line) content at this position, but not
        the first part. This allows to omit incoming arrow heads for example.
        """
        return widget

    # pass on everything else to the original tree.

    def parent_position(self, pos):
        return self._tree.parent_position(pos)

    def first_child_position(self, pos):
        return self._tree.first_child_position(pos)

    def last_child_position(self, pos):
        return self._tree.last_child_position(pos)

    def next_sibling_position(self, pos):
        return self._tree.next_sibling_position(pos)

    def prev_sibling_position(self, pos):
        return self._tree.prev_sibling_position(pos)

    def __getitem__(self, pos):
        return self._tree[pos]


class CollapseMixin(object):
    """
    Mixin for :class:`Tree` that allows to collapse subtrees.

    This works by overwriting
    :meth:`[first|last]_child_position <first_child_position>`, forcing them to
    return `None` if the given position is considered collapsed. We use a
    (given) callable `is_collapsed` that accepts positions and returns a
    boolean to determine which node is considered collapsed.
    """
    def __init__(self, is_collapsed=lambda pos: False,
                 **kwargs):
        self._initially_collapsed = is_collapsed
        self._divergent_positions = []

    def is_collapsed(self, pos):
        """checks if given position is currently collapsed"""
        collapsed = self._initially_collapsed(pos)
        if pos in self._divergent_positions:
            collapsed = not collapsed
        return collapsed

    # implement functionality by overwriting local position transformations

    # TODO: ATM this assumes we are in a wrapper: it uses self._tree.
    # This is not necessarily true, for example for subclasses of SimpleTree!
    # maybe define this whole class as a wrapper?

    def last_child_position(self, pos):
        if self.is_collapsed(pos):
            return None
        return self._tree.last_child_position(pos)

    def first_child_position(self, pos):
        if self.is_collapsed(pos):
            return None
        return self._tree.first_child_position(pos)

    def collapsible(self, pos):
        return not self._tree.is_leaf(pos)

    def set_position_collapsed(self, pos, is_collapsed):
        if self.collapsible(pos):
            if self._initially_collapsed(pos) == is_collapsed:
                if pos in self._divergent_positions:
                    self._divergent_positions.remove(pos)
            else:
                if pos not in self._divergent_positions:
                    self._divergent_positions.append(pos)

    def toggle_collapsed(self, pos):
        self.set_position_collapsed(pos, not self.is_collapsed(pos))

    def collapse(self, pos):
        self.set_position_collapsed(pos, True)

    def collapse_all(self):
        self.set_collapsed_all(True)

    def expand_all(self):
        self.set_collapsed_all(False)

    def set_collapsed_all(self, is_collapsed):
        self._initially_collapsed = lambda x: is_collapsed
        self._divergent_positions = []

    def expand(self, pos):
        self.set_position_collapsed(pos, False)


class CollapseIconMixin(CollapseMixin):
    """
    Mixin for :classs:`Tree` that allows to allows to collapse subtrees
    and use an indicator icon in line decorations.
    This Mixin adds the ability to construct collapse-icon for a
    position, indicating its collapse status to :class:`CollapseMixin`.
    """
    def __init__(self,
                 is_collapsed=lambda pos: False,
                 icon_collapsed_char='+',
                 icon_expanded_char='-',
                 icon_collapsed_att=None,
                 icon_expanded_att=None,
                 icon_frame_left_char='[',
                 icon_frame_right_char=']',
                 icon_frame_att=None,
                 icon_focussed_att=None,
                 **kwargs):
        """TODO: docstrings"""
        CollapseMixin.__init__(self, is_collapsed, **kwargs)
        self._icon_collapsed_char = icon_collapsed_char
        self._icon_expanded_char = icon_expanded_char
        self._icon_collapsed_att = icon_collapsed_att
        self._icon_expanded_att = icon_expanded_att
        self._icon_frame_left_char = icon_frame_left_char
        self._icon_frame_right_char = icon_frame_right_char
        self._icon_frame_att = icon_frame_att
        self._icon_focussed_att = icon_focussed_att

    def _construct_collapse_icon(self, pos):
        width = 0
        widget = None
        char = self._icon_expanded_char
        charatt = self._icon_expanded_att
        if self.is_collapsed(pos):
            char = self._icon_collapsed_char
            charatt = self._icon_collapsed_att
        if char is not None:

            columns = []
            if self._icon_frame_left_char is not None:
                lchar = self._icon_frame_left_char
                charlen = len(lchar)
                leftframe = urwid.Text((self._icon_frame_att, lchar))
                columns.append((charlen, leftframe))
                width += charlen

            # next we build out icon widget: we feed all markups to a Text,
            # make it selectable (to toggle collapse) if requested
            markup = (charatt, char)
            widget = urwid.Text(markup)
            charlen = len(char)
            columns.append((charlen, widget))
            width += charlen

            if self._icon_frame_right_char is not None:
                rchar = self._icon_frame_right_char
                charlen = len(rchar)
                rightframe = urwid.Text((self._icon_frame_att, rchar))
                columns.append((charlen, rightframe))
                width += charlen

            widget = urwid.Columns(columns)
        return width, widget


class CollapsibleTree(CollapseMixin, DecoratedTree):
    """Undecorated Tree that allows to collapse subtrees"""
    def __init__(self, tree, **kwargs):
        DecoratedTree.__init__(self, tree)
        CollapseMixin.__init__(self, **kwargs)


class IndentedTree(DecoratedTree):
    """Indent tree nodes according to their depth in the tree"""
    def __init__(self, tree, indent=2):
        """
        :param tree: tree of widgets to be displayed
        :type tree: Tree
        :param indent: indentation width
        :type indent: int
        """
        self._indent = indent
        DecoratedTree.__init__(self, tree)

    def decorate(self, pos, widget, is_first=True):
        line = None
        indent = self._tree.depth(pos) * self._indent
        cols = [(indent, urwid.SolidFill(' ')), widget]
        # construct a Columns, defining all spacer as Box widgets
        line = urwid.Columns(cols, box_columns=range(len(cols))[:-1])
        return line


class CollapsibleIndentedTree(CollapseIconMixin, IndentedTree):
    """
    Indent collapsible tree nodes according to their depth in the tree and
    display icons indicating collapse-status in the gaps.
    """
    def __init__(self, walker, icon_offset=1, indent=4, **kwargs):
        """
        :param walker: tree of widgets to be displayed
        :type walker: Tree
        :param indent: indentation width
        :type indent: int
        :param icon_offset: distance from icon to the eginning of the tree
                            node.
        :type icon_offset: int
        """
        self._icon_offset = icon_offset
        IndentedTree.__init__(self, walker, indent=indent)
        CollapseIconMixin.__init__(self, **kwargs)

    def decorate(self, pos, widget, is_first=True):
        """
        builds a list element for given position in the tree.
        It consists of the original widget taken from the Tree and some
        decoration columns depending on the existence of parent and sibling
        positions. The result is a urwid.Culumns widget.
        """
        void = urwid.SolidFill(' ')
        line = None
        cols = []
        depth = self._tree.depth(pos)

        # add spacer filling all but the last indent
        if depth > 0:
            cols.append((depth * self._indent, void)),  # spacer

        # construct last indent
        # TODO
        iwidth, icon = self._construct_collapse_icon(pos)
        available_space = self._indent
        firstindent_width = self._icon_offset + iwidth

        # stop if indent is too small for this decoration
        if firstindent_width > available_space:
            raise TreeDecorationError(NO_SPACE_MSG)

        # add icon only for non-leafs
        is_leaf = self._tree.is_leaf(pos)
        if not is_leaf:
            if icon is not None:
                # space to the left
                cols.append((available_space - firstindent_width,
                             urwid.SolidFill(' ')))
                # icon
                icon_pile = urwid.Pile([('pack', icon), void])
                cols.append((iwidth, icon_pile))
                # spacer until original widget
                available_space = self._icon_offset
            cols.append((available_space, urwid.SolidFill(' ')))
        else:  # otherwise just add another spacer
            cols.append((self._indent, urwid.SolidFill(' ')))

        cols.append(widget)  # original widget ]
        # construct a Columns, defining all spacer as Box widgets
        line = urwid.Columns(cols, box_columns=range(len(cols))[:-1])

        return line


class ArrowTree(IndentedTree):
    """
    Decorates the tree by indenting nodes according to their depth and using
    the gaps to draw arrows indicate the tree structure.
    """
    def __init__(self, walker,
                 indent=3,
                 childbar_offset=0,
                 arrow_hbar_char=u'\u2500',
                 arrow_hbar_att=None,
                 arrow_vbar_char=u'\u2502',
                 arrow_vbar_att=None,
                 arrow_tip_char=u'\u27a4',
                 arrow_tip_att=None,
                 arrow_att=None,
                 arrow_connector_tchar=u'\u251c',
                 arrow_connector_lchar=u'\u2514',
                 arrow_connector_att=None, **kwargs):
        """
        :param walker: tree of widgets to be displayed
        :type walker: Tree
        :param indent: indentation width
        :type indent: int
        """
        IndentedTree.__init__(self, walker, indent)
        self._childbar_offset = childbar_offset
        self._arrow_hbar_char = arrow_hbar_char
        self._arrow_hbar_att = arrow_hbar_att
        self._arrow_vbar_char = arrow_vbar_char
        self._arrow_vbar_att = arrow_vbar_att
        self._arrow_connector_lchar = arrow_connector_lchar
        self._arrow_connector_tchar = arrow_connector_tchar
        self._arrow_connector_att = arrow_connector_att
        self._arrow_tip_char = arrow_tip_char
        self._arrow_tip_att = arrow_tip_att
        self._arrow_att = arrow_att

    def _construct_spacer(self, pos, acc):
        """
        build a spacer that occupies the horizontally indented space between
        pos's parent and the root node. It will return a list of tuples to be
        fed into a Columns widget.
        """
        parent = self._tree.parent_position(pos)
        if parent is not None:
            grandparent = self._tree.parent_position(parent)
            if self._indent > 0 and grandparent is not None:
                parent_sib = self._tree.next_sibling_position(parent)
                draw_vbar = parent_sib is not None and \
                    self._arrow_vbar_char is not None
                space_width = self._indent - 1 * (draw_vbar) - self._childbar_offset
                if space_width > 0:
                    void = urwid.AttrMap(urwid.SolidFill(' '), self._arrow_att)
                    acc.insert(0, ((space_width, void)))
                if draw_vbar:
                    barw = urwid.SolidFill(self._arrow_vbar_char)
                    bar = urwid.AttrMap(barw, self._arrow_vbar_att or
                                        self._arrow_att)
                    acc.insert(0, ((1, bar)))
            return self._construct_spacer(parent, acc)
        else:
            return acc

    def _construct_connector(self, pos):
        """
        build widget to be used as "connector" bit between the vertical bar
        between siblings and their respective horizontab bars leading to the
        arrow tip
        """
        # connector symbol, either L or |- shaped.
        connectorw = None
        connector = None
        if self._tree.next_sibling_position(pos) is not None:  # |- shaped
            if self._arrow_connector_tchar is not None:
                connectorw = urwid.Text(self._arrow_connector_tchar)
        else:  # L shaped
            if self._arrow_connector_lchar is not None:
                connectorw = urwid.Text(self._arrow_connector_lchar)
        if connectorw is not None:
            att = self._arrow_connector_att or self._arrow_att
            connector = urwid.AttrMap(connectorw, att)
        return connector

    def _construct_arrow_tip(self, pos):
        """returns arrow tip as (width, widget)"""
        arrow_tip = None
        width = 0
        if self._arrow_tip_char:
            txt = urwid.Text(self._arrow_tip_char)
            arrow_tip = urwid.AttrMap(
                txt, self._arrow_tip_att or self._arrow_att)
            width = len(self._arrow_tip_char)
        return width, arrow_tip

    def _construct_first_indent(self, pos):
        """
        build spacer to occupy the first indentation level from pos to the
        left. This is separate as it adds arrowtip and sibling connector.
        """
        cols = []
        void = urwid.AttrMap(urwid.SolidFill(' '), self._arrow_att)
        available_width = self._indent

        if self._tree.depth(pos) > 0:
            connector = self._construct_connector(pos)
            if connector is not None:
                width = connector.pack()[0]
                if width > available_width:
                    raise TreeDecorationError(NO_SPACE_MSG)
                available_width -= width
                if self._tree.next_sibling_position(pos) is not None:
                    barw = urwid.SolidFill(self._arrow_vbar_char)
                    below = urwid.AttrMap(barw, self._arrow_vbar_att or
                                          self._arrow_att)
                else:
                    below = void
                # pile up connector and bar
                spacer = urwid.Pile([('pack', connector), below])
                cols.append((width, spacer))

            #arrow tip
            awidth, at = self._construct_arrow_tip(pos)
            if at is not None:
                if awidth > available_width:
                    raise TreeDecorationError(NO_SPACE_MSG)
                available_width -= awidth
                at_spacer = urwid.Pile([('pack', at), void])
                cols.append((awidth, at_spacer))

            # bar between connector and arrow tip
            if available_width > 0:
                barw = urwid.SolidFill(self._arrow_hbar_char)
                bar = urwid.AttrMap(
                    barw, self._arrow_hbar_att or self._arrow_att)
                hb_spacer = urwid.Pile([(1, bar), void])
                cols.insert(1, (available_width, hb_spacer))
        return cols

    def decorate(self, pos, widget, is_first=True):
        """
        builds a list element for given position in the tree.
        It consists of the original widget taken from the Tree and some
        decoration columns depending on the existence of parent and sibling
        positions. The result is a urwid.Culumns widget.
        """
        line = None
        if pos is not None:
            original_widget = widget
            cols = self._construct_spacer(pos, [])

            # Construct arrow leading from parent here,
            # if we have a parent and indentation is turned on
            if self._indent > 0:
                if is_first:
                    indent = self._construct_first_indent(pos)
                    if indent is not None:
                        cols = cols + indent
                else:
                    parent = self._tree.parent_position(pos)
                    if self._indent > 0 and parent is not None:
                        parent_sib = self._tree.next_sibling_position(pos)
                        draw_vbar = parent_sib is not None
                        void = urwid.AttrMap(urwid.SolidFill(' '),
                                             self._arrow_att)
                        if self._childbar_offset > 0:
                            cols.append((self._childbar_offset, void))
                        if draw_vbar:
                            barw = urwid.SolidFill(self._arrow_vbar_char)
                            bar = urwid.AttrMap(
                                barw, self._arrow_vbar_att or self._arrow_att)
                            rspace_width = self._indent - \
                                1 - self._childbar_offset
                            cols.append((1, bar))
                            cols.append((rspace_width, void))
                        else:
                            cols.append((self._indent, void))

            # add the original widget for this line
            cols.append(original_widget)
            # construct a Columns, defining all spacer as Box widgets
            line = urwid.Columns(cols, box_columns=range(len(cols))[:-1])
        return line


class CollapsibleArrowTree(CollapseIconMixin, ArrowTree):
    """Arrow-decoration that allows collapsing subtrees"""
    def __init__(self, treelistwalker, icon_offset=0, indent=5, **kwargs):
        self._icon_offset = icon_offset
        ArrowTree.__init__(self, treelistwalker, indent, **kwargs)
        CollapseIconMixin.__init__(self, **kwargs)

    def _construct_arrow_tip(self, pos):

        cols = []
        overall_width = self._icon_offset

        if self._icon_offset > 0:
            # how often we repeat the hbar_char until width icon_offset is
            # reached
            hbar_char_count = len(self._arrow_hbar_char) / self._icon_offset
            barw = urwid.Text(self._arrow_hbar_char * hbar_char_count)
            bar = urwid.AttrMap(barw, self._arrow_hbar_att or self._arrow_att)
            cols.insert(1, (self._icon_offset, bar))

        # add icon only for non-leafs
        if self.collapsible(pos):
            iwidth, icon = self._construct_collapse_icon(pos)
            if icon is not None:
                cols.insert(0, (iwidth, icon))
                overall_width += iwidth

        # get arrow tip
        awidth, tip = ArrowTree._construct_arrow_tip(self, pos)
        if tip is not None:
            cols.append((awidth, tip))
            overall_width += awidth

        return overall_width, urwid.Columns(cols)
