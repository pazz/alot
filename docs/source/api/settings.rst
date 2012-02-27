User Settings
=============

.. module:: alot.settings

There are four types of user settings: notmuchs and alot's config
files, the hooks-file for user provided python code and the mailcap,
defining shell comands as handlers for files of certain mime types.
Alot sets up :class:`SettingsManager` objects to access these user settings uniformly.

MIME handlers can be looked up via :meth:`SettingsManager.get_mime_handler`,
config values of alot and notmuch's config are accessible using
:meth:`SettingsManager.get` and :meth:`SettingsManager.get_notmuch_setting`.
These methods return either None or the requested value typed as indicated in
the spec files :file:`alot/defaults/*spec`.

Hooks can be looked up via :meth:`SettingsManager.get_hook`.
They are user defined callables that expect to be called with the following parameters:

  :ui: :class:`~alot.ui.UI` -- the initialized main component
  :dbm: :class:`~alot.db.DBManager` -- :obj:`ui.dbman`

.. autoclass:: SettingsManager
    :members:

Accounts
--------

.. module:: alot.account
.. autoclass:: Account
    :members:
.. autoclass:: SendmailAccount
    :members:

Addressbooks
------------

.. autoclass:: AddressBook
    :members:
.. autoclass:: MatchSdtoutAddressbook
    :members:
.. autoclass:: AbookAddressBook
    :members:
