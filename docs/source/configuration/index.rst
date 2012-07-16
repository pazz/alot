.. _configuration:

*************
Configuration
*************

Alot reads a config file in "INI" syntax:
It consists of key-value pairs that use "=" as separator and '#' is comment-prefixes.
Sections and subsections are defined using square brackets.

The default location for the config file is :file:`~/.config/alot/config`. If
upon startup this file is not found, a small default configuration (containing
mostly standard key bindings) will be copied in its place.

All configs are optional, but if you want to send mails you need to specify at least one
:ref:`account <account>` in your config.


Config options
==============

The following lists all available config options with their type and default values.
The type of an option is used to validate a given value. For instance,
if the type says "boolean" you may only provide "True" or "False" as values in your config file,
otherwise alot will complain on startup. Strings *may* be quoted but do not need to be.

.. include:: alotrc_table.rst

.. _account:

Accounts
========
In order to be able to send mails, you have to define at least one account subsection in your config:
There needs to be a section "accounts", and each subsection, indicated by double square brackets defines an account.

Here is an example configuration::

    [accounts]
        [[work]]
            realname = Bruce Wayne
            address = b.wayne@wayneenterprises.com
            gpg_key = D7D6C5AA
            sendmail_command = msmtp --account=wayne -t
            sent_box = maildir:///home/bruce/mail/work/Sent
            draft_box = maildir:///home/bruce/mail/work/Drafts

        [[secret]]
            realname = Batman
            address = batman@batcave.org
            aliases = batman@batmobile.org,
            sendmail_command = msmtp --account=batman -t
            signature = ~/.batman.vcf
            signature_as_attachment = True

.. warning::

  Sending mails is only supported via a sendmail shell command for now. If you want
  to use a sendmail command different from `sendmail -t`, specify it as `sendmail_command`.

The following entries are interpreted at the moment:

.. include:: accounts_table.rst


Contacts Completion
===================
For each :ref:`account <account>` you can define an address book by providing a subsection named `abook`.
Crucially, this section needs an option `type` that specifies the type of the address book.
The only types supported at the moment are "shellcommand" and "abook":

.. describe:: shellcommand

    Address books of this type use a shell command in combination with a regular
    expression to look up contacts.

    The value of `command` will be called with the search prefix as only argument for lookups.
    Its output is searched for email-name pairs using the regular expression given as `regexp`,
    which must include named groups "email" and "name" to match the email address and realname parts
    respectively. See below for an example that uses `abook <http://abook.sourceforge.net/>`_::

        [accounts]
        [[youraccount]]
            ...
            [[[abook]]]
                type = shellcommand
                command = abook --mutt-query
                regexp = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'

    See `here <http://notmuchmail.org/emacstips/#index12h2>`_ for alternative lookup commands.
    The few others I have tested so far are:

    `goobook <http://code.google.com/p/goobook/>`_
        for cached google contacts lookups. Works with the above default regexp::

          command = goobook query
          regexp = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'

    `nottoomuch-addresses <http://www.iki.fi/too/nottoomuch/nottoomuch-addresses/>`_
        completes contacts found in the notmuch index::

          command = nottoomuch-addresses.sh
          regexp = \"(?P<name>.+)\"\s*<(?P<email>.*.+?@.+?)>

    Don't hesitate to send me your custom `regexp` values to list them here.

.. describe:: abook

    Address books of this type directly parse `abooks <http://abook.sourceforge.net/>`_ contact files.
    You may specify a path using the "abook_contacts_file" option, which
    defaults to :file:`~/.abook/addressbook`. To use the default path, simply do this::

        [accounts]
        [[youraccount]]
            ...
            [[[abook]]]
                type = abook

.. _key_bindings:

Key Bindings
============
If you want to bind a command to a key you can do so by adding the pair to the
`[bindings]` section. This will introduce a *global* binding, that works in
all modes. To make a binding specific to a mode you have to add the pair
under the subsection named like the mode. For instance,
if you want to bind `T` to open a new search for threads tagged with 'todo',
and be able to toggle this tag in search mode, you'd add this to your config::

    [bindings]
      T = search tag:todo

      [[search]]
      t = toggletags todo

