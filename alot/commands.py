"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Alot is distributed in the hope that it will be useful, but WITHOUT
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

import buffer
from settings import config
from settings import get_hook
from settings import get_account_by_address
from settings import get_accounts
from db import DatabaseROError
from db import DatabaseLockedError
import completion
import helper


class Command:
    """base class for commands"""
    def __init__(self, prehook=None, posthook=None, **ignored):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        pass


class ExitCommand(Command):
    """shuts the MUA down cleanly"""
    def apply(self, ui):
        ui.shutdown()


class OpenThreadCommand(Command):
    """open a new thread-view buffer"""
    def __init__(self, thread=None, **kwargs):
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
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


class PromptCommand(Command):
    def __init__(self, startstring='', **kwargs):
        self.startstring = startstring

    def apply(self, ui):
        ui.commandprompt(self.startstring)


class RefreshCommand(Command):
    """refreshes the current buffer"""
    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


class ExternalCommand(Command):
    """
    calls external command
    """
    def __init__(self, commandstring, spawn=False, refocus=True,
                 in_thread=False, on_success=None, **kwargs):
        """
        :param commandstring: the command to call
        :type commandstring: str
        :param spawn: run command in a new terminal
        :type spawn: boolean
        :param refocus: refocus calling buffer after cmd termination
        :type refocus: boolean
        :param on_success: code to execute after command successfully exited
        :type on_success: callable
        """
        self.commandstring = commandstring
        self.spawn = spawn
        self.refocus = refocus
        self.in_thread = in_thread
        self.on_success = on_success
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        callerbuffer = ui.current_buffer

        def afterwards(data):
            if callable(self.on_success) and data == 'success':
                self.on_success()
            if self.refocus and callerbuffer in ui.buffers:
                ui.logger.info('refocussing')
                ui.buffer_focus(callerbuffer)

        write_fd = ui.mainloop.watch_pipe(afterwards)

        def thread_code(*args):
            cmd = self.commandstring
            if self.spawn:
                cmd = config.get('general', 'terminal_cmd') + ' ' + cmd
            ui.logger.info('calling external command: %s' % cmd)
            returncode = subprocess.call(cmd, shell=True)
            if returncode == 0:
                os.write(write_fd, 'success')

        if self.in_thread:
            thread = threading.Thread(target=thread_code)
            thread.start()
        else:
            ui.mainloop.screen.stop()
            thread_code()
            ui.mainloop.screen.start()


class EditCommand(ExternalCommand):
    def __init__(self, path, spawn=None, **kwargs):
        self.path = path
        if spawn != None:
            self.spawn = spawn
        else:
            self.spawn = config.getboolean('general', 'spawn_editor')
        editor_cmd = config.get('general', 'editor_cmd')
        cmd = editor_cmd + ' ' + self.path
        ExternalCommand.__init__(self, cmd, spawn=self.spawn,
                                 in_thread=self.spawn,
                                 **kwargs)


class PythonShellCommand(Command):
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
    def __init__(self, buffer=None, focussed=False, **kwargs):
        self.buffer = buffer
        self.focussed = focussed
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.focussed:
            self.buffer = ui.current_buffer.get_selected_buffer()
        elif not self.buffer:
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
        if self.offset:
            idx = ui.buffers.index(ui.current_buffer)
            num = len(ui.buffers)
            self.buffer = ui.buffers[(idx + self.offset) % num]
        else:
            if not self.buffer:
                self.buffer = ui.current_buffer.get_selected_buffer()
        ui.buffer_focus(self.buffer)


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


class TagListCommand(Command):
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
        ui.buffer_open(buffer.EnvelopeBuffer(ui, email=self.email))


class CommandPromptCommand(Command):
    """
    """
    def apply(self, ui):
        ui.commandprompt()


class FlushCommand(Command):
    """
    Flushes writes to the index. Retries until committed
    """
    def apply(self, ui):
        try:
            ui.dbman.flush()
        except DatabaseLockedError:
            timeout = config.getint('general', 'flush_retry_timeout')

            def f(*args):
                self.apply(ui)
            ui.mainloop.set_alarm_in(timeout, f)
            ui.notify('index locked, will try again in %d secs' % timeout)
            ui.update()
            return


