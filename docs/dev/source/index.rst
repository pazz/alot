`alot` Developer Manual
***********************

.. module:: alot

Birds eye on alot internals
===========================
The main component is :class:`alot.ui.UI`, which provides methods for user input and notifications,
sets up an :mod:`urwid` :class:`mainloop <urwid.main_loop.TwistedEventLoop>` and widget tree and
maintains the list of active buffers. Moreover, it integrates different "managers" responsible for
core functionalities:

* a :class:`~db.DBManager` to access the email database
* an :class:`~account.AccountManager` to deal with user accounts
* a :class:`~settings.AlotConfigParser` (subclasses :class:`configparser.ConfigParser`) for user settings

Every user action, triggered either by keybindings or as input to the commandprompt, is
given as commandline string that gets :func:`translated <commands.commandfactory>`
to a :class:`~commands.Command` which is then :meth:`applied <ui.UI.apply_command>`.
Different actions are defined as a subclasses of :class:`~commands.Command`, which live
in `alot/commands/MODE.py`, where MODE is the name of the mode (:class:`Buffer` type) they
are used in.

Contributing
============

Development is coordinated entirely via the projects `github page <https://github.com/pazz/alot>`_
especially the `issue tracker <https://github.com/pazz/alot/issues>`_.
Current HEAD can be found in branch `testing` from `git@github.com:pazz/alot.git`.

You can send patches to notmuch's mailing list but pull requests on github are preferred.
Here are a few more things you should know and check before you send pull requests:

* Follow :pep:`8`. This means in particular a maximum linewidth of *79* and no trailing
  white spaces. If in doubt, use an `automatic tool <http://pypi.python.org/pypi/pep8>`_
  to verify your code.

* Document! Needless to say, we want readable and well documented code. Moreover,

  * use `sphinx directives <http://sphinx.pocoo.org/rest.html>`_ to document
    the parameters and return values of your methods so that we maintain up-to-date API docs.
  * Make sure your patch doesn't break the API docs. The build service at `readthedocs.org <http:alot.rtfd.org>`_
    is fragile when it comes to new import statements in our code.
  * If you implemented a new feature, update the user manual in :file:`/docs/user` accordingly.


Contents
========

.. toctree::
   :maxdepth: 1

   database
   interface
   settings
   accounts
   utils
   commands