.. _modes:

Known modes are:

* envelope
* search
* thread
* taglist
* bufferlist

Have a look at `the urwid User Input documentation <http://excess.org/urwid/wiki/UserInput>`_ on how key strings are formatted.


Hooks
=====
Hooks are python callables that live in a module specified by `hooksfile` in the
config. Per default this points to :file:`~/.config/alot/hooks.py`.
When a hook gets called it receives a reference to the :class:`main user interface <alot.ui.UI>` and the
:class:`database manager <alot.db.DBManager>`.
For every :doc:`COMMAND <../usage/commands>` in mode :ref:`MODE <modes>`, the callables :func:`pre_MODE_COMMAND` and :func:`post_MODE_COMMAND`
-- if defined -- will be called before and after the command is applied respectively. The signature for the
pre-`send` hook in envelope mode for example looks like this:

.. py:function:: pre_envelope_send(ui=None, dbm=None)

    :param ui: the main user interface
    :type ui: :class:`alot.ui.UI`
    :param dbm: a database manager
    :type dbm: :class:`alot.db.DBManager`

Consider this pre-hook for the exit command, that logs a personalized goodbye message::

    import logging
    from alot.settings import settings
    def pre_global_exit(ui, dbm):
        accounts = settings.get_accounts()
        if accounts:
            logging.info('goodbye, %s!' % accounts[0].realname)
        else:
            logging.info('goodbye!')

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

.. _themes:

Themes
======
Alot can be run in 1, 16 or 256 colour mode. The requested mode is determined by the command-line parameter `-C` or read
from option `colourmode` config value. The default is 256, which scales down depending on how many colours your
terminal supports.

To specify the theme to use, set the :ref:`theme <theme>` config option to the name of a theme-file.
A file by that name will be looked up in the path given by the :ref:`themes_dir <themes-dir>` config setting
which defaults to :file:`~/.config/alot/themes/`.

.. _config.theming.themefiles:

Theme Files
-----------
contain a section for each :ref:`MODE <modes>` plus "help" for the bindings-help overlay
and "global" for globally used themables like footer, prompt etc.
Each such section contains attribute values for the parts that can be themed.
The names of the themables should be self-explanatory.
Have a look at the default theme file at :file:`alot/defaults/default.theme`
and the config spec :file:`alot/defaults/default.theme` for the exact format.

.. _config.theming.attributes:

Colour Attributes
-----------------
Attributes are *sextuples* of `urwid Attribute strings <http://excess.org/urwid/wiki/DisplayAttributes>`__
that specify foreground and background for mono, 16 and 256-colour modes respectively.
For mono-mode only the flags `blink`, `standup`, `underline` and `bold` are available,
16c mode supports these in combination with the colour names::

    brown    dark red     dark magenta    dark blue    dark cyan    dark green
    yellow   light red    light magenta   light blue   light cyan   light green
    black    dark gray    light gray      white

In high-colour mode, you may use the above plus grayscales `g0` to `g100` and
colour codes given as `#` followed by three hex values.
See `here <http://excess.org/urwid/wiki/DisplayAttributes>`__
and `here <http://excess.org/urwid/reference.html#AttrSpec>`__
for more details on the interpreted values.  A colour picker that makes choosing colours easy can be
found in :file:`alot/extra/colour_picker.py`.

As an example, check the setting below that makes the footer line appear as
underlined bold red text on a bright green background::

  [[global]]
    #name    mono fg     mono bg   16c fg                        16c bg         256c fg                 256c bg
    #        |                 |   |                             |              |                             |
    #        v                 v   v                             v              v                             v
    footer = 'bold,underline', '', 'light red, bold, underline', 'light green', 'light red, bold, underline', '#8f6'

Highlighting Thread lines in Search Mode
----------------------------------------
The subsection '[[threadline]]' of the '[search]' section in :ref:`Theme Files <config.theming.themefiles>`
determines how to present a thread: here, :ref:`attributes <config.theming.attributes>` 'normal' and
'focus' provide fallback/spacer themes and 'parts' is a (string) list of displayed subwidgets.
Possible part strings are:

* date
* mailcount
* tags
* authors
* subject

