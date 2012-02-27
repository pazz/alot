ask_subject = boolean(default=True)  # ask for subject when compose

# confirm exit
bug_on_exit = boolean(default=False)

# offset of next focussed buffer if the current one gets closed
bufferclose_focus_offset = integer(default=-1)

# number of colours your terminal supports
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
displayed_headers = string_list(default=list(From,To,Cc,Bcc,Subject))

# headers that are hidden in envelope buffers by default
envelope_headers_blacklist = string_list(default=list(In-Reply-To,References))

# set terminal command used for spawning shell commands
terminal_cmd = string(default='x-terminal-emulator -e')

# editor command
# if unset, alot will first try the EDITOR env variable, then /usr/bin/editor
editor_cmd = string(default=None)

# file encoding used by your editor
editor_writes_encoding = string(default='UTF-8')

# use terminal_command to spawn a new terminal for the editor?
editor_spawn = boolean(default=False)

# call editor in separate thread.
# In case your editor doesn't run in the same window as alot, setting true here
# will make alot non-blocking during edits
editor_in_thread = boolean(default=False)

# Which header fields should be editable in your editor
# used are those that match the whitelist and don't macht the blacklist.
# in both cases '*' may be used to indicate all fields.
edit_headers_whitelist = string_list(default=list(*,))
edit_headers_blacklist = string_list(default=list(Content-Type,MIME-Version,References,In-Reply-To))

# timeout in secs after a failed attempt to flush is repeated
flush_retry_timeout = integer(default=5)

# where to look up hooks
hooksfile = string(default='~/.config/alot/hooks.py')

# time in secs to display status messages
notify_timeout = integer(default=2)

# display statusline?
show_statusbar = boolean(default=True)

# timestamp format in strftime format syntax:
# http://docs.python.org/library/datetime.html#strftime-strptime-behavior
timestamp_format = string(default=None)

# max length of authors line in thread widgets
authors_maxlength = integer(default=30)

# how to print messages:
# this specifies a shellcommand used pro printing.
# threads/messages are piped to this as plaintext.
# muttprint/a2ps works nicely
print_cmd = string(default=None)

# initial command when none is given as argument:
initial_command = string(default='search tag:inbox AND NOT tag:killed')

# default sort order of results in a search
search_threads_sort_order = option('oldest_first', 'newest_first', 'message_id', 'unsorted', default='newest_first')

# in case more than one account has an address book:
# Set this to True to make tabcompletion for recipients during compose only
# look in the abook of the account matching the sender address
complete_matching_abook_only = boolean(default=False)

# shut down when the last buffer gets closed
quit_on_last_bclose = boolean(default=False)

# value of the User-Agent header used for outgoing mails.
# setting this to the empty string will cause alot to omit the header all together.
# The string '$VERSION' will be replaced by the version string of the running instance.
user_agent = string(default='alot/$VERSION')

# Keybindings 
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
        # foreground if focussed
        focus_fg = string(default=None)
        # background if focussed
        focus_bg = string(default=None)
        # don't display at all?
        hidden = boolean(default=False)
        # alternative string representation
        translated = string(default=None)
        # substitution to generate translated from section name
        translation = mixed_list(string, string, default=None)

[accounts]
[[__many__]]
        # your email address
        address = string

        # used to format the (proposed) From-header in outgoing mails
        realname = string

        # used to clear your addresses/ match account when formating replies
        aliases = string_list(default=list())

        # how to send mails
        sendmail_command = string(default='sendmail')

        # specifies the mailbox where you want outgoing mails to be stored after successfully sending them, e.g. 
        # where to store outgoing mail, e.g. `maildir:///home/you/mail//Sent`
        # You can use mbox, maildir, mh, babyl and mmdf in the protocol part of the url.
        sent_box = string(default=None)

        # how to tag sent mails.
        sent_tags = string_list(default=list('sent'))

        # path to signature file that gets attached to all outgoing mails from this account, optionally
        # renamed to `signature_filename`.
        signature = string(default=None)

        # attach signature file if set to True, append its content (mimetype text)
        # to the body text if set to False. Defaults to False.
        signature_as_attachment = boolean(default=False)

        # signature file's name as it appears in outgoing mails if
        # signature_as_attachment is set to True
        signature_filename = string(default=None)


        # address book for this account
        [[[abook]]]
            # type identifier for addressbook
            type = option('shellcommand', 'abook', default=None)
            # command to lookup contacts in shellcommand abooks
            # it will be called with the lookup prefix as only argument
            command = string(default=None)

            # regular expression used to match name/address pairs in the output of `command`
            # for shellcommand abooks
            regexp = string(default=None)

            # contacts file used for type 'abook' addressbook
            abook_contacts_file = string(default='~/.abook/addressbook')
