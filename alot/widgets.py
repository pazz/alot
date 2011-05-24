from urwid import Text
from urwid import Edit
from urwid import Pile
from urwid import Columns
from urwid import AttrMap
from urwid import WidgetWrap

import email
from datetime import datetime

import settings
from helper import shorten
from helper import pretty_datetime


class ThreadlineWidget(AttrMap):
    def __init__(self, thread):
        self.thread = thread

        self.datetime = datetime.fromtimestamp(thread.get_newest_date())
        datestring = pretty_datetime(self.datetime)
        self.date_w = AttrMap(Text(datestring), 'threadline_date')

        mailcountstring = "(%d)" % self.thread.get_total_messages()
        self.mailcount_w = AttrMap(Text(mailcountstring),
                                   'threadline_mailcount')

        tagsstring = " ".join(self.thread.get_tags())
        self.tags_w = AttrMap(Text(tagsstring),
                              'threadline_tags')

        authorsstring = shorten(thread.get_authors(),
                                settings.authors_maxlength)
        self.authors_w = AttrMap(Text(authorsstring),
                                 'threadline_authors')

        self.subject_w = AttrMap(Text(thread.get_subject(), wrap='clip'),
                                 'threadline_subject')

        self.columns = Columns([
            ('fixed', len(datestring), self.date_w),
            ('fixed', len(mailcountstring), self.mailcount_w),
            ('fixed', len(tagsstring), self.tags_w),
            ('fixed', len(authorsstring), self.authors_w),
            self.subject_w,
            ],
            dividechars=1)
        AttrMap.__init__(self, self.columns, 'threadline', 'threadline_focus')

    def render(self, size, focus=False):
        if focus:
            self.date_w.set_attr_map({None: 'threadline_date_linefocus'})
            self.mailcount_w.set_attr_map({None: 'threadline_mailcount_linefocus'})
            self.tags_w.set_attr_map({None: 'threadline_tags_linefocus'})
            self.authors_w.set_attr_map({None: 'threadline_authors_linefocus'})
            self.subject_w.set_attr_map({None: 'threadline_subject_linefocus'})
        else:
            self.date_w.set_attr_map({None: 'threadline_date'})
            self.mailcount_w.set_attr_map({None: 'threadline_mailcount'})
            self.tags_w.set_attr_map({None: 'threadline_tags'})
            self.authors_w.set_attr_map({None: 'threadline_authors'})
            self.subject_w.set_attr_map({None: 'threadline_subject'})
        return AttrMap.render(self, size, focus)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_thread(self):
        return self.thread


class BufferlineWidget(Text):
    def __init__(self, buffer):
        self.buffer = buffer
        Text.__init__(self, buffer.__str__(), wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer

class TagWidget(Text):
    def __init__(self, tag):
        self.tag = tag
        Text.__init__(self, tag, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_tag(self):
        return self.tag


class PromptWidget(AttrMap):
    def __init__(self, prefix):
        leftpart = Text(prefix, align='left')
        self.editpart = Edit()
        both = Columns(
            [
                ('fixed', len(prefix) + 1, leftpart),
                ('weight', 1, self.editpart),
            ])
        AttrMap.__init__(self, both, 'prompt', 'prompt')

    def set_input(self, txt):
        return self.editpart.set_edit_text(txt)

    def get_input(self):
        return self.editpart.get_edit_text()


class MessageWidget(WidgetWrap):
    def __init__(self, message, even=False):
        self.message = message
        self.email = self.read_mail(message)
        if even:
            lineattr = 'messageline_even'
        else:
            lineattr = 'messageline_odd'

        self.bodyw = MessageBodyWidget(self.email)
        self.headerw = MessageHeaderWidget(self.email)
        self.linew = MessageLineWidget(self.message)
        pile = Pile([
            AttrMap(self.linew, lineattr),
            AttrMap(self.headerw, 'message_header'),
            AttrMap(self.bodyw, 'message_body')
            ])
        WidgetWrap.__init__(self, pile)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_message(self):
        return self.message

    def get_email(self):
        return self.eml

    def read_mail(self, message):
        #what about crypto?
        try:
            f_mail = open(message.get_filename())
        except EnvironmentError:
            eml = email.message_from_string('Unable to open the file')
        else:
            eml = email.message_from_file(f_mail)
            f_mail.close()
        return eml


class MessageLineWidget(WidgetWrap):
    def __init__(self, message):
        self.message = message
        WidgetWrap.__init__(self, Text(str(message)))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageHeaderWidget(WidgetWrap):
    def __init__(self, eml):
        self.eml = eml
        headerlines = []
        for l in settings.displayed_headers:
            if l in eml:
                headerlines.append('%s:%s' % (l, eml.get(l)))
        headertxt = '\n'.join(headerlines)
        WidgetWrap.__init__(self, Text(headertxt))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageBodyWidget(WidgetWrap):
    def __init__(self, eml):
        self.eml = eml
        bodytxt = ''.join(email.iterators.body_line_iterator(self.eml))
        WidgetWrap.__init__(self, Text(bodytxt))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