class ToggleThreadTagCommand(Command):
    """
    """
    def __init__(self, tag, thread=None, **kwargs):
        assert tag
        self.thread = thread
        self.tag = tag
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        try:
            if self.tag in self.thread.get_tags():
                self.thread.remove_tags([self.tag])
            else:
                self.thread.add_tags([self.tag])
        except DatabaseROError:
            ui.notify('index in read only mode')
            return

        # flush index
        ui.apply_command(FlushCommand())

        # update current buffer
        # TODO: what if changes not yet flushed?
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
                ui.update()
        elif isinstance(cb, buffer.SingleThreadBuffer):
            pass


class SendMailCommand(Command):
    def __init__(self, email=None, envelope=None, **kwargs):
        self.email = email
        self.envelope_buffer = envelope
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        sname, saddr = helper.parse_addr(self.email.get('From'))
        account = get_account_by_address(saddr)
        if account:
            success, reason = account.sender.send_mail(self.email)
            if success:
                if self.envelope_buffer:  # close the envelope
                    cmd = BufferCloseCommand(buffer=self.envelope_buffer)
                    ui.apply_command(cmd)
                ui.notify('mail send successful')
            else:
                ui.notify('failed to send: %s' % reason)
        else:
            ui.notify('failed to send: no account set up for %s' % saddr)


class ComposeCommand(Command):
    def __init__(self, email=None, **kwargs):
        self.email = email
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.email:
            header = {}
            # TODO: fill with default header (per account)
            accounts = get_accounts()
            if len(accounts) == 0:
                ui.notify('no accounts set')
                return
            elif len(accounts) == 1:
                a = accounts[0]
            else:
                while fromaddress not in [a.address for a in accounts]:
                    fromaddress = ui.prompt(prefix='From>')
                a = get_account_by_address(fromaddress)
            header['From'] = "%s <%s>" % (a.realname, a.address)
            header['To'] = ui.prompt(prefix='To>')
            if config.getboolean('general', 'ask_subject'):
                header['Subject'] = ui.prompt(prefix='Subject>')

        def onSuccess():
            f = open(tf.name)
            editor_input = f.read()
            self.email = Parser().parsestr(editor_input)
            f.close()
            os.unlink(tf.name)
            ui.apply_command(OpenEnvelopeCommand(email=self.email))

        tf = tempfile.NamedTemporaryFile(delete=False)
        for i in header.items():
            tf.write('%s: %s\n' % i)
        tf.write('\n\n')
        tf.close()
        ui.apply_command(EditCommand(tf.name, on_success=onSuccess,
                                     refocus=False))


class ThreadTagCommand(Command):
    """prompt the user for labels, then tag thread"""

    def __init__(self, tagsstring=None, **kwargs):
        self.tagsstring = tagsstring
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        thread = ui.current_buffer.get_selected_thread()
        initial_tagstring = ','.join(thread.get_tags())
        if self.tagsstring == None:
            ui.commandprompt('retag ' + initial_tagstring)
        else:
            tags = filter(lambda x: x, self.tagsstring.split(','))
            ui.logger.info("got %s:%s" % (self.tagsstring, tags))
            try:
                thread.set_tags(tags)
            except DatabaseROError, e:
                ui.notify('index in read-only mode')
                return

        # flush index
        ui.apply_command(FlushCommand())

        # refresh selected threadline
        sbuffer = ui.current_buffer
        threadwidget = sbuffer.get_selected_threadline()
        threadwidget.rebuild()  # rebuild and redraw the line


class RefineSearchPromptCommand(Command):
    """refine the query of the currently open searchbuffer"""

    def __init__(self, query=None, **kwargs):
        self.querystring = query
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        if not self.querystring:
            self.querystring = ui.prompt('refine search:', text=oldquery,
                                         completer=completion.QueryCompleter(ui.dbman))
        if self.querystring not in [None, oldquery]:
            sbuffer.querystring = self.querystring
            sbuffer = ui.current_buffer
            sbuffer.rebuild()
            ui.update()
