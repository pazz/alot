"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import os
import code
import logging
import threading
import subprocess
from cmd import Cmd
import StringIO
import email
from email.parser import Parser
import tempfile
from Queue import Queue

import buffer
from settings import config
from settings import get_hook
import completion


class Command:
    """base class for commands"""
    def __init__(self, prehook=None, posthook=None, **ignored):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        pass


class ShutdownCommand(Command):
    """shuts the MUA down cleanly"""
    def apply(self, ui):
        ui.shutdown()


class OpenThreadCommand(Command):
    """open a new thread-view buffer"""
    def __init__(self, thread, **kwargs):
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.logger.info('open thread view for %s' % self.thread)
        sb = buffer.SingleThreadBuffer(ui, self.thread)
        ui.buffer_open(sb)


class SearchCommand(Command):
    """open a new search buffer"""
    def __init__(self, query, force_new=False, **kwargs):
        """
        @param query initial querystring
        @param force_new True forces a new buffer
        """
        self.query = query
        self.force_new = force_new
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.force_new:
            open_searches = ui.get_buffers_of_type(buffer.SearchBuffer)
            to_be_focused = None
            for sb in open_searches:
                if sb.querystring == self.query:
                    to_be_focused = sb
            if to_be_focused:
                ui.buffer_focus(to_be_focused)
            else:
                ui.buffer_open(buffer.SearchBuffer(ui, self.query))
        else:
            ui.buffer_open(buffer.SearchBuffer(ui, self.query))


class SearchPromptCommand(Command):
    """prompt the user for a querystring, then start a search"""
    def apply(self, ui):
        querystring = ui.prompt('search threads:',
                                completer=completion.QueryCompleter(ui.dbman))
        ui.logger.info("got %s" % querystring)
        if querystring:
            cmd = factory('search', query=querystring)
            ui.apply_command(cmd)


class RefreshCommand(Command):
    """refreshes the current buffer"""
    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


class EditExternalCommand(Command):
    """
    opens editor
    """
    def __init__(self, path, spawn=None, on_success=None, refocus=False, **kwargs):
        self.path = path
        self.on_success = on_success
        self.refocus = refocus
        if spawn != None:
            self.spawn = spawn
        else:
            self.spawn = config.getboolean('general', 'spawn_editor')
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        editor_cmd = config.get('general', 'editor_cmd')
        cmd = ExternalCommand(editor_cmd + ' ' + self.path,
                              spawn=self.spawn,
                              refocus=self.refocus,
                              on_success=self.on_success)
        ui.apply_command(cmd)


class PagerCommand(Command):
    """opens pager"""

    def __init__(self, path, spawn=False, **kwargs):
        self.path = path
        self.spawn = config.get('general', 'spawn_pager') or spawn
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        def afterwards():
            ui.logger.info('pager was closed')
        pager_cmd = config.get('general', 'pager_cmd')
        cmd = ExternalCommand(pager_cmd + ' ' + self.path,
                              spawn=self.spawn,
                              on_success=afterwards)
        ui.apply_command(cmd)


class ExternalCommand(Command):
    """calls external command"""
    # TODO: separate spawn from fork
    def __init__(self, commandstring, spawn=False, refocus=True,
                 on_success=None, **kwargs):
        self.commandstring = commandstring
        self.spawn = spawn
        self.refocus = refocus
        self.onSuccess = on_success
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        q = Queue()
        def interpret_return_value():
            returnvalue = q.get()
            if callable(self.onSuccess) and returnvalue == 0:
                ui.logger.info("return:%d"%returnvalue)
                self.onSuccess()

        def thread_code(q,*popenArgs):
            callerbuffer = ui.current_buffer
            returncode = subprocess.call(*popenArgs, shell=True) # this blocks
            if self.refocus and callerbuffer in ui.buffers:
                ui.logger.info('trying to refocus: %s' % callerbuffer)
                ui.buffer_focus(callerbuffer)
            interpret_return_value(returncode)
            return

        if self.spawn:
            cmd = config.get('general', 'terminal_cmd')
            cmd += ' ' + self.commandstring
            ui.logger.info('calling external command: %s' % cmd)
            thread = threading.Thread(target=thread_code, args=(q,(cmd,)))
            thread.start()
        else:
            ui.mainloop.screen.stop()
            cmd = self.commandstring
            logging.debug(cmd)
            thread_code(q, (cmd,))
            ui.mainloop.screen.start()


