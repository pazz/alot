.. _config.theming:

Theming
=======
Alot can be run in 1, 16 or 256 colour mode. The requested mode is determined by the command-line parameter `-C` or read
from option `colourmode` config value. The default is 256, which scales down depending on how many colours your
terminal supports.

Most parts of the user interface can be individually coloured to your liking.
To make it easier to switch between or share different such themes, they are defined in separate
files (see below for the exact format).
To specify the theme to use, set the :ref:`theme <theme>` config option to the name of a theme-file.
A file by that name will be looked up in the path given by the :ref:`themes_dir <themes-dir>` config setting
which defaults to $XDG_CONFIG_HOME/alot/themes, and :file:`~/.config/alot/themes/`,
if XDG_CONFIG_HOME is empty or not set. If the themes_dir is not
present then the contents of $XDG_DATA_DIRS/alot/themes will be tried in order.
This defaults to :file:`/usr/local/share/alot/themes` and :file:`/usr/share/alot/themes`, in that order.
These locations are meant to be used by distro packages to put themes in.

.. _config.theming.themefiles:

Theme Files
-----------
contain a section for each :ref:`MODE <modes>` plus "help" for the bindings-help overlay
and "global" for globally used themables like footer, prompt etc.
Each such section defines colour :ref:`attributes <config.theming.attributes>` for the parts that
can be themed.  The names of the themables should be self-explanatory.
Have a look at the default theme file at :file:`alot/defaults/default.theme` and the config spec
:file:`alot/defaults/default.theme` for the exact format.

.. _config.theming.attributes:

Colour Attributes
-----------------
Attributes are *sextuples* of `urwid Attribute strings <http://urwid.org/manual/displayattributes.html>`__
that specify foreground and background for mono, 16 and 256-colour modes respectively.
For mono-mode only the flags `blink`, `standup`, `underline` and `bold` are available,
16c mode supports these in combination with the colour names::

    brown    dark red     dark magenta    dark blue    dark cyan    dark green
    yellow   light red    light magenta   light blue   light cyan   light green
    black    dark gray    light gray      white

In high-colour mode, you may use the above plus grayscales `g0` to `g100` and
colour codes given as `#` followed by three hex values.
See `here <http://urwid.org/manual/displayattributes.html>`__
and `here <http://urwid.org/reference/attrspec.html#urwid.AttrSpec>`__
for more details on the interpreted values.  A colour picker that makes choosing colours easy can be
found in :file:`alot/extra/colour_picker.py`.

As an example, check the setting below that makes the footer line appear as
underlined bold red text on a bright green background:

.. sourcecode:: ini

  [[global]]
    #name    mono fg     mono bg   16c fg                        16c bg         256c fg                 256c bg
    #        |                 |   |                             |              |                             |
    #        v                 v   v                             v              v                             v
    footer = 'bold,underline', '', 'light red, bold, underline', 'light green', 'light red, bold, underline', '#8f6'

Search mode thread ines
-------------------------
The subsection '[[threadline]]' of the '[search]' section in :ref:`Theme Files <config.theming.themefiles>`
determines how to present a thread: here, :ref:`attributes <config.theming.attributes>` 'normal' and
'focus' provide fallback/spacer themes and 'parts' is a (string) list of displayed subwidgets.
Possible part strings are:

* authors
* content
* date
* mailcount
* subject
* tags

For every listed part there must be a subsection with the same name, defining

:normal: :ref:`attribute <config.theming.attributes>` used for this part if unfocussed
:focus: :ref:`attribute <config.theming.attributes>` used for this part if focussed
:width: tuple indicating the width of the part. This is either `('fit', min, max)` to force the widget
        to be at least `min` and at most `max` characters wide,
        or `('weight', n)` which makes it share remaining space
        with other 'weight' parts.
:alignment: how to place the content string if the widget space is larger.
            This must be one of 'right', 'left' or 'center'.

Dynamic theming of thread lines based on query matching
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
To highlight some thread lines (use different attributes than the defaults found in the
'[[threadline]]' section), one can define sections with prefix 'threadline'.
Each one of those can redefine any part of the structure outlined above, the rest defaults to
values defined in '[[threadline]]'.

The section used to theme a particular thread is the first one (in file-order) that matches
the criteria defined by its 'query' and 'tagged_with' values:

* If 'query' is defined, the thread must match that querystring.
* If 'tagged_with' is defined, is value (string list)  must be a subset of the accumulated tags of all messages in the thread.

.. note:: that 'tagged_with = A,B' is different from 'query = "is:A AND is:B"':
   the latter will match only if the thread contains a single message that is both tagged with
   A and B.

   Moreover, note that if both query and tagged_with is undefined, this section will always match
   and thus overwrite the defaults.

The example below shows how to highlight unread threads:
The date-part will be bold red if the thread has unread messages and flagged messages
and just bold if the thread has unread but no flagged messages:

.. sourcecode:: ini

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
            # ...

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

.. _config.theming.tags:

Tagstring Formatting
--------------------

One can specify how a particular tagstring is displayed throughout the interface. To use this
feature, add a section `[tags]` to you alot config (not the theme file)
and for each tag you want to customize, add a subsection named after the tag.
Such a subsection may define

:normal: :ref:`attribute <config.theming.attributes>` used if unfocussed
:focus: :ref:`attribute <config.theming.attributes>` used if focussed
:translated: fixed string representation for this tag. The tag can be hidden from view,
             if the key `translated` is set to '', the empty string.
:translation: a pair of strings that define a regular substitution to compute the string
              representation on the fly using `re.sub`. This only really makes sense if
              one uses a regular expression to match more than one tagstring (see below).

The following will make alot display the "todo" tag as "TODO" in white on red.

.. sourcecode:: ini

    [tags]
      [[todo]]
        normal = '','', 'white','light red', 'white','#d66'
        translated = TODO

Utf-8 symbols are welcome here, see e.g.
http://panmental.de/symbols/info.htm for some fancy symbols. I personally display my maildir flags
like this:

.. sourcecode:: ini

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
do the following:

.. sourcecode:: ini

  [[notmuch::bug]]
    translated = 'nm:bug'
    normal = "", "", "light red, bold", "light blue", "light red, bold", "#88d"

  [[notmuch::.*]]
    translation = 'notmuch::(.*)','nm:\1'
    normal = "", "", "white", "light blue", "#fff", "#88d"

.. _nmbug: http://notmuchmail.org/nmbug/

