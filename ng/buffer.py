import urwid
import logging
from cnotmuch.notmuch import Database, Query, Messages, Message
import widgets
import db
import command
from walker import NotmuchIteratorWalker,IteratorWalker

class Buffer(urwid.AttrMap):
    def __init__(self,ui,widget,name):
        self.ui = ui
        self.typename = name
        self.bindings = {}
        urwid.AttrMap.__init__(self,widget,{})
    def info(self):
        return ""
    def refresh(self):
        pass
    def __str__(self):
        return "[%s] %s" % (self.typename,self.info())
    def apply_command(self,cmd):
        #call and store it directly for a local cmd history
        self.ui.apply_command(cmd)
        #self.refresh()
    def keypress(self,size,key):
        if self.bindings.has_key(key):
            logging.debug("%s: handeles key: %s"%(self.typename,key))
            cmdname,parms = self.bindings[key]
            cmd = command.factory(cmdname,**parms)
            self.apply_command(cmd)
        else:
            logging.debug(key)
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
        Buffer.__init__(self,ui,self.original_widget,'threadlist')
        self.bindings = {
                'enter': ('thread_open',{'thread': self.get_selected_thread}),
                }

    def refresh(self):
        logging.info("querystring: %s"%self.querystring)
        self.result_count = self.dbman.count_messages(self.querystring)
        logging.info("count: %d"%self.result_count)
        threads = self.dbman.search_threads(self.querystring)
        self.threadlist = urwid.ListBox(IteratorWalker(threads,widgets.ThreadlineWidget))
        self.original_widget = self.threadlist

    def info(self):
        return "for %s, (%d)" %(self.querystring,self.result_count)

    def get_selected_thread(self):
        (linewidget,size) = self.threadlist.get_focus()
        threadlinewidget = linewidget.original_widget
        return threadlinewidget.get_thread()