class OpenPythonShellCommand(Command):
    """
    opens an interactive shell for introspection
    """
    def apply(self, ui):
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()


class BufferCloseCommand(Command):
    """
    close a buffer
    @param buffer the selected buffer
    """
    def __init__(self, buffer=None, **kwargs):
        self.buffer = buffer
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.buffer:
            self.buffer = ui.current_buffer
        ui.buffer_close(self.buffer)
        ui.buffer_focus(ui.current_buffer)


class BufferFocusCommand(Command):
    """
    focus a buffer
    @param buffer the selected buffer
    """
    def __init__(self, buffer=None, offset=0, **kwargs):
        self.buffer = buffer
        self.offset = offset
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.buffer:
            self.buffer = ui.current_buffer
        idx = ui.buffers.index(self.buffer)
        num = len(ui.buffers)
        to_be_focused = ui.buffers[(idx + self.offset) % num]
        ui.buffer_focus(to_be_focused)


class OpenBufferListCommand(Command):
    """
    open a bufferlist
    """
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        blists = ui.get_buffers_of_type(buffer.BufferListBuffer)
        if blists:
            ui.buffer_focus(blists[0])
        else:
            ui.buffer_open(buffer.BufferListBuffer(ui, self.filtfun))


class OpenTagListCommand(Command):
    """
    open a taglist
    """
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        tags = ui.dbman.get_all_tags()
        buf = buffer.TagListBuffer(ui, tags, self.filtfun)
        ui.buffers.append(buf)
        buf.rebuild()
        ui.buffer_focus(buf)


class OpenEnvelopeCommand(Command):
    def __init__(self, email=None, **kwargs):
        self.email = email
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.logger.info('apply OPENENVELOPE')
        # ui.buffer_open(buffer.EnvelopeBuffer(ui, email=self.email))
        b=buffer.BufferListBuffer(ui, None)
        ui.buffer_open(b)
        b.rebuild()


class ToggleThreadTagCommand(Command):
    """
    """
    def __init__(self, thread, tag, **kwargs):
        assert thread
        self.thread = thread
        self.tag = tag
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.tag in self.thread.get_tags():
            self.thread.remove_tags([self.tag])
        else:
            self.thread.add_tags([self.tag])

        # update current buffer
        cb = ui.current_buffer
        if isinstance(cb, buffer.SearchBuffer):
            # refresh selected threadline
            threadwidget = cb.get_selected_threadline()
            threadwidget.rebuild()  # rebuild and redraw the line
            #remove line from searchlist if thread doesn't match the query
            qs = "(%s) AND thread:%s" % (cb.querystring,
                                         self.thread.get_thread_id())
            msg_count = ui.dbman.count_messages(qs)
            if ui.dbman.count_messages(qs) == 0:
                ui.logger.debug('remove: %s' % self.thread)
                cb.threadlist.remove(threadwidget)
                cb.result_count -= self.thread.get_total_messages()
                ui.update_footer()
        elif isinstance(cb, buffer.SingleThreadBuffer):
            pass
            #if (self.tag == 'inbox') and 'inbox' not in self.thread.get_tags():
            #    ui.apply_command(BufferCloseCommand(cb))


