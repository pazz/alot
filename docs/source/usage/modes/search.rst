.. CAUTION: THIS FILE IS AUTO-GENERATED!


Commands in 'search' mode
-------------------------
The following commands are available in search mode:

.. _cmd.search.move:

.. describe:: move

    move focus in search buffer

    argument
        last


.. _cmd.search.refine:

.. describe:: refine

    refine query

    argument
        search string

    optional arguments
        :---sort: sort order; valid choices are: 'oldest_first','newest_first','message_id','unsorted'

.. _cmd.search.refineprompt:

.. describe:: refineprompt

    prompt to change this buffers querystring


.. _cmd.search.retag:

.. describe:: retag

    set tags to all messages in the selected thread

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')
        :---all: retag all messages that match the current query

.. _cmd.search.retagprompt:

.. describe:: retagprompt

    prompt to retag selected thread's or message's tags


.. _cmd.search.savequery:

.. describe:: savequery

    store query string as a "named query" in the database. This falls back to the current search query in search buffers.

    positional arguments
        0: alias to use for query string
        1: query string to store


    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.search.select:

.. describe:: select

    open thread in a new buffer


.. _cmd.search.sort:

.. describe:: sort

    set sort order

    argument
        sort order; valid choices are: 'oldest_first','newest_first','message_id','unsorted'


.. _cmd.search.tag:

.. describe:: tag

    add tags to all messages in the selected thread

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')
        :---all: tag all messages that match the current search query

.. _cmd.search.toggletags:

.. describe:: toggletags

    flip presence of tags on the selected thread: a tag is considered present and will be removed if at least one message in this thread is tagged with it

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.search.untag:

.. describe:: untag

    remove tags from all messages in the selected thread

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')
        :---all: untag all messages that match the current query

