from urwid import Text,AttrMap,Edit,Columns
import logging

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
        logging.error('THREAD: %s'%self.thread)
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

class MessageWidget(AttrMap):
    def __init__(self,message):
        self.message = message
        txt = Text(message.__str__())
        AttrMap.__init__(self,txt, 'message','message_focus')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_message(self):
        return self.message
