`alot` API overview
====================

The main component is :class:`alot.ui.UI`, which provides methods for user input and notifications,
sets up an urwid `mainloop` and widget tree and maintains the list of active buffers.
Moreover, it integrates different "managers" responsible for core functionalities:

* a :class:`~alot.db.DBManager` to access the email database
* an :class:`~alot.account.AccountManager` to deal with user accounts
* a :class:`~alot.settings.AlotConfigParser` (subclasses :class:`configparserConfigParser`) for user settings
* a :class:`~alot.settings.HookManager` to load custom python code to be used as hooks

All user actions, triggered either by keybindings or the prompt, are given as commandline strings
that are translated into :class:`alot.commands.Command` objects.
Different actions are defined as a subclasses of :class:`~alot.commands.Command`, which live
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

