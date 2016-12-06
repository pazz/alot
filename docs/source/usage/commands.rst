Commands
========

Alot interprets user input as command line strings given via its prompt
or :ref:`bound to keys <config.key_bindings>` in the config.
Command lines are semi-colon separated command strings, each of which
starts with a command name and possibly followed by arguments.


See the sections below for which commands are available in which (UI) mode.
`global` commands are available independently of the mode.


:doc:`modes/global`
    globally available commands
:doc:`modes/search`
    commands available when showing thread search results
:doc:`modes/thread`
    commands available while displaying a thread
:doc:`modes/envelope`
    commands during message composition
:doc:`modes/bufferlist`
    commands while listing active buffers
:doc:`modes/taglist`
    commands while listing all tagstrings present in the notmuch database
:doc:`modes/folders`
    commands available when displaying tree view of maildir folders

.. toctree::
   :maxdepth: 2
   :hidden:

   modes/global
   modes/search
   modes/thread
   modes/envelope
   modes/bufferlist
   modes/taglist
   modes/folders

