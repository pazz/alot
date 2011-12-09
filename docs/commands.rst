Commands
=========

.. module:: alot.commands

User actions are given as alot commandline strings that get interpreted
by :func:`commandfactory` which returns a :class:`Command` object
representing the action. Commands can then be triggered by
:meth:`alot.ui.UI.apply_command`.

.. Note:: 

    that the return value
    of :func:`commandfactory` depends on the current *mode* the user interface is in.
    The mode identifier is a string that is uniquely defined by the currently focussed
    :class:`~alot.buffers.Buffer`.

Specific actions are defined as subclasses of :class:`Command` and can be registered
to a global command pool using the :class:`registerCommand` decorator.

.. note::

    The names of the commands available to the user in any given mode do not correspond
    one-to-one to these subclasses. You canregister a Command multiple times under different
    names, with different forced constructor parameters and so on. See for instance the
    definition of BufferFocusCommand in 'commands/globals.py'::

        @registerCommand(MODE, 'bprevious', forced={'offset': -1},
                         help='focus previous buffer')
        @registerCommand(MODE, 'bnext', forced={'offset': +1},
                         help='focus next buffer')
        class BufferFocusCommand(Command):
            ...

.. autoclass:: Command
    :members:
    
.. autoclass:: CommandParseError
.. autoclass:: CommandArgumentParser
.. autofunction:: commandfactory
.. autofunction:: lookup_command
.. autofunction:: lookup_parser
.. autoclass:: registerCommand


Globals
--------

.. automodule:: alot.commands.globals
  :members:

Envelope
--------

.. automodule:: alot.commands.envelope
  :members:

Bufferlist
----------

.. automodule:: alot.commands.bufferlist
  :members:

Search
--------

.. automodule:: alot.commands.search
  :members:

Taglist
--------

.. automodule:: alot.commands.taglist
  :members:

Thread
--------

.. automodule:: alot.commands.thread
  :members:
