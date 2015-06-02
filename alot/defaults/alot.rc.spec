
ask_subject = boolean(default=True) # ask for subject when compose

# automatically remove 'unread' tag when focussing messages in thread mode
auto_remove_unread = boolean(default=True)

# prompt for initial tags when compose
compose_ask_tags = boolean(default=False)

# directory prefix for downloading attachments
attachment_prefix = string(default='~')

# timeout in (floating point) seconds until partial input is cleared
input_timeout = float(default=1.0)

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

# What should be considered to be "the thread subject".
# Valid values are:
#
# * 'notmuch' (the default), will use the thread subject from notmuch, which
#   depends on the selected sorting method
# * 'oldest' will always use the subject of the oldest message in the thread as
#   the thread subject
thread_subject = option('oldest', 'notmuch', default='notmuch')

# set terminal command used for spawning shell commands
terminal_cmd = string(default='x-terminal-emulator -e')

# editor command
# if unset, alot will first try the :envvar:`EDITOR` env variable, then :file:`/usr/bin/editor`
editor_cmd = string(default=None)

# file encoding used by your editor
editor_writes_encoding = string(default='UTF-8')

# use terminal_command to spawn a new terminal for the editor?
# equivalent to always providing the `--spawn=yes` parameter to compose/edit commands
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

# timeout in seconds after a failed attempt to writeout the database is
# repeated. Set to 0 for no retry.
flush_retry_timeout = integer(default=5)

# where to look up hooks
hooksfile = string(default='~/.config/alot/hooks.py')

# time in secs to display status messages
notify_timeout = integer(default=2)

# display status-bar at the bottom of the screen?
show_statusbar = boolean(default=True)

# Format of the status-bar in bufferlist mode.
# This is a pair of strings to be left and right aligned in the status-bar that may contain variables:
#
# * `{buffer_no}`: index of this buffer in the global buffer list
# * `{total_messages}`: total numer of messages indexed by notmuch
# * `{pending_writes}`: number of pending write operations to the index
bufferlist_statusbar = mixed_list(string, string, default=list('[{buffer_no}: bufferlist]','{input_queue} total messages: {total_messages}'))

# Format of the status-bar in search mode.
# This is a pair of strings to be left and right aligned in the status-bar.
# Apart from the global variables listed at :ref:`bufferlist_statusbar <bufferlist-statusbar>`
# these strings may contain variables:
#
# * `{querystring}`: search string
# * `{result_count}`: number of matching messages
# * `{result_count_positive}`: 's' if result count is greater than 0.
search_statusbar = mixed_list(string, string, default=list('[{buffer_no}: search] for "{querystring}"','{input_queue} {result_count} of {total_messages} messages'))

# Format of the status-bar in thread mode.
# This is a pair of strings to be left and right aligned in the status-bar.
# Apart from the global variables listed at :ref:`bufferlist_statusbar <bufferlist-statusbar>`
# these strings may contain variables:
#
# * `{tid}`: thread id
# * `{subject}`: subject line of the thread
# * `{authors}`: abbreviated authors string for this thread
# * `{message_count}`: number of contained messages
thread_statusbar = mixed_list(string, string, default=list('[{buffer_no}: thread] {subject}','{input_queue} total messages: {total_messages}'))

# Format of the status-bar in taglist mode.
# This is a pair of strings to be left and right aligned in the status-bar.
# These strings may contain variables listed at :ref:`bufferlist_statusbar <bufferlist-statusbar>`
# that will be substituted accordingly.
taglist_statusbar = mixed_list(string, string, default=list('[{buffer_no}: taglist]','{input_queue} total messages: {total_messages}'))

# Format of the status-bar in envelope mode.
# This is a pair of strings to be left and right aligned in the status-bar.
# Apart from the global variables listed at :ref:`bufferlist_statusbar <bufferlist-statusbar>`
# these strings may contain variables:
#
# * `{to}`: To-header of the envelope
envelope_statusbar = mixed_list(string, string, default=list('[{buffer_no}: envelope]','{input_queue} total messages: {total_messages}'))

# timestamp format in `strftime format syntax <http://docs.python.org/library/datetime.html#strftime-strptime-behavior>`_
timestamp_format = string(default=None)

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

# String prepended to line when quoting
quote_prefix = string(default='> ')

# String prepended to subject header on reply
# only if original subject doesn't start with 'Re:' or this prefix
reply_subject_prefix = string(default='Re: ')

# String prepended to subject header on forward
# only if original subject doesn't start with 'Fwd:' or this prefix
forward_subject_prefix = string(default='Fwd: ')

# Always use the proper realname when constructing "From" headers for replies.
# Set this to False to use the realname string as received in the original message.
reply_force_realname = boolean(default=True)

# Always use the accounts main address when constructing "From" headers for replies.
# Set this to False to use the address string as received in the original message.
reply_force_address = boolean(default=False)

