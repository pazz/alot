.. CAUTION: THIS FILE IS AUTO-GENERATED!


Global Commands
---------------
The following commands are available globally

.. _cmd.global.bclose:

.. describe:: bclose

    close a buffer

    optional arguments
        :---redraw: redraw current buffer after command has finished.
        :---force: never ask for confirmation.

.. _cmd.global.bprevious:

.. describe:: bprevious

    focus previous buffer


.. _cmd.global.search:

.. describe:: search

    open a new search buffer. Search obeys the notmuch
    :ref:`search.exclude_tags <search.exclude_tags>` setting.

    argument
        search string

    optional arguments
        :---sort: sort order. Valid choices are: \`oldest_first\`,\`newest_first\`,\`message_id\`,\`unsorted\`.

.. _cmd.global.repeat:

.. describe:: repeat

    Repeats the command executed last time


.. _cmd.global.prompt:

.. describe:: prompt

    prompts for commandline and interprets it upon select

    argument
        initial content


.. _cmd.global.help:

.. describe:: help

    display help for a command. Use 'bindings' to display all keybings
    interpreted in current mode.'

    argument
        command or 'bindings'


.. _cmd.global.buffer:

.. describe:: buffer

    focus buffer with given index

    argument
        buffer index to focus


.. _cmd.global.move:

.. describe:: move

    move focus in current buffer

    argument
        up, down, [half]page up, [half]page down, first, last


.. _cmd.global.shellescape:

.. describe:: shellescape

    run external command

    argument
        command line to execute

    optional arguments
        :---spawn: run in terminal window.
        :---thread: run in separate thread.
        :---refocus: refocus current buffer after command has finished.

.. _cmd.global.refresh:

.. describe:: refresh

    refresh the current buffer


.. _cmd.global.reload:

.. describe:: reload

    Reload all configuration files


.. _cmd.global.pyshell:

.. describe:: pyshell

    open an interactive python shell for introspection


.. _cmd.global.compose:

.. describe:: compose

    compose a new email

    argument
        None

    optional arguments
        :---sender: sender.
        :---template: path to a template message file.
        :---subject: subject line.
        :---to: recipients.
        :---cc: copy to.
        :---bcc: blind copy to.
        :---attach: attach files.
        :---omit_signature: do not add signature.
        :---spawn: spawn editor in new terminal.

.. _cmd.global.exit:

.. describe:: exit

    Shut down cleanly.

    The _prompt variable is for internal use only, it's used to control
    prompting to close without sending, and is used by the BufferCloseCommand
    if settings change after yielding to the UI.
    


.. _cmd.global.flush:

.. describe:: flush

    flush write operations or retry until committed


.. _cmd.global.bufferlist:

.. describe:: bufferlist

    open a list of active buffers


.. _cmd.global.call:

.. describe:: call

    Executes python code

    argument
        python command string to call


.. _cmd.global.bnext:

.. describe:: bnext

    focus next buffer


.. _cmd.global.taglist:

.. describe:: taglist

    opens taglist buffer

    optional arguments
        :---tags: tags to display.

