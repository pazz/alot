.. _config.hooks:

Hooks
=====
Hooks are python callables that live in a module specified by `hooksfile` in the
config. Per default this points to :file:`~/.config/alot/hooks.py`.

.. rubric:: Pre/Post Command Hooks

For every :ref:`COMMAND <usage.commands>` in mode :ref:`MODE <modes>`, the callables :func:`pre_MODE_COMMAND` and :func:`post_MODE_COMMAND`
-- if defined -- will be called before and after the command is applied respectively. The signature for the
pre-`send` hook in envelope mode for example looks like this:

.. py:function:: pre_envelope_send(ui=None, dbm=None)

    :param ui: the main user interface
    :type ui: :class:`alot.ui.UI`
    :param dbm: a database manager
    :type dbm: :class:`alot.db.manager.DBManager`

Consider this pre-hook for the exit command, that logs a personalized goodbye message::

    import logging
    from alot.settings import settings
    def pre_global_exit(ui, dbm):
        accounts = settings.get_accounts()
        if accounts:
            logging.info('goodbye, %s!' % accounts[0].realname)
        else:
            logging.info('goodbye!')

.. rubric:: Other Hooks

Apart from command pre- and posthooks, the following hooks will be interpreted:

.. py:function:: reply_prefix(realname, address, timestamp[, ui= None, dbm=None])

    Is used to reformat the first indented line in a reply message.
    This defaults to 'Quoting %s (%s)\n' % (realname, timestamp)' unless this hook is defined

    :param realname: name or the original sender
    :type realname: str
    :param address: address of the sender
    :type address: str
    :param timestamp: value of the Date header of the replied message
    :type timestamp: :obj:`datetime.datetime`
    :rtype: string

.. py:function:: forward_prefix(realname, address, timestamp[, ui= None, dbm=None])

    Is used to reformat the first indented line in a inline forwarded message.
    This defaults to 'Forwarded message from %s (%s)\n' % (realname, timestamp)' if this hook is undefined

    :param realname: name or the original sender
    :type realname: str
    :param address: address of the sender
    :type address: str
    :param timestamp: value of the Date header of the replied message
    :type timestamp: :obj:`datetime.datetime`
    :rtype: string

.. py:function:: pre_edit_translate(bodytext[, ui= None, dbm=None])

    used to manipulate a messages bodytext *before* the editor is called.

    :param bodytext: text representation of mail body as displayed in the interface and as sent to the editor
    :type bodytext: str
    :rtype: str

.. py:function:: post_edit_translate(bodytext[, ui= None, dbm=None])

    used to manipulate a messages bodytext *after* the editor is called

    :param bodytext: text representation of mail body as displayed in the interface and as sent to the editor
    :type bodytext: str
    :rtype: str

.. py:function:: text_quote(message)

    used to transform a message into a quoted one

    :param message: message to be quoted
    :type message: str
    :rtype: str

.. py:function:: timestamp_format(timestamp)

    represents given timestamp as string

    :param bodytext: timestamp to represent
    :type timestamp: `datetime`
    :rtype: str

.. py:function:: touch_external_cmdlist(cmd, shell=shell, spawn=spawn, thread=thread)

    used to change external commands according to given flags shortly
    before they are called.

    :param cmd: command to be called
    :type cmd: list of str
    :param shell: is this to be interpreted by the shell?
    :type shell: bool
    :param spawn: should be spawned in new terminal/environment
    :type spawn: bool
    :param threads: should be called in new thread
    :type thread: bool
    :returns: triple of amended command list, shell and thread flags
    :rtype: list of str, bool, bool

.. py:function:: reply_subject(subject)

    used to reformat the subject header on reply

    :param subject: subject to reformat
    :type subject: str
    :rtype: str

.. py:function:: forward_subject(subject)

    used to reformat the subject header on forward

    :param subject: subject to reformat
    :type subject: str
    :rtype: str

.. py:function:: pre_buffer_open(ui= None, dbm=None, buf=buf)

    run before a new buffer is opened

    :param buf: buffer to open
    :type buf: alot.buffer.Buffer

.. py:function:: post_buffer_open(ui=None, dbm=None, buf=buf)

    run after a new buffer is opened

    :param buf: buffer to open
    :type buf: alot.buffer.Buffer

.. py:function:: pre_buffer_close(ui=None, dbm=None, buf=buf)

    run before a buffer is closed

    :param buf: buffer to open
    :type buf: alot.buffer.Buffer

.. py:function:: post_buffer_close(ui=None, dbm=None, buf=buf, success=success)

    run after a buffer is closed

    :param buf: buffer to open
    :type buf: alot.buffer.Buffer
    :param success: true if successfully closed buffer
    :type success: boolean

.. py:function:: pre_buffer_focus(ui=None, dbm=None, buf=buf)

    run before a buffer is focused

    :param buf: buffer to open
    :type buf: alot.buffer.Buffer

.. py:function:: post_buffer_focus(ui=None, dbm=None, buf=buf, success=success)

    run after a buffer is focused

    :param buf: buffer to open
    :type buf: alot.buffer.Buffer
    :param success: true if successfully focused buffer
    :type success: boolean
