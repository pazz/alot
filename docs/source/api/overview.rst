Overview
========

The main component is :class:`alot.ui.UI`, which provides methods for user input and notifications, sets up the widget
tree and maintains the list of active buffers.
When you start up alot, :file:`init.py` initializes logging, parses settings and commandline args
and instantiates the :class:`UI <alot.ui.UI>` instance of that gets passes around later.
From its constructor this instance starts the :mod:`urwid` :class:`mainloop <urwid.main_loop.TwistedEventLoop>`
that takes over.

Apart from the central :class:`UI <alot.ui.UI>`, there are two other "managers" responsible for
core functionalities, also set up in :file:`init.py`:

* :attr:`ui.dbman <alot.ui.UI.dbman>`: a :class:`DBManager <alot.db.DBManager>` to access the email database and
* :attr:`alot.settings.settings`: a :class:`SettingsManager <alot.settings.SettingsManager>` oo access user settings

Every user action, triggered either by key bindings or via the command prompt, is
given as commandline string that gets :func:`translated <alot.commands.commandfactory>`
to a :class:`Command <alot.commands.Command>` object which is then :meth:`applied <alot.ui.UI.apply_command>`.
Different actions are defined as a subclasses of :class:`Command <alot.commands.Command>`, which live
in :file:`alot/commands/MODE.py`, where MODE is the name of the mode (:class:`Buffer <alot.buffers.Buffer>` type) they
are used in.

