User Interface
==================

Alot sets up a widget tree and a :class:`mainloop <urwid.main_loop.TwistedEventLoop>`
in the constructor of :class:`alot.ui.UI`. The visible area is
a :class:`urwid.Frame`, where the footer is used as a status line and the body part
displays the currently active :class:`alot.buffers.Buffer`.

To be able to bind keystrokes and translate them to :class:`Commands
<alot.commands.Command>`, keypresses are *not* propagated down the widget tree as is
customary in urwid. Instead, the root widget given to urwids mainloop is a custom wrapper
(:class:`alot.ui.Inputwrap`) that interprets key presses. A dedicated
:class:`~alot.commands.globals.SendKeypressCommand` can be used to trigger
key presses to the wrapped root widget and thereby accessing standard urwid
behaviour.

In order to keep the interface non-blocking and react to events like
terminal size changes, alot makes use of twisted's deferred_ - a
framework that makes it easy to deal with callbacks. Many commands in alot make use of
`inline callbacks`_, which allow you to treat deferred-returning functions almost like
syncronous functions. Consider the following example of a function that prompts for some
input and acts on it:

.. _deferred: http://twistedmatrix.com/documents/current/core/howto/defer.html
.. _`inline callbacks`: http://twistedmatrix.com/documents/8.1.0/api/twisted.internet.defer.html#inlineCallbacks

.. code-block:: python

    from twisted.internet import defer

    @defer.inlineCallbacks
    def greet(ui):  # ui is instance of alot.ui.UI
        name = yield ui.prompt('pls enter your name')
        ui.notify('your name is: ' + name)


:class:`UI` - the main component
-----------------------------------

.. module:: alot.ui
.. autoclass:: UI
    :members:

Buffers
----------

A buffer defines a view to your data. It knows how to render itself, to interpret
keypresses and is visible in the "body" part of the widget frame.
Different modes are defined by subclasses of the following base class.

.. autoclass:: alot.buffers.Buffer
    :members:

Available modes are:

============ ========================================
   Mode       Buffer Subclass
============ ========================================
search       :class:`~alot.buffers.SearchBuffer`
thread       :class:`~alot.buffers.ThreadBuffer`
bufferlist   :class:`~alot.buffers.BufferlistBuffer`
taglist      :class:`~alot.buffers.TagListBuffer`
namedqueries :class:`~alot.buffers.NamedQueriesBuffer`
envelope     :class:`~alot.buffers.EnvelopeBuffer`
============ ========================================

.. automodule:: alot.buffers
    :members: BufferlistBuffer, EnvelopeBuffer, NamedQueriesBuffer, SearchBuffer, ThreadBuffer, TagListBuffer

Widgets
--------
What follows is a list of the non-standard urwid widgets used in alot.
Some of them respect :doc:`user settings <settings>`, themes in particular.

utils
`````
.. automodule:: alot.widgets.utils
    :members:

globals
```````
.. automodule:: alot.widgets.globals
    :members:

bufferlist
``````````
.. automodule:: alot.widgets.bufferlist
    :members:

search
``````
.. automodule:: alot.widgets.search
    :members:

thread
``````
.. automodule:: alot.widgets.thread
    :members:

Completion
----------

:meth:`alot.ui.UI.prompt` allows tab completion using a :class:`~alot.completion.Completer`
object handed as 'completer' parameter. :mod:`alot.completion` defines several
subclasses for different occasions like completing email addresses from an
:class:`~alot.account.AddressBook`, notmuch tagstrings. Some of these actually build on top
of each other; the :class:`~alot.completion.QueryCompleter` for example uses a
:class:`~alot.completion.TagsCompleter` internally to allow tagstring completion after
"is:" or "tag:" keywords when typing a notmuch querystring.

All these classes overide the method :meth:`~alot.completion.Completer.complete`, which
for a given string and cursor position in that string returns
a list of tuples `(completed_string, new_cursor_position)` that are taken to be
the completed values. Note that `completed_string` does not need to have the original
string as prefix.
:meth:`~alot.completion.Completer.complete` may rise :class:`alot.errors.CompletionError`
exceptions.

.. automodule:: alot.completion
    :members:
