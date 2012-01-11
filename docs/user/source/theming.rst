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
