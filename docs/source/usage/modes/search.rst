.. CAUTION: THIS FILE IS AUTO-GENERATED!


Commands in `search` mode
-------------------------
The following commands are available in search mode

.. _cmd.search.sort:

.. describe:: sort

    set sort order

    argument
        sort order. valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.


.. _cmd.search.untag:

.. describe:: untag

    remove tags from all messages in the thread

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.untagsearch:

.. describe:: untagsearch

    remove tags from all messages in threads in the search results

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.retag:

.. describe:: retag

    set tags of all messages in the thread

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.retagsearch:

.. describe:: retagsearch

    set tags of all messages in all threads in the search results

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.refineprompt:

.. describe:: refineprompt

    prompt to change this buffers querystring


.. _cmd.search.tag:

.. describe:: tag

    add tags to all messages in the thread

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.tagsearch:

.. describe:: tagsearch

    add tags to all messages in all threads in the search results

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.refine:

.. describe:: refine

    refine query

    argument
        search string

    optional arguments
        :---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.

.. _cmd.search.retagprompt:

.. describe:: retagprompt

    prompt to retag selected threads' tags


.. _cmd.search.toggletags:

.. describe:: toggletags

    flip presence of tags on this thread.
    A tag is considered present if at least one message contained in this
    thread is tagged with it. In that case this command will remove the tag
    from every message in the thread.
    

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').

.. _cmd.search.toggletagssearch:

.. describe:: toggletagssearch

    flip presence of tags on threads in the search results.
    A tag is considered present if at least one message contained in this
    thread is tagged with it. In that case this command will remove the tag
    from every message in the thread.
    

    argument
        comma separated list of tags

    optional arguments
        :---no-flush: postpone a writeout to the index (Defaults to: 'True').


.. _cmd.search.select:

.. describe:: select

    open thread in a new buffer


