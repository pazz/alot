..
    CAUTION: THIS FILE IS AUTO-GENERATED
    from the inline comments of specfile defaults/alot.rc.spec.

    If you want to change its content make your changes
    to that spec to ensure they woun't be overwritten later.

.. _ask-subject:

.. describe:: ask_subject


    :type: boolean
    :default: True


.. _authors-maxlength:

.. describe:: authors_maxlength

     maximal length of authors string in search mode before it gets truncated

    :type: integer
    :default: 30


.. _bufferclose-focus-offset:

.. describe:: bufferclose_focus_offset

     offset of next focused buffer if the current one gets closed

    :type: integer
    :default: -1


.. _bug-on-exit:

.. describe:: bug_on_exit

     confirm exit

    :type: boolean
    :default: False


.. _colourmode:

.. describe:: colourmode

     number of colours to use

    :type: option, one of ['1', '16', '256']
    :default: 256


.. _complete-matching-abook-only:

.. describe:: complete_matching_abook_only

     in case more than one account has an address book:
     Set this to True to make tab completion for recipients during compose only
     look in the abook of the account matching the sender address

    :type: boolean
    :default: False


.. _display-content-in-threadline:

.. describe:: display_content_in_threadline

     fill threadline with message content

    :type: boolean
    :default: False


.. _displayed-headers:

.. describe:: displayed_headers

     headers that get displayed by default

    :type: string list
    :default: From, To, Cc, Bcc, Subject


.. _edit-headers-blacklist:

.. describe:: edit_headers_blacklist

     see :ref:`edit_headers_whitelist <edit-headers-whitelist>`

    :type: string list
    :default: Content-Type, MIME-Version, References, In-Reply-To


.. _edit-headers-whitelist:

.. describe:: edit_headers_whitelist

     Which header fields should be editable in your editor
     used are those that match the whitelist and don't match the blacklist.
     in both cases '*' may be used to indicate all fields.

    :type: string list
    :default: *,


.. _editor-cmd:

.. describe:: editor_cmd

     editor command
     if unset, alot will first try the :envvar:`EDITOR` env variable, then :file:`/usr/bin/editor`

    :type: string
    :default: None


.. _editor-in-thread:

.. describe:: editor_in_thread

     call editor in separate thread.
     In case your editor doesn't run in the same window as alot, setting true here
     will make alot non-blocking during edits

    :type: boolean
    :default: False


.. _editor-spawn:

.. describe:: editor_spawn

     use terminal_command to spawn a new terminal for the editor?
     equivalent to always providing the `--spawn` parameter to compose/edit commands

    :type: boolean
    :default: False


.. _editor-writes-encoding:

.. describe:: editor_writes_encoding

     file encoding used by your editor

    :type: string
    :default: `UTF-8`


.. _envelope-headers-blacklist:

.. describe:: envelope_headers_blacklist

     headers that are hidden in envelope buffers by default

    :type: string list
    :default: In-Reply-To, References


.. _flush-retry-timeout:

.. describe:: flush_retry_timeout

     timeout in seconds after a failed attempt to writeout the database is repeated

    :type: integer
    :default: 5


.. _hooksfile:

.. describe:: hooksfile

     where to look up hooks

    :type: string
    :default: `~/.config/alot/hooks.py`


.. _initial-command:

.. describe:: initial_command

     initial command when none is given as argument:

    :type: string
    :default: `search tag:inbox AND NOT tag:killed`


.. _notify-timeout:

.. describe:: notify_timeout

     time in secs to display status messages

    :type: integer
    :default: 2


.. _print-cmd:

.. describe:: print_cmd

     how to print messages:
     this specifies a shell command used for printing.
     threads/messages are piped to this command as plain text.
     muttprint/a2ps works nicely

    :type: string
    :default: None


.. _prompt-suffix:

.. describe:: prompt_suffix

     Suffix of the prompt used when waiting for user input

    :type: string
    :default: `:`


.. _quit-on-last-bclose:

.. describe:: quit_on_last_bclose

     shut down when the last buffer gets closed

    :type: boolean
    :default: False


.. _search-threads-sort-order:

.. describe:: search_threads_sort_order

     default sort order of results in a search

    :type: option, one of ['oldest_first', 'newest_first', 'message_id', 'unsorted']
    :default: newest_first


.. _show-statusbar:

.. describe:: show_statusbar

     display status-bar at the bottom of the screen?

    :type: boolean
    :default: True


.. _tabwidth:

.. describe:: tabwidth

     number of spaces used to replace tab characters

    :type: integer
    :default: 8


.. _template-dir:

.. describe:: template_dir

     templates directory that contains your message templates.
     It will be used if you give `compose --template` a filename without a path prefix.

    :type: string
    :default: `$XDG_CONFIG_HOME/alot/templates`


.. _terminal-cmd:

.. describe:: terminal_cmd

     set terminal command used for spawning shell commands

    :type: string
    :default: `x-terminal-emulator -e`


.. _theme:

.. describe:: theme

     name of the theme to use

    :type: string
    :default: None


.. _themes-dir:

.. describe:: themes_dir

     directory containing theme files

    :type: string
    :default: None


.. _thread-authors-me:

.. describe:: thread_authors_me

     Word to replace own addresses with. Works in combination with
     :ref:`thread_authors_replace_me <thread-authors-replace-me>`

    :type: string
    :default: `Me`


.. _thread-authors-replace-me:

.. describe:: thread_authors_replace_me

     Replace own email addresses with "me" in author lists
     Uses own addresses and aliases in all configured accounts.

    :type: boolean
    :default: True


.. _timestamp-format:

.. describe:: timestamp_format

     timestamp format in `strftime format syntax <http://docs.python.org/library/datetime.html#strftime-strptime-behavior>`_

    :type: string
    :default: None


.. _user-agent:

.. describe:: user_agent

     value of the User-Agent header used for outgoing mails.
     setting this to the empty string will cause alot to omit the header all together.
     The string '{version}' will be replaced by the version string of the running instance.

    :type: string
    :default: `alot/{version}`

