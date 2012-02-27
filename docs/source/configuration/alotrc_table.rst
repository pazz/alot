
.. describe:: ask_subject

    ask for subject when compose

.. describe:: authors_maxlength

    max length of authors line in thread widgets

.. describe:: bufferclose_focus_offset

    offset of next focused buffer if the current one gets closed

.. describe:: bug_on_exit

    confirm exit

.. describe:: colourmode

    number of colours your terminal supports

.. describe:: complete_matching_abook_only

    in case more than one account has an address book:
    Set this to True to make tab-completion for recipients during compose only
    look in the abook of the account matching the sender address

.. describe:: display_content_in_threadline

    fill threadline with message content

.. describe:: displayed_headers

    headers that get displayed by default

.. describe:: edit_headers_blacklist


.. describe:: edit_headers_whitelist

    Which header fields should be editable in your editor
    used are those that match the whitelist and don't match the blacklist.
    in both cases '*' may be used to indicate all fields.

.. describe:: editor_cmd

    editor command
    if unset, alot will first try the EDITOR env variable, then /usr/bin/editor

.. describe:: editor_in_thread

    call editor in separate thread.
    In case your editor doesn't run in the same window as alot, setting true here
    will make alot non-blocking during edits

.. describe:: editor_spawn

    use terminal_command to spawn a new terminal for the editor?

.. describe:: editor_writes_encoding

    file encoding used by your editor

.. describe:: envelope_headers_blacklist

    headers that are hidden in envelope buffers by default

.. describe:: flush_retry_timeout

    timeout in secs after a failed attempt to flush is repeated

.. describe:: hooksfile

    where to look up hooks

.. describe:: initial_command

    initial command when none is given as argument:

.. describe:: notify_timeout

    time in secs to display status messages

.. describe:: print_cmd

    how to print messages:
    this specifies a shell command used pro printing.
    threads/messages are piped to command as plain text.
    muttprint/a2ps works nicely

.. describe:: quit_on_last_bclose

    shut down when the last buffer gets closed

.. describe:: search_threads_sort_order

    default sort order of results in a search

.. describe:: show_statusbar

    display status-line?

.. describe:: tabwidth

    number of spaces used to replace tab characters

.. describe:: template_dir

    templates directory that contains your message templates.
    It will be used if you give `compose --template` a filename without a path prefix.

.. describe:: terminal_cmd

    set terminal command used for spawning shell commands

.. describe:: theme

    name of the theme to use

.. describe:: themes_dir

    directory containing theme files

.. describe:: timestamp_format

    timestamp format in strftime format syntax:
    http://docs.python.org/library/datetime.html#strftime-strptime-behavior

.. describe:: user_agent

    value of the User-Agent header used for outgoing mails.
    setting this to the empty string will cause alot to omit the header all together.
    The string '$VERSION' will be replaced by the version string of the running instance.
