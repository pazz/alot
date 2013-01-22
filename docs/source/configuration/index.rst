.. _configuration:

*************
Configuration
*************

Alot reads a config file in "INI" syntax:
It consists of key-value pairs that use "=" as separator and '#' is comment-prefixes.
Sections and subsections are defined using square brackets.

The default location for the config file is :file:`~/.config/alot/config`.

All configs are optional, but if you want to send mails you need to specify at least one
:ref:`account <config.accounts>` in your config.

.. toctree::
   :maxdepth: 2

   config_options
   accounts
   contacts_completion
   key_bindings
   hooks
   theming
