.. CAUTION: THIS FILE IS AUTO-GENERATED!


Commands in `thread` mode
-------------------------
The following commands are available in thread mode:

.. _cmd.thread.bounce:

.. describe:: bounce

    directly re-send selected message


.. _cmd.thread.editnew:

.. describe:: editnew

    edit message in as new

    optional arguments
        :---spawn: open editor in new window

.. _cmd.thread.fold:

.. describe:: fold

    fold message(s)

    argument
        query used to filter messages to affect


.. _cmd.thread.forward:

.. describe:: forward

    forward message

    optional arguments
        :---attach: attach original mail
        :---spawn: open editor in new window

.. _cmd.thread.indent:

.. describe:: indent

    change message/reply indentation

    argument
        None


.. _cmd.thread.move:

.. describe:: move

    move focus in current buffer

    argument
        up, down, [half]page up, [half]page down, first, last,                   parent, first reply, last reply,                   next sibling, previous sibling, next, previous,                   next unfolded, previous unfolded,                   next NOTMUCH_QUERY, previous NOTMUCH_QUERY


.. _cmd.thread.pipeto:

.. describe:: pipeto

    pipe message(s) to stdin of a shellcommand

    argument
        shellcommand to pipe to

    optional arguments
        :---all: pass all messages
        :---format: output format; valid choices are: \`raw\`,\`decoded\`,\`id\`,\`filepath\` (defaults to: 'raw')
        :---separately: call command once for each message
        :---background: don't stop the interface
        :---add_tags: add 'Tags' header to the message
        :---shell: let the shell interpret the command
        :---notify_stdout: display cmd's stdout as notification

.. _cmd.thread.print:

.. describe:: print

    print message(s)

    optional arguments
        :---all: print all messages
        :---raw: pass raw mail string
        :---separately: call print command once for each message
        :---add_tags: add 'Tags' header to the message

.. _cmd.thread.remove:

.. describe:: remove

    remove message(s) from the index

    optional arguments
        :---all: remove whole thread

.. _cmd.thread.reply:

.. describe:: reply

    reply to message

    optional arguments
        :---all: reply to all
        :---list: reply to list
        :---spawn: open editor in new window

.. _cmd.thread.retag:

.. describe:: retag

    set message(s) tags.

    argument
        comma separated list of tags

    optional arguments
        :---all: tag all messages in thread
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.thread.retagprompt:

.. describe:: retagprompt

    prompt to retag selected thread's or message's tags


.. _cmd.thread.save:

.. describe:: save

    save attachment(s)

    argument
        path to save to

    optional arguments
        :---all: save all attachments

.. _cmd.thread.select:

.. describe:: select

    select focussed element:
        - if it is a message summary, toggle visibility of the message;
        - if it is an attachment line, open the attachment


.. _cmd.thread.tag:

.. describe:: tag

    add tags to message(s)

    argument
        comma separated list of tags

    optional arguments
        :---all: tag all messages in thread
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.thread.toggleheaders:

.. describe:: toggleheaders

    display all headers

    argument
        query used to filter messages to affect


.. _cmd.thread.togglesource:

.. describe:: togglesource

    display message source

    argument
        query used to filter messages to affect


.. _cmd.thread.toggletags:

.. describe:: toggletags

    flip presence of tags on message(s)

    argument
        comma separated list of tags

    optional arguments
        :---all: tag all messages in thread
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

.. _cmd.thread.unfold:

.. describe:: unfold

    unfold message(s)

    argument
        query used to filter messages to affect


.. _cmd.thread.untag:

.. describe:: untag

    remove tags from message(s)

    argument
        comma separated list of tags

    optional arguments
        :---all: tag all messages in thread
        :---no-flush: postpone a writeout to the index (defaults to: 'True')

