Accessing User Settings
=======================

.. module:: alot.settings

There are three types of user settings: notmuchs and alot's config
files and the hooks-file for user provided python code.
Alot sets up :class:`Configparser.ConfigParser` objects for the first two
and a :class:`HookManager` object to access hooks:

+----------------+-----------------------------------+------------------------------+
|     What       |            accessible via         |             Type             |
+================+===================================+==============================+
| alot config    | :obj:`alot.settings.config`       | :class:`AlotConfigParser`    |
+----------------+-----------------------------------+------------------------------+
| notmuch config | :obj:`alot.settings.notmuchconfig`| :class:`FallbackConfigParser`|
+----------------+-----------------------------------+------------------------------+
| hooks          | :obj:`alot.settings.hooks`        | :class:`HooksManager`        |
+----------------+-----------------------------------+------------------------------+

Through these objects you can access user settings (or their default values
if unset) in the following manner:

.. code-block:: python

    from alot.settings import config

    timeout_int = config.getint('general', 'notify_timeout')
    showbar_bool = config.getboolean('general', 'show_statusbar')
    header_list = config.getstringlist('general', 'displayed_headers')

    
.. automodule:: alot.settings
  :members:
