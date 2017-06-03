User Settings
=============

.. module:: alot.settings.manager

Alot sets up a :class:`SettingsManager` to access user settings
defined in different places uniformly.
There are four types of user settings:

+------------------------------------+----------------------------------+---------------------------------------------+
| what?                              | location                         | accessible via                              |
+====================================+==================================+=============================================+
| alot config                        | :file:`~/.config/alot/config`    | :meth:`SettingsManager.get`                 |
|                                    | or given by command option `-c`. |                                             |
+------------------------------------+----------------------------------+---------------------------------------------+
| hooks -- user provided python code | :file:`~/.config/alot/hooks.py`  | :meth:`SettingsManager.get_hook`            |
|                                    | or as given by the `hooksfile`   |                                             |
|                                    | config value                     |                                             |
+------------------------------------+----------------------------------+---------------------------------------------+
| notmuch config                     | :file:`~/.notmuch-config` or     | :meth:`SettingsManager.get_notmuch_setting` |
|                                    | given by `$NOTMUCH_CONFIG` or    |                                             |
|                                    | given by command option `-n`     |                                             |
+------------------------------------+----------------------------------+---------------------------------------------+
| mailcap -- defines shellcommands   | :file:`~/.mailcap`               | :meth:`SettingsManager.mailcap_find_match`  |
| to handle mime types               | (:file:`/etc/mailcap`)           |                                             |
+------------------------------------+----------------------------------+---------------------------------------------+


Settings Manager
----------------
.. autoclass:: SettingsManager
    :members:


Errors
------

.. automodule:: alot.settings.errors
    :members:

Utils
-----

.. automodule:: alot.settings.utils
    :members:

Themes
------
.. autoclass:: alot.settings.theme.Theme
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

.. module:: alot.addressbook

.. autoclass:: AddressBook
    :members:

.. module:: alot.addressbook.abook

.. autoclass:: AbookAddressBook
    :members:

.. module:: alot.addressbook.external

.. autoclass:: ExternalAddressbook
