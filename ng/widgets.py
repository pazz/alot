from urwid import Text,AttrMap,Edit,Columns,ListBox,Pile,WidgetWrap
from walker import IteratorWalker
import email
import settings

class ThreadlineWidget(AttrMap):
    def __init__(self,thread):
        self.thread = thread
        self.markup = thread.__str__()
        txt = Text(thread.__str__(),wrap='clip')
        AttrMap.__init__(self,txt, 'threadline','threadline_focus')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_thread(self):
        return self.thread

class BufferlineWidget(Text):
    def __init__(self,buffer):
        self.buffer = buffer
        Text.__init__(self,buffer.__str__(),wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer

class PromptWidget(AttrMap):
    def __init__(self, prefix):
        leftpart = Text(prefix,align='left')
        self.editpart = Edit()
        both = Columns(
            [
                ('fixed', len(prefix)+1, leftpart),
                ('weight', 1, self.editpart),
            ])
        AttrMap.__init__(self,both, 'prompt','prompt')

    def set_input(self,txt):
        return self.editpart.set_edit_text(txt)

    def get_input(self):
        return self.editpart.get_edit_text()

class MessageWidget(WidgetWrap):
    def __init__(self,message,even=False):
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
            AttrMap(self.linew,lineattr),
            AttrMap(self.headerw,'message_header'),
            AttrMap(self.bodyw,'message_body')
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

    def read_mail(self,message):
        #what about crypto?
        f=open(message.get_filename())
        eml = email.message_from_file(f)
        f.close()
        return eml

class MessageLineWidget(WidgetWrap):
    def __init__(self,message):
        self.message = message
        headertxt=message.__str__()
        txt = Text(headertxt)
        WidgetWrap.__init__(self,txt)

    def selectable(self):
        return True
    def keypress(self, size, key):
        return key

class MessageHeaderWidget(WidgetWrap):
    def __init__(self,eml):
        self.eml = eml
        headerlines = []
        for l in settings.displayed_headers:
            if eml.has_key(l):
                headerlines.append('%s:%s'%(l,eml.get(l)))
        headertxt = '\n'.join(headerlines)
        txt = Text(headertxt)
        WidgetWrap.__init__(self,txt)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
class MessageBodyWidget(WidgetWrap):
    def __init__(self,eml):
        self.eml = eml
        bodytxt = ""
        for l in email.iterators.body_line_iterator(self.eml):
            bodytxt+=l
        txt = Text(bodytxt)
        WidgetWrap.__init__(self,txt)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
