from urwid import Text,AttrMap
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

