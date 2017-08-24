.. _config.contacts_completion:

Contacts Completion
===================
For each :ref:`account <config.accounts>` you can define an address book by providing a subsection named `abook`.
Crucially, this section needs an option `type` that specifies the type of the address book.
The only types supported at the moment are "shellcommand" and "abook".
Both respect the `ignorecase` option which defaults to `True` and results in case insensitive lookups.

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
                    ignorecase = True


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

    `notmuch-abook <https://github.com/guyzmo/notmuch-abook>`_
        completes contacts found in database of notmuch-abook:

        .. code-block:: ini

          command = notmuch_abook.py lookup
          regexp = ^((?P<name>[^(\\s+\<)]*)\s+<)?(?P<email>[^@]+?@[^>]+)>?$

    `notmuch address <https://notmuchmail.org/manpages/notmuch-address-1/>`_
        Since version `0.19`, notmuch itself offers a subcommand `address`, that
        returns email addresses found in the notmuch index.
        Combined with the `date:` syntax to query for mails within a certain
        timeframe, this allows to search contacts that you've sent emails to
        (output all addresses from the `To`, `Cc` and `Bcc` headers):

        .. code-block:: ini

           command = 'notmuch address --format=json --output=recipients date:1Y.. AND from:my@address.org'
           regexp = '\[?{"name": "(?P<name>.*)", "address": "(?P<email>.+)", "name-addr": ".*"}[,\]]?'
           shellcommand_external_filtering = False

        If you want to search for senders in the `From` header (which should be
        must faster according to `notmuch address docs
        <https://notmuchmail.org/manpages/notmuch-address-1/>`_), then use the
        following command:

        .. code-block:: ini

           command = 'notmuch address --format=json date:1Y..'

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

