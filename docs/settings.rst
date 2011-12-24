Accessing User Settings
=======================

.. module:: alot.settings

There are four types of user settings: notmuchs and alot's config
files, the hooks-file for user provided python code and the mailcap,
defining shellcomands as handlers for files of certain mime types.

Alot sets up :class:`FallbackConfigParser` objects to access the configs
of alot and notmuch`.
Hooks can be accessed via :meth:`AlotConfigParser.get_hook`
and MIME handlers can be looked up using :func:`alot.settings.get_mime_handler`.

+----------------+-----------------------------------+------------------------------+
|     What       |            accessible via         |             Type             |
+================+===================================+==============================+
| alot config    | :obj:`alot.settings.config`       | :class:`AlotConfigParser`    |
+----------------+-----------------------------------+------------------------------+
| notmuch config | :obj:`alot.settings.notmuchconfig`| :class:`FallbackConfigParser`|
+----------------+-----------------------------------+------------------------------+

Through these objects you can access user settings (or their default values
if unset) in the following manner::

    from alot.settings import config, notmuchconfig

    # alot config
    >>> config.getint('general', 'notify_timeout')
    5
    >>> config.getboolean('general', 'show_statusbar')
    True
    >>> config.getstringlist('general', 'displayed_headers')
    [u'From', u'To', u'Cc', u'Bcc', u'Subject']

    # notmuch config
    >>> notmuchconfig.get('user', 'primary_email')
    'patricktotzke@gmail.com'
    >>> notmuchconfig.getboolean('maildir', 'synchronize_flags')
    True

Hooks can be looked up using :meth:`AlotConfigParser.get_hook`.
They are user defined callables that expect to be called with the following parameters:

  :ui: :class:`~alot.ui.UI` -- the initialized main component
  :dbm: :class:`~alot.db.DBManager` -- :obj:`ui.dbman`
  :aman: :class:`~alot.account.AccountManager` -- :obj:`ui.accountman`
  :log: :class:`~logging.Logger` -- :obj:`ui.logger`
  :config: :class:`AlotConfigParser` :obj:`alot.settings.config`

.. autoclass:: FallbackConfigParser
    :members:
.. autoclass:: AlotConfigParser
    :members:
.. autofunction:: get_mime_handler
