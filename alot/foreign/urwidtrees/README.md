Urwid Tree Container API
========================

This is a POC implementation of a new Widget Container API for the [urwid][urwid] toolkit.
Its design goals are

* clear separation classes that define, decorate and display trees of widgets
* representation of trees by local operations on node positions
* easy to use default implementation for simple trees
* Collapses are considered decoration

We propose a `urwid.ListBox`-based widget that display trees where siblings grow vertically and
children horizontally.  This `TreeBox` widget handles key presses to move in the tree and
collapse/expand subtrees if possible.

The choice to define trees by overwriting local position movements allows to
easily define potentially infinite tree structures. See `example4` for how to
walk local file systems.

The overall structure of the API contains three parts:


Structure
---------

`tree.Tree` objects define a tree structure by implementing the local movement methods

    parent_position
    first_child_position
    last_child_position
    next_sibling_position
    prev_sibling_position

Each of which takes and returns a `position` object of arbitrary type (fixed for the Tree)
as done in urwids ListWalker API. Apart from this, a `Tree` is assumed to define a dedicated
position `tree.root` that is used as fallback initially focussed element,
and define the `__getitem__` method to return its content (usually a Widget) for a given position.

Note that `Tree` only defines a tree structure, it does not necessarily have any decoration around
its contained Widgets.

There is a ready made subclass called `SimpleTree` that offers the tree API for a given 
nested tuple structure. If you write your own classes its a good idea to subclass `Tree`
and just overwrite the above mentioned methods as the base class already offers a number of
derivative methods.


Decoration
----------

Is done by using (subclasses of ) `decoration.DecoratedTree`. Objects of this type
wrap around a given `Tree` and themselves behave like a (possibly altered) tree.
Per default, `DecoratedTree` just passes every method on to its underlying tree.
Decoration is done *not* by overwriting `__getitem__`, but by offering two additional
methods

  get_decorated()
  decorate().

`get_decorated(pos)` returns the (decorated) content of the original tree at the given position.
`decorate(pos, widget,..)` decorates the given widget assuming its placed at a given position.
The former is trivially based on the latter, Containers that display `Tree`s use `get_decorated`
instead of `__getitem__` when working on `DecoratedTree`s.

The reason for this slightly odd design choice is that first it makes it easy to read
the original content of a decorated tree: You simply use `dtree[pos]`.
Secondly, this makes it possible to recursively add line decoration when nesting (decorated) Trees.

The module `decoration` offers a few readily usable `DecoratedTree` subclasses that implement
decoration by indentation, arrow shapes and subtree collapsing:
`CollapsibleTree`, `IndentedTree`, `CollapsibleIndentedTree`, `ArrowTree` and `CollapsibleArrowTree`.
Each can be further customized by constructor parameters.


Containers
----------

`widgets.TreeBox` is essentially a `urwid.ListBox` that displays a given `Tree`.
Per default no decoration is used and the widgets of the tree are simply displayed line by line in
depth first order. `TreeBox`'s constructor accepts a `focus` parameter to specify the initially
focussed position. Internally, it uses a `TreeListWalker` to linearize the tree to a list.

`widgets.TreeListWalker` serve as adapter between `Tree` and ListWalker APIs:
They implement the ListWalker API using the data from a given `Tree` in depth-first order.
As such, one can directly pass on a `TreeListWalker` to an `urwid.ListBox` if one doesn't want
to use tree-based focus movement or key bindings for collapsing subtrees.

[urwid]: http://excess.org/urwid/
