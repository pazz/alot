
.. _ask-subject:

.. describe:: ask_subject

    ask for subject when compose

.. _authors-maxlength:

.. describe:: authors_maxlength

    max length of authors line in thread widgets

.. _bufferclose-focus-offset:

.. describe:: bufferclose_focus_offset

    offset of next focused buffer if the current one gets closed

.. _bug-on-exit:

.. describe:: bug_on_exit

    confirm exit

.. _colourmode:

.. describe:: colourmode

    number of colours your terminal supports

.. _complete-matching-abook-only:

.. describe:: complete_matching_abook_only

    in case more than one account has an address book:
    Set this to True to make tab completion for recipients during compose only
    look in the abook of the account matching the sender address

.. _display-content-in-threadline:

.. describe:: display_content_in_threadline

    fill threadline with message content

.. _displayed-headers:

.. describe:: displayed_headers

    headers that get displayed by default

.. _edit-headers-blacklist:

.. describe:: edit_headers_blacklist

    see :ref:`edit_headers_whitelist <edit-headers-whitelist>`

.. _edit-headers-whitelist:

.. describe:: edit_headers_whitelist

    Which header fields should be editable in your editor
    used are those that match the whitelist and don't match the blacklist.
    in both cases '*' may be used to indicate all fields.

.. _editor-cmd:

.. describe:: editor_cmd

    editor command
    if unset, alot will first try the EDITOR env variable, then /usr/bin/editor

.. _editor-in-thread:

.. describe:: editor_in_thread

    call editor in separate thread.
    In case your editor doesn't run in the same window as alot, setting true here
    will make alot non-blocking during edits

.. _editor-spawn:

.. describe:: editor_spawn

    use terminal_command to spawn a new terminal for the editor?

.. _editor-writes-encoding:

.. describe:: editor_writes_encoding

    file encoding used by your editor

.. _envelope-headers-blacklist:

.. describe:: envelope_headers_blacklist

    headers that are hidden in envelope buffers by default

.. _flush-retry-timeout:

.. describe:: flush_retry_timeout

    timeout in secs after a failed attempt to flush is repeated

.. _hooksfile:

.. describe:: hooksfile

    where to look up hooks

.. _initial-command:

.. describe:: initial_command

    initial command when none is given as argument:

.. _notify-timeout:

.. describe:: notify_timeout

    time in secs to display status messages

.. _print-cmd:

.. describe:: print_cmd

    how to print messages:
    this specifies a shell command used pro printing.
    threads/messages are piped to this command as plain text.
    muttprint/a2ps works nicely

.. _quit-on-last-bclose:

.. describe:: quit_on_last_bclose

    shut down when the last buffer gets closed

.. _search-threads-sort-order:

.. describe:: search_threads_sort_order

    default sort order of results in a search

.. _show-statusbar:

.. describe:: show_statusbar

    display status-line?

.. _tabwidth:

.. describe:: tabwidth

    number of spaces used to replace tab characters

.. _template-dir:

.. describe:: template_dir

    templates directory that contains your message templates.
    It will be used if you give `compose --template` a filename without a path prefix.

.. _terminal-cmd:

.. describe:: terminal_cmd

    set terminal command used for spawning shell commands

.. _theme:

.. describe:: theme

    name of the theme to use

.. _themes-dir:

.. describe:: themes_dir

    directory containing theme files

.. _thread-authors-me:

.. describe:: thread_authors_me

    Word to replace own addresses with. Works in combination with
    :ref:`thread_authors_replace_me <thread-authors-replace-me>`

.. _thread-authors-replace-me:

.. describe:: thread_authors_replace_me

    Replace own email addresses with "me" in author lists
    Uses own addresses and aliases in all configured accounts.

.. _timestamp-format:

.. describe:: timestamp_format

    timestamp format in strftime format syntax:
    http://docs.python.org/library/datetime.html#strftime-strptime-behavior

.. _user-agent:

.. describe:: user_agent

    value of the User-Agent header used for outgoing mails.
    setting this to the empty string will cause alot to omit the header all together.
    The string '{version}' will be replaced by the version string of the running instance.
