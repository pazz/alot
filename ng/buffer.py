import urwid
import widgets
import db
import command
from walker import IteratorWalker

class Buffer(urwid.AttrMap):
    def __init__(self,ui,widget,name):
        self.ui = ui
        self.typename = name
        self.bindings = {}
        urwid.AttrMap.__init__(self,widget,{})

        return ""
    def refresh(self):
        pass

    def __str__(self):
        return "[%s]" % (self.typename)

    def apply_command(self,cmd):
        #call and store it directly for a local cmd history
        self.ui.apply_command(cmd)
        #self.refresh()

    def keypress(self,size,key):
        if self.bindings.has_key(key):
            self.ui.logger.debug("%s: handeles key: %s"%(self.typename,key))
            cmdname,parms = self.bindings[key]
            cmd = command.factory(cmdname,**parms)
            self.apply_command(cmd)
        else:
            if key == 'j':
                key='down'
            elif key == 'k':
                key='up'
            elif key == 'h':
                key='left'
            elif key == 'l':
                key='right'
            elif key == ' ':
                key='page down'
            return self.original_widget.keypress(size,key)

class BufferListBuffer(Buffer):
    def __init__(self,ui,filtfun=None):
        self.filtfun = filtfun
        self.ui = ui
        #better create a walker obj that has a pointer to ui.bufferlist
        #self.widget=createWalker(...
        self.refresh()
        Buffer.__init__(self,ui,self.original_widget,'bufferlist')
        self.bindings = {
                'd': ('buffer_close',{'buffer': self.get_selected_buffer}),
                'enter': ('buffer_focus',{'buffer': self.get_selected_buffer}),
                }

    def index_of(self,b):
        return self.ui.buffers.index(b)

    def refresh(self):
        lines = []
        i=0
        for b in filter(self.filtfun,self.ui.buffers):
            line = widgets.BufferlineWidget(b)
            if (i%2 == 1):
                attr = 'bufferlist_results_odd'
            else:
                attr = 'bufferlist_results_even'
            buf =  urwid.AttrMap(line, attr,'bufferlist_focus')
            num = urwid.Text('%3d:'%self.index_of(b))
            lines.append(urwid.Columns([('fixed',4,num),buf]))
            i+=1
        self.bufferlist = urwid.ListBox(urwid.SimpleListWalker(lines))
        self.original_widget = self.bufferlist

    def get_selected_buffer(self):
        (linewidget,size) = self.bufferlist.get_focus()
        bufferlinewidget = linewidget.get_focus().original_widget
        return bufferlinewidget.get_buffer()

class SearchBuffer(Buffer):
    threads = []
    def __init__(self,ui,initialquery=''):
        self.dbman = ui.dbman
        self.querystring = initialquery
        self.result_count = 0
        #self.widget=createWalker(...
        self.refresh()
        Buffer.__init__(self,ui,self.original_widget,'search')
        self.bindings = {
                'enter': ('open_thread',{'thread': self.get_selected_thread}),
                }

    def refresh(self):
        self.result_count = self.dbman.count_messages(self.querystring)
        threads = self.dbman.search_threads(self.querystring)
        self.threadlist = urwid.ListBox(IteratorWalker(threads,widgets.ThreadlineWidget))
        self.original_widget = self.threadlist

    def __str__(self):
        return "[%s] for %s, (%d)" % (self.typename,self.querystring,self.result_count)

    def get_selected_thread(self):
        (threadlinewidget,size) = self.threadlist.get_focus()
        t=threadlinewidget.get_thread()
        return t

class SingleThreadBuffer(Buffer):
    def __init__(self,ui,thread):
        self.read_thread(thread)
        self.refresh()
        Buffer.__init__(self,ui,self.original_widget,'search')
        self.bindings = {
                'enter': ('call_pager',{'path': self.get_selected_message_file}),
                }
    def read_thread(self,thread):
        self.message_count = thread.get_total_messages()
        self.subject = thread.get_subject()
        self.messages = []
        for m in thread.get_toplevel_messages():
            self.messages.append(m)

    def refresh(self):
        msgs = []
        for m in self.messages:
            msgs.append(widgets.MessageWidget(m))
        self.messagelist = urwid.ListBox(msgs)
        self.original_widget = self.messagelist

    def __str__(self):
        return "[%s] %s, (%d)" %(self.typename,self.subject,self.message_count)

    def get_selected_message(self):
        (messagewidget,size) = self.messagelist.get_focus()
        return messagewidget.get_message()

    def get_selected_message_file(self):
        return self.get_selected_message().get_filename()
