
ask_subject = boolean(default=True) # ask for subject when compose

# confirm exit
bug_on_exit = boolean(default=False)

# offset of next focused buffer if the current one gets closed
bufferclose_focus_offset = integer(default=-1)

# number of colours to use
colourmode = option(1, 16, 256, default=256)

# number of spaces used to replace tab characters
tabwidth = integer(default=8)

# templates directory that contains your message templates.
# It will be used if you give `compose --template` a filename without a path prefix.
template_dir = string(default='$XDG_CONFIG_HOME/alot/templates')

# directory containing theme files
themes_dir = string(default=None)

# name of the theme to use
theme = string(default=None)

# fill threadline with message content
display_content_in_threadline = boolean(default=False)

# headers that get displayed by default
displayed_headers = force_list(default=list(From,To,Cc,Bcc,Subject))

# headers that are hidden in envelope buffers by default
envelope_headers_blacklist = force_list(default=list(In-Reply-To,References))

# Replace own email addresses with "me" in author lists
# Uses own addresses and aliases in all configured accounts.
thread_authors_replace_me = boolean(default=True)

# Word to replace own addresses with. Works in combination with
# :ref:`thread_authors_replace_me <thread-authors-replace-me>`
thread_authors_me = string(default='Me')

# set terminal command used for spawning shell commands
terminal_cmd = string(default='x-terminal-emulator -e')

# editor command
# if unset, alot will first try the :envvar:`EDITOR` env variable, then :file:`/usr/bin/editor`
editor_cmd = string(default=None)

# file encoding used by your editor
editor_writes_encoding = string(default='UTF-8')

# use terminal_command to spawn a new terminal for the editor?
# equivalent to always providing the `--spawn` parameter to compose/edit commands
editor_spawn = boolean(default=False)

# call editor in separate thread.
# In case your editor doesn't run in the same window as alot, setting true here
# will make alot non-blocking during edits
editor_in_thread = boolean(default=False)

# Which header fields should be editable in your editor
# used are those that match the whitelist and don't match the blacklist.
# in both cases '*' may be used to indicate all fields.
edit_headers_whitelist = force_list(default=list(*,))

# see :ref:`edit_headers_whitelist <edit-headers-whitelist>`
edit_headers_blacklist = force_list(default=list(Content-Type,MIME-Version,References,In-Reply-To))

# timeout in seconds after a failed attempt to writeout the database is repeated
flush_retry_timeout = integer(default=5)

# where to look up hooks
hooksfile = string(default='~/.config/alot/hooks.py')

# time in secs to display status messages
notify_timeout = integer(default=2)

# display status-bar at the bottom of the screen?
show_statusbar = boolean(default=True)

# timestamp format in `strftime format syntax <http://docs.python.org/library/datetime.html#strftime-strptime-behavior>`_
timestamp_format = string(default=None)

# maximal length of authors string in search mode before it gets truncated
authors_maxlength = integer(default=30)

# how to print messages:
# this specifies a shell command used for printing.
# threads/messages are piped to this command as plain text.
# muttprint/a2ps works nicely
print_cmd = string(default=None)

# initial command when none is given as argument:
initial_command = string(default='search tag:inbox AND NOT tag:killed')

# default sort order of results in a search
search_threads_sort_order = option('oldest_first', 'newest_first', 'message_id', 'unsorted', default='newest_first')

# in case more than one account has an address book:
# Set this to True to make tab completion for recipients during compose only
# look in the abook of the account matching the sender address
complete_matching_abook_only = boolean(default=False)

# shut down when the last buffer gets closed
quit_on_last_bclose = boolean(default=False)

# value of the User-Agent header used for outgoing mails.
# setting this to the empty string will cause alot to omit the header all together.
# The string '{version}' will be replaced by the version string of the running instance.
user_agent = string(default='alot/{version}')

# Suffix of the prompt used when waiting for user input
prompt_suffix = string(default=':')

# Key bindings 
[bindings]
    __many__ = string(default=None)
    [[___many___]]
        __many__ = string(default=None)

[tags]
    # for each tag
    [[__many__]]
        # foreground
        fg = string(default=None)
        # background
        bg = string(default=None)
        # foreground if focused
        focus_fg = string(default=None)
        # background if focused
        focus_bg = string(default=None)
        # don't display at all?
        hidden = boolean(default=False)
        # alternative string representation
        translated = string(default=None)
        # substitution to generate translated from section name
        translation = mixed_list(string, string, default=None)

[accounts]
[[__many__]]
        # your main email address
        address = string

        # used to format the (proposed) From-header in outgoing mails
        realname = string

        # used to clear your addresses/ match account when formatting replies
        aliases = force_list(default=list())

        # sendmail command. This is the shell command used to send out mails via the sendmail protocol
        sendmail_command = string(default='sendmail -t')

        # where to store outgoing mails, e.g. `maildir:///home/you/mail/Sent`.
        # You can use mbox, maildir, mh, babyl and mmdf in the protocol part of the URL.
        #
        # .. note:: If you want to add outgoing mails automatically to the notmuch index
        #           you must use maildir in a path within your notmuch database path.
        sent_box = mail_container(default=None)

        # where to store draft mails, e.g. `maildir:///home/you/mail/Drafts`.
        # You can use mbox, maildir, mh, babyl and mmdf in the protocol part of the URL.
        #
        # .. note:: You will most likely want drafts indexed by notmuch to be able to
        #           later access them within alot. This currently only works for
        #           maildir containers in a path below your notmuch database path.
        draft_box = mail_container(default=None)

        # list of tags to automatically add to outgoing messages
        sent_tags = force_list(default=list('sent'))

        # path to signature file that gets attached to all outgoing mails from this account, optionally
        # renamed to ref:`signature_filename <signature-filename>`.
        signature = string(default=None)

        # attach signature file if set to True, append its content (mimetype text)
        # to the body text if set to False.
        signature_as_attachment = boolean(default=False)

        # signature file's name as it appears in outgoing mails if
        # :ref:`signature_as_attachment <signature-as-attachment>` is set to True
        signature_filename = string(default=None)

        # Outgoing messages will be GPG signed by default if this is set to True.
        sign_by_default = boolean(default=False)

        # The GPG key ID you want to use with this account. If unset, alot will
        # use your default key.
        gpg_key = gpg_key_hint(default=None)

        # address book for this account
        [[[abook]]]
            # type identifier for address book
            type = option('shellcommand', 'abook', default=None)
            # command to lookup contacts in shellcommand abooks
            # it will be called with the lookup prefix as only argument
            command = string(default=None)

            # regular expression used to match name/address pairs in the output of `command`
            # for shellcommand abooks
            regexp = string(default=None)

            # contacts file used for type 'abook' address book
            abook_contacts_file = string(default='~/.abook/addressbook')