class ComposeCommand(Command):
    def __init__(self, email=None, **kwargs):
        self.email = email
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.email:
            header = {}
            # TODO: fill with default header
            header['From'] = 'me' #ui.prompt(prefix='From>')
            header['To'] = 'you' #ui.prompt(prefix='To>')
            header['Subject'] = 'sjb' #ui.prompt(prefix='Subject>')

        def onSuccess():
            f = open(tf.name)
            editor_input = f.read()
            self.email = Parser().parsestr(editor_input)
            f.close()
            os.unlink(tf.name)
            ui.apply_command(OpenEnvelopeCommand(email=self.email))

        tf = tempfile.NamedTemporaryFile(delete=False)
        for i in header.items():
            tf.write('%s: %s\n'%i)
        tf.write('\n\n')
        tf.close()
        ui.apply_command(EditExternalCommand(tf.name, on_success=onSuccess,
                                             refocus=False))



class ThreadTagPromptCommand(Command):
    """prompt the user for labels, then tag thread"""

    def __init__(self, thread, **kwargs):
        assert thread
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        initial_tagstring = ','.join(self.thread.get_tags())
        tagsstring = ui.prompt('label thread:',
                               text=initial_tagstring,
                               completer=completion.TagListCompleter(ui.dbman))
        if tagsstring != None:  # esc -> None, enter could return ''
            tags = filter(lambda x: x, tagsstring.split(','))
            ui.logger.info("got %s:%s" % (tagsstring, tags))
            self.thread.set_tags(tags)

        # refresh selected threadline
        sbuffer = ui.current_buffer
        threadwidget = sbuffer.get_selected_threadline()
        threadwidget.rebuild()  # rebuild and redraw the line


class RefineSearchPromptCommand(Command):
    """refine the current search"""

    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        querystring = ui.prompt('refine search:', text=oldquery,
                                completer=completion.QueryCompleter(ui.dbman))
        if querystring not in [None, oldquery]:
            sbuffer.querystring = querystring
            sbuffer = ui.current_buffer
            sbuffer.rebuild()
            ui.update_footer()

commands = {
        'buffer_close': (BufferCloseCommand, {}),
        'buffer_focus': (BufferFocusCommand, {}),
        'buffer_list': (OpenBufferListCommand, {}),
        'buffer_next': (BufferFocusCommand, {'offset': 1}),
        'buffer_prev': (BufferFocusCommand, {'offset': -1}),
        'edit': (EditExternalCommand, {}),
        'call_pager': (PagerCommand, {}),
        'compose': (ComposeCommand, {}),
        'open_taglist': (OpenTagListCommand, {}),
        'open_thread': (OpenThreadCommand, {}),
        'open_envelope': (OpenEnvelopeCommand, {}),
        'search': (SearchCommand, {}),
        'search_prompt': (SearchPromptCommand, {}),
        'refine_search_prompt': (RefineSearchPromptCommand, {}),
        'shell': (OpenPythonShellCommand, {}),
        'shutdown': (ShutdownCommand, {}),
        'thread_tag_prompt': (ThreadTagPromptCommand, {}),
        'toggle_thread_tag': (ToggleThreadTagCommand, {'tag': 'inbox'}),
        'view_log': (PagerCommand, {'path': 'debug.log'}),
        'refresh_buffer': (RefreshCommand, {}),
        }


def factory(cmdname, **kwargs):
    if cmdname in commands:
        (cmdclass, parms) = commands[cmdname]
        parms = parms.copy()
        parms.update(kwargs)
        for (key, value) in kwargs.items():
            if callable(value):
                parms[key] = value()
            else:
                parms[key] = value

        parms['prehook'] = get_hook('pre_' + cmdname)
        parms['posthook'] = get_hook('post_' + cmdname)

        logging.debug('cmd parms %s' % parms)
        return cmdclass(**parms)
    else:
        logging.error('there is no command %s' % cmdname)

class MyCmd(Cmd):
    def do_test(self, line):
        self.stdout.write(line)
        pass

    def run(self, cmdline):
        self.stdout = StringIO.StringIO()
        self.onecmd(cmdline)
        output = self.stdout.getvalue()
        return output
