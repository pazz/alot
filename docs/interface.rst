User Interface
==================

In order to keep the interface non-blocking, alot makes use of 
twisted's deferred - a framework that makes it easy to deal with callbacks.
See `here <http://twistedmatrix.com/documents/current/core/howto/defer.html>`_
for an intro.

Many commands in alot make use of a construct called 
`inline callbacks <http://twistedmatrix.com/documents/8.1.0/api/twisted.internet.defer.html#inlineCallbacks>`_, which allows you to treat deferred-returning functions almost like syncronous functions. Consider the following example of a function that prompts for some input and acts on it:

.. code-block:: python

    from twisted.internet import defer
    
    @defer.inlineCallbacks
    def greet(ui):  # ui is instance of alot.ui.UI
        name = yield ui.prompt(prefix='pls enter your name>')
        ui.notify('your name is: ' + name)



:class:`UI`
---------------------

.. module:: alot.ui
.. autoclass:: UI

    .. autoattribute:: buffers
    .. autoattribute:: current_buffer
    .. autoattribute:: dbman
    .. autoattribute:: logger
    .. autoattribute:: accountman

    .. automethod:: prompt
    .. automethod:: choice
    .. automethod:: notify
    .. automethod:: clear_notify
    .. automethod:: buffer_open
    .. automethod:: buffer_focus
    .. automethod:: buffer_close
    .. automethod:: get_buffers_of_type


Buffers
---------------------
TODO: describe use of buffers, link to subclasses


Widgets
--------
non-standart urwid widgets used throughout alot
