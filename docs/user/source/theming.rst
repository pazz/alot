Theming
=======

Colours
-------
Alot can be run in 1, 16 or 256 colour mode.
The requested mode is determined by the commandline parameter `-C` or read from
option `colourmode` in section `[globals]` of your config file.
The default is 256, which will be scaled down depending on how many colours
your terminal supports.

The interface will theme its widgets according to the palette defined in
section `[MODEc-theme]` where `MODE` is the integer indicating the colour mode.
Have a look at the default config (`alot/defaults/alot.rc`) for a complete list
of interpreted widget settings; the keys in this section should be self-explanatory.

Values can be colour names (`light red`, `dark green`..), RGB colour codes (e.g. `#868`),
font attributes (`bold`, `underline`, `blink`, `standout`) or a comma separated combination of
colour and font attributes.
In sections `[16c-theme]` and `[256c-theme]` you can define Y_fg and
Y_bg for the foreground and background of each widget keyword Y, whereas the monochromatic
(`[1c-theme]`) palette can only interpret font attributes for key Y without the suffix.
As an example, check the setting below that makes the footer line appear as
underlined bold red text on a bright green background::

    [256c-theme]
    global_footer_bg = #8f6
    global_footer_fg = light red, bold, underline

See `urwids docs on Attributes <http://excess.org/urwid/reference.html#AttrSpec>`_ for more details
on the interpreted values. Urwid provides a `neat colour picker script`_ that makes choosing
colours easy.

.. _neat colour picker script: http://excess.org/urwid/browser/palette_test.py


Custom Tagstring Formatting
---------------------------
In theme sections you can use keys with prefix `tag_` to format specific tagstrings. For instance,
the following will make alot display the "todo" tag in white on red when in 256c-mode. ::

    [256c-theme]
    tag_todo_bg = #d66
    tag_todo_fg = white

You can translate tag strings before displaying them using the `[tag-translate]` section. A
key=value statement in this section is interpreted as:
Always display the tag `key` as string `value`. Utf-8 symbols are welcome here, see e.g.
http://panmental.de/symbols/info.htm for some fancy symbols. I personally display my maildir flags
like this::

    [tag-translate]
    flagged = ⚑
    unread = ✉
    replied = ⇄


Highlighting
============

About
-----
Thread lines in the ``SearchBuffer`` can be highlighted by applying a theme different
from their regular one if they match a `notmuch` query.

The default config predefines highlighting for threads that carry the `unread`,
the `flagged` or both of those tags.

Components
----------
Thread lines consist of up to six components (not all of which are shown by
default) that may be themed individually to provide highlighting. The components
are 

 - `date`
 - `mailcount`
 - `tags`
 - `authors`
 - `subject`
 - `content`
 
Have a look at Alot's interface to see what they are.

Customizing highlighting, you may define which components you want highlighted.
Add a `highlighting` section to your config file and define a comma separated
list of highlightable components: ::

    [highlighting]
    components = date, mailcount, tags, authors, subject

Rules
-----
To specify which threads should be highlighted, you need to define highlighting
rules. Rules map queries onto theme identifiers. Each thread that matches a given rule
will use a theme identified by the ID the rule is mapped to.

.. admonition:: Example

    To highlight threads that are tagged as 'important', add the `rules`
    key to your `highlighting` section and provide a dict in JSON syntax. Use an
    appropriate `notmuch` query as a key and select a meaningful theme identifier as
    its value:
    
::

    rules = { "tag:important":"isimportant" }

.. note::
  Please make sure the identifier isn't the name of an actual tag, since this
  may introduce ambiguity when highlighting tags. More on that later.

If you want highlighting for other threads as well, just add more rules to the
dict: ::

    rules = { "tag:important":"isimportant",
              "subject:alot":"concernsalot",
              "from:mom@example.com":"frommom"}

.. note:: 
    The sequence of the list defines the search order. The first query that
    matches selects the highlighting. So if you have queries that are harder to
    satisfy, you should put them earlier in the dict than ones that match more
    easily:

::

    rules = { "tag:unread":"isunread",
              "tag:unread AND tag:important":"isunreadimportant"}

This setup will never highlight any threads as `isunreadimportant`, since alle
threads that would match that identifier's query will *also* have matched the
`isunread` query earlier in the rules dict. So, again, make sure that rules that
are hard to satisfy show up early in the dict: ::

    rules = { "tag:unread AND tag:important":"isunreadimportant",
              "tag:unread":"isunread"}

This way only threads that didn't match `isunreadimportant` before end up
highlighted as `isunread` only.

Themes
------
Now that you have selected components for highlighting and defined some rules,
you need to actually decide on some colours.

.. note:: 
  The following schema will allow you to define highlighting themes for all
  components *except* `tags`, which follow a different system and will be
  explained in the next example.

To define a highlighting theme for a component, you need to add a key of the
following format to your colour theme (please cf. `colours`_ for more information
on theming): ::

   search_thread_COMPONENT_ID_[focus_][fg|bg]

where 

 - ``COMPONENT`` is the component this theme is meant to highlight,
 - ``ID`` is the theme identifier that defines which query this option belongs
   to,
 - ``focus_`` is optional and if present defines that the theme should only be
   used if the current thread is focussed and
 - ``fg`` or ``bg`` is a selection that specifies which themable part of the
   component this option refers to.

.. admonition:: Example

    The following option will highlight the `subject` of each thread that
    matches the query mapping to `isimportant` if the current thread is
    `focus`\sed by theming its `foreground` according to the values stated
    below:

::
    
    search_thread_subject_isimportant_focus_fg = dark red, underline

Following this pattern will allow you to set theming for the `background`, for
the `subject` of threads tagged as `important` that are currently not focussed
(by omitting the `focus_` part of the key string), for `subject`\s of threads
matching a different query, and all other components except `tags`.

-----

As described in `Custom Tagstring Formatting`_, tags may be themed individually.
Highlighting expands this concept by allowing default themed tags as well as
custom themed tags to provide highlighting variants.

To specify highlighting themes for default themed tags, just add a key with the wanted
theme identifier: ::

    tag_ID_[focus_][fg|bg]

where

 - ``ID`` is the theme identifier that defines which query this option belongs
   to,
 - ``focus_`` is optional and if present defines that the theme should only be
   used if the current thread is focussed and
 - ``fg`` or ``bg`` is a selection that specifies which themable part of the
   component this option refers to.

To highlight custom themed tags, proceed accordingly. Specify ::

   tag_TAG_ID_[focus_][fg|bg]

where

 - ``TAG`` is the name of the custom themed tag that is to be highlighted,
 - ``ID`` is the theme identifier that defines which query this option belongs
   to,
 - ``focus_`` is optional and if present defines that the theme should only be
   used if the current thread is focussed and
 - ``fg`` or ``bg`` is a selection that specifies which themable part of the
   component this option refers to.

.. caution::
    As mentioned earlier, using tag names as theme identifiers may introduce
    ambiguity and lead to unexpected theming results. 

Assuming one would replace the theme identifier `isimportant` with its intuitive
alternative `important`, the tag theme ``tag_important_fg`` might either be a
custom theme for the tag `important` of the form ``tag_TAG_fg`` or the highlight
theme for default themed tags of threads that match the query that maps to the
`important` identifier: ``tag_ID_fg``.

Using above proper identifier would distinguish those options as
``tag_important_fg`` for the custom theme and ``tag_isimportant_fg`` for the
highlighting theme.