For every listed part there must be a subsection with the same name, defining

:normal: :ref:`attribute <config.theming.attributes>` used for this part if unfocussed
:focus: :ref:`attribute <config.theming.attributes>` used for this part if focussed
:width: tuple indicating the width of the part. This is either `('fit', min, max)` to force the widget
        to be at least `min` and at most `max` characters wide,
        or `('weight', n)` which makes it share remaining space
        with other 'weight' parts.
:alignment: how to place the content string if the widget space is larger.
            This must be one of 'right', 'left' or 'center'.

To "highlight" some thread lines (use different attributes than the defaults found in the
'[[threadline]]' section), one can define sections with prefix 'threadline'.
Each one of those can redefine any part of the structure outlined above, the rest defaults to
values defined in '[[threadline]]'.

The section used to theme a particular thread is the first one (in file-order) that matches
the criteria defined by its 'query' and 'taggeswith' values:

* If 'query' is defined, the thread must match that querystring.
* If 'tagged_with' is defined, is value (string list)  must be a subset of the accumulated tags of all messages in the thread.

.. note:: that 'tagged_with = A,B' is different from 'query = "is:A AND is:B"':
   the latter will match only if the thread contains a single message that is both tagged with
   A and B.

   Moreover, note that if both query and tagged_with is undefined, this section will always match
   and thus overwrite the defaults.

The example below shows how to highlight unread threads:
The date-part will be bold red if the thread has unread messages and flagged messages
and just bold if the thread has unread but no flagged messages::

    [search]
        # default threadline
        [[threadline]]
            normal = 'default','default','default','default','#6d6','default'
            focus = 'standout','default','light gray','dark gray','white','#68a'
            parts = date,mailcount,tags,authors,subject
            [[[date]]]
                normal = 'default','default','light gray','default','g58','default'
                focus = 'standout','default','light gray','dark gray','g89','#68a'
                width = 'fit',10,10
            ...

        # highlight threads containing unread and flagged messages
        [[threadline-flagged-unread]]
            tagged_with = 'unread','flagged'
            [[[date]]]
                normal = 'default','default','light red,bold','default','light red,bold','default'

        # highlight threads containing unread messages
        [[threadline-unread]]
            query = 'is:unread'
            [[[date]]]
                normal = 'default','default','light gray,bold','default','g58,bold','default'



Custom Tagstring Formatting
===========================

To specify how a particular tagstring is displayed throughout the interface you can
add a subsection named after the tag to the `[tags]` config section.
`normal` and `focus` keys will interpreted and may contain urwid attribute strings
as described in the :ref:`Themes <themes>` section above.

An alternative string representation is read from the option `translated` or can be given
as pair of strings in `translation`.

The tag can also be hidden from view, if the key `hidden` is present and set to
True. The tag can still be seen in the taglist buffer.

The following will make alot display the "todo" tag as "TODO" in white on red. ::

    [tags]
      [[todo]]
        normal = '','', 'white','light red', 'white','#d66'
        translated = TODO

Utf-8 symbols are welcome here, see e.g.
http://panmental.de/symbols/info.htm for some fancy symbols. I personally display my maildir flags
like this::

    [tags]

      [[flagged]]
        translated = ⚑
        normal = '','','light red','','light red',''
        focus = '','','light red','','light red',''

      [[unread]]
        translated = ✉

      [[replied]]
        translated = ⏎

      [[encrypted]]
        translated = ⚷

You may use regular expressions in the tagstring subsections to theme multiple tagstrings at once (first match wins).
If you do so, you can use the `translation` option to specify a string substitution that will
rename a matching tagstring. `translation` takes a comma separated *pair* of strings that will be fed to
:func:`re.sub`. For instance, to theme all your `nmbug`_ tagstrings and especially colour tag `notmuch::bug` red,
do the following::

  [[notmuch::bug]]
    translated = 'nm:bug'
    normal = "", "", "light red, bold", "light blue", "light red, bold", "#88d"

  [[notmuch::.*]]
    translation = 'notmuch::(.*)','nm:\1'
    normal = "", "", "white", "light blue", "#fff", "#88d"

.. _nmbug: http://notmuchmail.org/nmbug/
