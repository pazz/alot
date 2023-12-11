"""
Theme tester
"""
import sys
import urwid
from alot.settings import theme

WIDTH = 42


def as_attr(t, colourmode, name):
    """
    Get urwid Attr from theme file
    """
    s = name.split(".")
    if len(s) == 2:
        attr = t.get_attribute(colourmode, s[0], s[1])
    elif len(s) == 3:
        attr = t._config[s[0]][s[1]][s[2]][t._colours.index(colourmode)]
    elif len(s) == 4:
        attr = t._config[s[0]][s[1]][s[2]][s[3]][t._colours.index(colourmode)]
    return [f"{name}:".rjust(WIDTH), (attr, "A B C")]


def main():
    """
    Theme tester
    """
    if len(sys.argv) > 1:
        theme_filename = sys.argv[1]
    else:
        theme_filename = "alot/defaults/default.theme"
    with open(theme_filename, encoding="utf8") as f:
        t = theme.Theme(f)

    txt = []
    for colourmode in (1, 16, 256):
        txt.append(
            [
                [f"\nColourmode: {colourmode}\n"]
                + as_attr(t, colourmode, "global.footer")
                + as_attr(t, colourmode, "global.body")
                + as_attr(t, colourmode, "global.notify_error")
                + as_attr(t, colourmode, "global.notify_normal")
                + ["\n"]
                + as_attr(t, colourmode, "global.prompt")
                + as_attr(t, colourmode, "global.tag")
                + as_attr(t, colourmode, "global.tag_focus")
                + as_attr(t, colourmode, "help.text")
                + ["\n"]
                + as_attr(t, colourmode, "help.section")
                + as_attr(t, colourmode, "help.title")
                + as_attr(t, colourmode, "bufferlist.line_focus")
                + as_attr(t, colourmode, "bufferlist.line_even")
                + ["\n"]
                + as_attr(t, colourmode, "bufferlist.line_odd")
                + as_attr(t, colourmode, "taglist.line_focus")
                + as_attr(t, colourmode, "taglist.line_even")
                + as_attr(t, colourmode, "taglist.line_odd")
                + ["\n"]
                + as_attr(t, colourmode, "namedqueries.line_focus")
                + as_attr(t, colourmode, "namedqueries.line_even")
                + as_attr(t, colourmode, "namedqueries.line_odd")
                + as_attr(t, colourmode, "thread.arrow_heads")
                + ["\n"]
                + as_attr(t, colourmode, "thread.arrow_bars")
                + as_attr(t, colourmode, "thread.attachment")
                + as_attr(t, colourmode, "thread.attachment_focus")
                + as_attr(t, colourmode, "thread.body")
                + ["\n"]
                + as_attr(t, colourmode, "thread.body_focus")
                + as_attr(t, colourmode, "thread.header")
                + as_attr(t, colourmode, "thread.header_key")
                + as_attr(t, colourmode, "thread.header_value")
                + ["\n"]
                + as_attr(t, colourmode, "thread.summary.even")
                + as_attr(t, colourmode, "thread.summary.odd")
                + as_attr(t, colourmode, "thread.summary.focus")
                + as_attr(t, colourmode, "envelope.body")
                + ["\n"]
                + as_attr(t, colourmode, "envelope.header")
                + as_attr(t, colourmode, "envelope.header_key")
                + as_attr(t, colourmode, "envelope.header_value")
                + as_attr(t, colourmode, "search.threadline.normal")
                + ["\n"]
                + as_attr(t, colourmode, "search.threadline.focus")
                + as_attr(t, colourmode, "search.threadline.parts")
                + as_attr(t, colourmode, "search.threadline.date.normal")
                + as_attr(t, colourmode, "search.threadline.date.focus")
                + ["\n"]
                + as_attr(t, colourmode, "search.threadline.mailcount.normal")
                + as_attr(t, colourmode, "search.threadline.mailcount.focus")
                + as_attr(t, colourmode, "search.threadline.tags.normal")
                + as_attr(t, colourmode, "search.threadline.tags.focus")
                + ["\n"]
                + as_attr(t, colourmode, "search.threadline.authors.normal")
                + as_attr(t, colourmode, "search.threadline.authors.focus")
                + as_attr(t, colourmode, "search.threadline.subject.normal")
                + as_attr(t, colourmode, "search.threadline.subject.focus")
                + ["\n"]
                + as_attr(t, colourmode, "search.threadline.content.normal")
                + as_attr(t, colourmode, "search.threadline.content.focus")
                + as_attr(t, colourmode, "search.threadline-unread.normal")
                + as_attr(t, colourmode, "search.threadline-unread.date.normal")
                + ["\n"]
                + as_attr(t, colourmode, "search.threadline-unread.mailcount.normal")
                + as_attr(t, colourmode, "search.threadline-unread.tags.normal")
                + as_attr(t, colourmode, "search.threadline-unread.authors.normal")
                + as_attr(t, colourmode, "search.threadline-unread.subject.normal")
                + ["\n"]
                + as_attr(t, colourmode, "search.threadline-unread.content.normal")
                + []
            ]
        )
    fill = urwid.Filler(urwid.Text(txt), "top")

    loop = urwid.MainLoop(fill)
    loop.run()


if __name__ == "__main__":
    main()
