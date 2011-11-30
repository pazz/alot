`alot` API overview
====================

.. module:: alot

The main component is :class:`alot.ui.UI`, which provides methods for user input and notifications,
sets up an urwid `mainloop` and widget tree and maintains the list of active buffers.
Moreover, it integrates different "managers" responsible for core functionalities:

* a :class:`~db.DBManager` to access the email database
* an :class:`~account.AccountManager` to deal with user accounts
* a :class:`~settings.AlotConfigParser` (subclasses :class:`configparser.ConfigParser`) for user settings
* a :class:`~settings.HookManager` to load custom python code to be used as hooks

All user actions, triggered either by keybindings or the prompt, are given as commandline strings
that are translated into :class:`commands.Command` objects by
:func:`commands.commandfactory` and applied by :meth:`ui.UI.apply_command`.
Different actions are defined as a subclasses of :class:`~commands.Command`, which live
in `alot/commands/MODE.py`, where MODE is the name of the mode (:class:`Buffer` type) they
are used in.

Contents:

.. toctree::
   :maxdepth: 1

   database
   interface
   settings
   accounts
   utils
   commands
   

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

