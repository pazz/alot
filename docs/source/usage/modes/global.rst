.. CAUTION: THIS FILE IS AUTO-GENERATED!


Global commands
---------------
The following commands are available globally:

.. _cmd.global.bclose:

.. describe:: bclose

    close a buffer

    optional arguments
        :---redraw: redraw current buffer after command has finished
        :---force: never ask for confirmation

.. _cmd.global.bnext:

.. describe:: bnext

    focus next buffer


.. _cmd.global.bprevious:

.. describe:: bprevious

    focus previous buffer


.. _cmd.global.buffer:

.. describe:: buffer

    focus buffer with given index

    argument
        buffer index to focus


.. _cmd.global.bufferlist:

.. describe:: bufferlist

    open a list of active buffers


.. _cmd.global.call:

.. describe:: call

    execute python code

    argument
        python command string to call


.. _cmd.global.compose:

.. describe:: compose

    compose a new email

    argument
        None

    optional arguments
        :---sender: sender
        :---template: path to a template message file
        :---tags: comma-separated list of tags to apply to message
        :---subject: subject line
        :---to: recipients
        :---cc: copy to
        :---bcc: blind copy to
        :---attach: attach files
        :---omit_signature: do not add signature
        :---spawn: spawn editor in new terminal

.. _cmd.global.exit:

.. describe:: exit

    shut down cleanly


.. _cmd.global.flush:

.. describe:: flush

    flush write operations or retry until committed


.. _cmd.global.help:

.. describe:: help

    display help for a command (use 'bindings' to display all keybindings
    interpreted in current mode)

    argument
        command or 'bindings'


.. _cmd.global.move:

.. describe:: move

    move focus in current buffer

    argument
        up, down, [half]page up, [half]page down, first, last


.. _cmd.global.namedqueries:

.. describe:: namedqueries

    opens named queries buffer


.. _cmd.global.prompt:

.. describe:: prompt

    prompts for commandline and interprets it upon select

    argument
        initial content


.. _cmd.global.pyshell:

.. describe:: pyshell

    open an interactive python shell for introspection


.. _cmd.global.refresh:

.. describe:: refresh

    refresh the current buffer


.. _cmd.global.reload:

.. describe:: reload

    reload all configuration files


.. _cmd.global.removequery:

.. describe:: removequery

    removes a "named query" from the database

    argument
        alias to remove

    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.global.repeat:

.. describe:: repeat

    repeat the command executed last time


.. _cmd.global.savequery:

.. describe:: savequery

    store query string as a "named query" in the database

    positional arguments
        0: alias to use for query string
        1: query string to store


    optional arguments
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.global.search:

.. describe:: search

    open a new search buffer. Search obeys the notmuch
    :ref:`search.exclude_tags <search.exclude_tags>` setting.

    argument
        search string

    optional arguments
        :---sort: sort order; valid choices are: 'oldest_first','newest_first','message_id','unsorted'

.. _cmd.global.shellescape:

.. describe:: shellescape

    run external command

    argument
        command line to execute

    optional arguments
        :---spawn: run in terminal window
        :---thread: run in separate thread
        :---refocus: refocus current buffer after command has finished

.. _cmd.global.taglist:

.. describe:: taglist

    opens taglist buffer

    optional arguments
        :---tags: tags to display

