"""
Theme tester
"""
import sys
import urwid
from alot.settings import theme

WIDTH = 44


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
    return [f"{name}: ".rjust(WIDTH), (attr, "A B C")]


def get_text(t):
    txt = []
    for colourmode in (1, 16, 256):
        txt += [f"\nColourmode: {colourmode}\n"]
        for i, name in enumerate(
            (
                "global.footer",
                "global.body",
                "global.notify_error",
                "global.notify_normal",
                "global.prompt",
                "global.tag",
                "global.tag_focus",
                "help.text",
                "help.section",
                "help.title",
                "bufferlist.line_focus",
                "bufferlist.line_even",
                "bufferlist.line_odd",
                "taglist.line_focus",
                "taglist.line_even",
                "taglist.line_odd",
                "namedqueries.line_focus",
                "namedqueries.line_even",
                "namedqueries.line_odd",
                "thread.arrow_heads",
                "thread.arrow_bars",
                "thread.attachment",
                "thread.attachment_focus",
                "thread.body",
                "thread.body_focus",
                "thread.header",
                "thread.header_key",
                "thread.header_value",
                "thread.summary.even",
                "thread.summary.odd",
                "thread.summary.focus",
                "envelope.body",
                "envelope.header",
                "envelope.header_key",
                "envelope.header_value",
                "search.threadline.normal",
                "search.threadline.focus",
                "search.threadline.parts",
                "search.threadline.date.normal",
                "search.threadline.date.focus",
                "search.threadline.mailcount.normal",
                "search.threadline.mailcount.focus",
                "search.threadline.tags.normal",
                "search.threadline.tags.focus",
                "search.threadline.authors.normal",
                "search.threadline.authors.focus",
                "search.threadline.subject.normal",
                "search.threadline.subject.focus",
                "search.threadline.content.normal",
                "search.threadline.content.focus",
                "search.threadline-unread.normal",
                "search.threadline-unread.date.normal",
                "search.threadline-unread.mailcount.normal",
                "search.threadline-unread.tags.normal",
                "search.threadline-unread.authors.normal",
                "search.threadline-unread.subject.normal",
                "search.threadline-unread.content.normal",
            )
        ):
            txt += as_attr(t, colourmode, name)
            if i % 4 == 0:
                txt.append("\n")
    return txt


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

    fill = urwid.Filler(urwid.Text(get_text(t)), "top")

    loop = urwid.MainLoop(fill)
    loop.run()


if __name__ == "__main__":
    main()
