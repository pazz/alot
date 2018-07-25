.. _config.options:

Configuration Options
=====================

The following lists all available config options with their type and default values.
The type of an option is used to validate a given value. For instance,
if the type says "boolean" you may only provide "True" or "False" as values in your config file,
otherwise alot will complain on startup. Strings *may* be quoted but do not need to be.

.. include:: alotrc_table

Notmuch options
---------------

The following lists the notmuch options that alot reads.

.. _search.exclude_tags:

.. describe:: search.exclude_tags

     A  list  of tags that will be excluded from search results by
     default. Using an excluded tag in a query will override  that
     exclusion.

    :type: semicolon separated list
    :default: empty list