# Always use the proper realname when constructing "From" headers for forwards.
# Set this to False to use the realname string as received in the original message.
forward_force_realname = boolean(default=True)

# Always use the accounts main address when constructing "From" headers for forwards.
# Set this to False to use the address string as received in the original message.
forward_force_address = boolean(default=False)

# Always use the proper realname when constructing "Resent-From" headers for bounces.
# Set this to False to use the realname string as received in the original message.
bounce_force_realname = boolean(default=True)

# Always use the accounts main address when constructing "Resent-From" headers for bounces.
# Set this to False to use the address string as received in the original message.
bounce_force_address = boolean(default=False)

# When group-reply-ing to an email that has the "Mail-Followup-To" header set,
# use the content of this header as the new "To" header and leave the "Cc"
# header empty
honor_followup_to = boolean(default=False)

# When one of the recipients of an email is a subscribed mailing list, set the
# "Mail-Followup-To" header to the list of recipients without yourself
followup_to = boolean(default=False)

# The list of addresses associated to the mailinglists you are subscribed to
mailinglists = force_list(default=list())

# Automatically switch to list reply mode if appropriate
auto_replyto_mailinglist = boolean(default=False)

# prefer plaintext alternatives over html content in multipart/alternative
prefer_plaintext = boolean(default=False)

# In a thread buffer, hide from messages summaries tags that are commom to all
# messages in that thread.
msg_summary_hides_threadwide_tags = boolean(default=True)

# The list of headers to match to determine sending account for a reply.
# Headers are searched in the order in which they are specified here, and the first header
# containing a match is used. If multiple accounts match in that header, the one defined
# first in the account block is used.
reply_account_header_priority = force_list(default=list(From,To,Cc,Envelope-To,X-Envelope-To,Delivered-To))

# Key bindings 
[bindings]
    __many__ = string(default=None)
    [[___many___]]
        __many__ = string(default=None)

[tags]
    # for each tag
    [[__many__]]
        # unfocussed
        normal = attrtriple(default=None)
        # focussed
        focus = attrtriple(default=None)
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

        # a regex for catching further aliases (like + extensions).
        alias_regexp = string(default=None)

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
        # renamed to :ref:`signature_filename <signature-filename>`.
        signature = string(default=None)

        # attach signature file if set to True, append its content (mimetype text)
        # to the body text if set to False.
        signature_as_attachment = boolean(default=False)

        # signature file's name as it appears in outgoing mails if
        # :ref:`signature_as_attachment <signature-as-attachment>` is set to True
        signature_filename = string(default=None)

        # Outgoing messages will be GPG signed by default if this is set to True.
        sign_by_default = boolean(default=False)

	# Alot will try to GPG encrypt outgoing messages by default when this
	# is set to `all` or `trusted`.  If set to `all` the message will be
	# encrypted for all recipients for who a key is available in the key
	# ring.  If set to `trusted` it will be encrypted to all
	# recipients if a trusted key is available for all recipients (one
	# where the user id for the key is signed with a trusted signature).
	#
	# .. note:: If the message will not be encrypted by default you can
	#           still use the :ref:`toggleencrypt
	#           <cmd.envelope.toggleencrypt>`, :ref:`encrypt
	#           <cmd.envelope.encrypt>` and :ref:`unencrypt
	#           <cmd.envelope.unencrypt>` commands to encrypt it.
	# .. note:: The values `True` and `False` are interpreted as `all` and
	#           `none` respectively.  They are kept for backwards
	#           compatibility to give users a change to migrate to the new
	#           option type.  They might become deprecated in future
	#           versions.
        encrypt_by_default = option('all', 'none', 'trusted', 'True', 'False', 'true', 'false', 'Yes', 'No', 'yes', 'no', '1', '0', default='none')

        # The GPG key ID you want to use with this account. If unset, alot will
        # use your default key.
        gpg_key = gpg_key_hint(default=None)

        # address book for this account
        [[[abook]]]
            # type identifier for address book
            type = option('shellcommand', 'abook', default=None)

            # make case-insensitive lookups
            ignorecase = boolean(default=True)

            # command to lookup contacts in shellcommand abooks
            # it will be called with the lookup prefix as only argument
            command = string(default=None)

            # regular expression used to match name/address pairs in the output of `command`
            # for shellcommand abooks
            regexp = string(default=None)

            # contacts file used for type 'abook' address book
            abook_contacts_file = string(default='~/.abook/addressbook')

            # (shellcommand addressbooks)
            # let the external command do the filtering when looking up addresses.
            # If set to True, the command is fired with the given search string
            # as parameter. Otherwise, the command is fired without additional parameters
            # and the result list is filtered according to the search string.
            shellcommand_external_filtering = boolean(default=True)
