.. _config.contacts_completion:

Contacts Completion
===================
For each :ref:`account <config.accounts>` you can define an address book by providing a subsection named `abook`.
Crucially, this section needs an option `type` that specifies the type of the address book.
The only types supported at the moment are "shellcommand" and "abook":

.. describe:: shellcommand

    Address books of this type use a shell command in combination with a regular
    expression to look up contacts.

    The value of `command` will be called with the search prefix as only argument for lookups.
    Its output is searched for email-name pairs using the regular expression given as `regexp`,
    which must include named groups "email" and "name" to match the email address and realname parts
    respectively. See below for an example that uses `abook <http://abook.sourceforge.net/>`_

    .. sourcecode:: ini

          [accounts]
            [[youraccount]]
                # ...
                [[[abook]]]
                    type = shellcommand
                    command = abook --mutt-query
                    regexp = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'


    See `here <http://notmuchmail.org/emacstips/#index12h2>`_ for alternative lookup commands.
    The few others I have tested so far are:

    `goobook <http://code.google.com/p/goobook/>`_
        for cached google contacts lookups. Works with the above default regexp

        .. code-block:: ini

          command = goobook query
          regexp = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'

    `nottoomuch-addresses <http://www.iki.fi/too/nottoomuch/nottoomuch-addresses/>`_
        completes contacts found in the notmuch index:

        .. code-block:: ini

          command = nottoomuch-addresses.sh
          regexp = \"(?P<name>.+)\"\s*<(?P<email>.*.+?@.+?)>

    Don't hesitate to send me your custom `regexp` values to list them here.

.. describe:: abook

    Address books of this type directly parse `abooks <http://abook.sourceforge.net/>`_ contact files.
    You may specify a path using the "abook_contacts_file" option, which
    defaults to :file:`~/.abook/addressbook`. To use the default path, simply do this:

    .. code-block:: ini

        [accounts]
        [[youraccount]]
            # ...
            [[[abook]]]
                type = abook

