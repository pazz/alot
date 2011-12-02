import os
import code
import threading
import subprocess
import shlex
import email
import urwid
from twisted.internet import defer
import logging
import argparse

from alot.commands import Command, registerCommand
from alot.completion import CommandLineCompleter
from alot.commands import CommandParseError
from alot.commands import commandfactory
from alot import buffers
from alot import settings
from alot import widgets
from alot import helper
from alot.db import DatabaseLockedError
from alot.completion import ContactsCompleter
from alot.completion import AccountCompleter
from alot.message import encode_header
from alot.message import decode_header
from alot.message import Envelope
from alot import commands

MODE = 'global'


@registerCommand(MODE, 'exit', help='shut alot down cleanly')
class ExitCommand(Command):
    @defer.inlineCallbacks
    def apply(self, ui):
        if settings.config.getboolean('general', 'bug_on_exit'):
            if (yield ui.choice('realy quit?', select='yes', cancel='no',
                               msg_position='left')) == 'no':
                return
        for b in ui.buffers:
            b.cleanup()
        ui.exit()


@registerCommand(MODE, 'search', usage='search query', arguments=[
    (['query'], {'nargs':argparse.REMAINDER, 'help':'search string'})],
    help='open a new search buffer')
class SearchCommand(Command):
    def __init__(self, query, **kwargs):
        self.query = ' '.join(query)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.query:
            open_searches = ui.get_buffers_of_type(buffers.SearchBuffer)
            to_be_focused = None
            for sb in open_searches:
                if sb.querystring == self.query:
                    to_be_focused = sb
            if to_be_focused:
                ui.buffer_focus(to_be_focused)
            else:
                ui.buffer_open(buffers.SearchBuffer(ui, self.query))
        else:
            ui.notify('empty query string')


@registerCommand(MODE, 'prompt',
                 help='prompts for commandline and interprets it upon select',
                 arguments=[
    (['startwith'], {'nargs':'?', 'default':'', 'help':'initial content'})])
class PromptCommand(Command):
    def __init__(self, startwith='', **kwargs):
        self.startwith = startwith
        Command.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def apply(self, ui):
        ui.logger.info('open command shell')
        mode = ui.current_buffer.typename
        cmdline = yield ui.prompt(prefix=':',
                              text=self.startwith,
                              completer=CommandLineCompleter(ui.dbman,
                                                             ui.accountman,
                                                             mode),
                              history=ui.commandprompthistory,
                             )
        ui.logger.debug('CMDLINE: %s' % cmdline)

        # interpret and apply commandline
        if cmdline:
            # save into prompt history
            ui.commandprompthistory.append(cmdline)

            mode = ui.current_buffer.typename
            try:
                cmd = commandfactory(cmdline, mode)
                ui.apply_command(cmd)
            except CommandParseError, e:
                ui.notify(e.message, priority='error')


@registerCommand(MODE, 'refresh', help='refreshes the current buffer')
class RefreshCommand(Command):
    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


@registerCommand(MODE, 'shellescape', arguments=[
    (['--spawn'], {'action': 'store_true', 'help':'run in terminal window'}),
    (['--thread'], {'action': 'store_true', 'help':'run in separate thread'}),
    (['--refocus'], {'action': 'store_true', 'help':'refocus current buffer \
                     after command has finished'}),
    (['cmd'], {'help':'command line to execute'})],
                 help='calls external command')
class ExternalCommand(Command):
    def __init__(self, cmd, path=None, spawn=False, refocus=True,
                 thread=False, on_success=None, **kwargs):
        """
        :param cmd: the command to call
        :type cmd: str
        :param path: a path to a file (or None)
        :type path: str
        :param spawn: run command in a new terminal
        :type spawn: bool
        :param thread: run asynchronously, don't block alot
        :type thread: bool
        :param refocus: refocus calling buffer after cmd termination
        :type refocus: bool
        :param on_success: code to execute after command successfully exited
        :type on_success: callable
        """
        self.commandstring = cmd
        self.path = path
        self.spawn = spawn
        self.refocus = refocus
        self.in_thread = thread
        self.on_success = on_success
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        callerbuffer = ui.current_buffer

        def afterwards(data):
            if data == 'success':
                if callable(self.on_success):
                    self.on_success()
            else:
                ui.notify(data, priority='error')
            if self.refocus and callerbuffer in ui.buffers:
                ui.logger.info('refocussing')
                ui.buffer_focus(callerbuffer)

        write_fd = ui.mainloop.watch_pipe(afterwards)

        def thread_code(*args):
            if self.path:
                if '{}' in self.commandstring:
                    cmd = self.commandstring.replace('{}',
                            helper.shell_quote(self.path))
                else:
                    cmd = '%s %s' % (self.commandstring,
                                     helper.shell_quote(self.path))
            else:
                cmd = self.commandstring

            if self.spawn:
                cmd = '%s %s' % (settings.config.get('general',
                                                     'terminal_cmd'),
                                 cmd)
            cmd = cmd.encode('utf-8', errors='ignore')
            ui.logger.info('calling external command: %s' % cmd)
            try:
                if 0 == subprocess.call(shlex.split(cmd)):
                    os.write(write_fd, 'success')
            except OSError, e:
                os.write(write_fd, str(e))

        if self.in_thread:
            thread = threading.Thread(target=thread_code)
            thread.start()
        else:
            ui.mainloop.screen.stop()
            thread_code()
            ui.mainloop.screen.start()


#@registerCommand(MODE, 'edit', arguments=[
#    (['--nospawn'], {'action': 'store_true', 'help':'spawn '}), #todo
#    (['path'], {'help':'file to edit'})]
#]
#)
class EditCommand(ExternalCommand):
    """opens editor"""
    def __init__(self, path, spawn=None, thread=None, **kwargs):
        self.path = path
        if spawn != None:
            self.spawn = spawn
        else:
            self.spawn = settings.config.getboolean('general', 'editor_spawn')
        if thread != None:
            self.thread = thread
        else:
            self.thread = settings.config.getboolean('general',
                                                     'editor_in_thread')

        self.editor_cmd = None
        if os.path.isfile('/usr/bin/editor'):
            self.editor_cmd = '/usr/bin/editor'
        self.editor_cmd = os.environ.get('EDITOR', self.editor_cmd)
        self.editor_cmd = settings.config.get('general', 'editor_cmd',
                                         fallback=self.editor_cmd)
        logging.debug('using editor_cmd: %s' % self.editor_cmd)

        ExternalCommand.__init__(self, self.editor_cmd, path=self.path,
                                 spawn=self.spawn, thread=self.thread,
                                 **kwargs)

    def apply(self, ui):
        if self.editor_cmd == None:
            ui.notify('no editor set', priority='error')
        else:
            return ExternalCommand.apply(self, ui)


@registerCommand(MODE, 'pyshell',
                 help="opens an interactive python shell for introspection")
class PythonShellCommand(Command):
    def apply(self, ui):
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()


@registerCommand(MODE, 'bclose',
                 help="close current buffer or exit if it is the last")
class BufferCloseCommand(Command):
    def apply(self, ui):
        selected = ui.current_buffer
        ui.buffer_close(selected)


@registerCommand(MODE, 'bprevious', forced={'offset': -1},
                 help='focus previous buffer')
@registerCommand(MODE, 'bnext', forced={'offset': +1},
                 help='focus next buffer')
class BufferFocusCommand(Command):
    def __init__(self, buffer=None, offset=0, **kwargs):
        """
        :param buffer: the buffer to focus
        :type buffer: `alot.buffers.Buffer`
        """
        self.buffer = buffer
        self.offset = offset
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.offset:
            idx = ui.buffers.index(ui.current_buffer)
            num = len(ui.buffers)
            self.buffer = ui.buffers[(idx + self.offset) % num]
        ui.buffer_focus(self.buffer)


@registerCommand(MODE, 'bufferlist', help='opens buffer list')
class OpenBufferlistCommand(Command):
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        blists = ui.get_buffers_of_type(buffers.BufferlistBuffer)
        if blists:
            ui.buffer_focus(blists[0])
        else:
            bl = buffers.BufferlistBuffer(ui, self.filtfun)
            ui.buffer_open(bl)
            bl.rebuild()


@registerCommand(MODE, 'taglist', help='opens taglist buffer')
class TagListCommand(Command):
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        tags = ui.dbman.get_all_tags()
        buf = buffers.TagListBuffer(ui, tags, self.filtfun)
        ui.buffers.append(buf)
        buf.rebuild()
        ui.buffer_focus(buf)


@registerCommand(MODE, 'flush',
                 help='Flushes write operations or retries until committed')
class FlushCommand(Command):
    def apply(self, ui):
        try:
            ui.dbman.flush()
        except DatabaseLockedError:
            timeout = settings.config.getint('general', 'flush_retry_timeout')

            def f(*args):
                self.apply(ui)
            ui.mainloop.set_alarm_in(timeout, f)
            ui.notify('index locked, will try again in %d secs' % timeout)
            ui.update()
            return


#todo choices
@registerCommand(MODE, 'help', arguments=[
    (['commandname'], {'help':'command or \'bindings\''})],
                 help='display help for a command. Use \'bindings\' to\
                 display all keybings interpreted in current mode.',
)
class HelpCommand(Command):
    def __init__(self, commandname='', **kwargs):
        Command.__init__(self, **kwargs)
        self.commandname = commandname

    def apply(self, ui):
        ui.logger.debug('HELP')
        if self.commandname == 'bindings':
            # get mappings
            modemaps = dict(settings.config.items('%s-maps' % ui.mode))
            globalmaps = dict(settings.config.items('global-maps'))

            # build table
            maxkeylength = len(max((modemaps).keys() + globalmaps.keys(),
                                   key=len))
            keycolumnwidth = maxkeylength + 2

            linewidgets = []
            # mode specific maps
            linewidgets.append(urwid.Text(('help_section',
                                '\n%s-mode specific maps' % ui.mode)))
            for (k, v) in modemaps.items():
                line = urwid.Columns([('fixed', keycolumnwidth, urwid.Text(k)),
                                      urwid.Text(v)])
                linewidgets.append(line)

            # global maps
            linewidgets.append(urwid.Text(('help_section',
                                           '\nglobal maps')))
            for (k, v) in globalmaps.items():
                if k not in modemaps:
                    line = urwid.Columns(
                        [('fixed', keycolumnwidth, urwid.Text(k)),
                         urwid.Text(v)])
                    linewidgets.append(line)

            body = urwid.ListBox(linewidgets)
            ckey = 'cancel'
            titletext = 'Bindings Help (%s cancels)' % ckey

            box = widgets.DialogBox(body, titletext,
                                    bodyattr='help_text',
                                    titleattr='help_title')

            # put promptwidget as overlay on main widget
            overlay = urwid.Overlay(box, ui.mainframe, 'center',
                                    ('relative', 70), 'middle',
                                    ('relative', 70))
            ui.show_as_root_until_keypress(overlay, 'cancel')
        else:
            ui.logger.debug('HELP %s' % self.commandname)
            parser = commands.lookup_parser(self.commandname, ui.mode)
            if parser:
                ui.notify(parser.format_help(), block=True)
            else:
                ui.notify('command not known: %s' % self.commandname,
                          priority='error')


@registerCommand(MODE, 'compose', help='compose a new email',
                 arguments=[
    (['--sender'], {'nargs': '?', 'help':'sender'}),
    (['--template'], {'nargs':'?',
                      'help':'path to a template message file'}),
    (['--subject'], {'nargs':'?', 'help':'subject line'}),
    (['--to'], {'nargs':'+', 'help':'recipients'}),
    (['--cc'], {'nargs':'+', 'help':'copy to'}),
    (['--bcc'], {'nargs':'+', 'help':'blind copy to'}),
])
class ComposeCommand(Command):
    def __init__(self, envelope=None, headers={}, template=None,
                 sender=u'', subject=u'', to=[], cc=[], bcc=[],
                 **kwargs):
        Command.__init__(self, **kwargs)

        self.envelope = envelope
        self.template = template
        self.headers = headers
        self.sender = sender
        self.subject = subject
        self.to = to
        self.cc = cc
        self.bcc = bcc

    @defer.inlineCallbacks
    def apply(self, ui):
        if self.envelope == None:
            self.envelope = Envelope()
        if self.template is not None:
            #get location of tempsdir, containing msg templates
            tempdir = settings.config.get('general', 'template_dir')
            tempdir = os.path.expanduser(tempdir)
            if not tempdir:
                xdgdir = os.environ.get('XDG_CONFIG_HOME',
                                        os.path.expanduser('~/.config'))
                tempdir = os.path.join(xdgdir, 'alot', 'templates')

            path = os.path.expanduser(self.template)
            if not os.path.dirname(path):  # use tempsdir
                if not os.path.isdir(tempdir):
                    ui.notify('no templates directory: %s' % tempdir,
                              priority='error')
                    return
                path = os.path.join(tempdir, path)

            if not os.path.isfile(path):
                ui.notify('could not find template: %s' % path,
                          priority='error')
                return
            try:
                self.envelope.parse_template(open(path).read())
            except Exception, e:
                ui.notify(str(e), priority='error')
                return

        # set forced headers
        for key, value in self.headers.items():
            self.envelope.headers[key] = encode_header(key, value)

        # set forced headers for separate parameters
        if self.sender:
            self.envelope['From'] = encode_header('From', self.sender)
        if self.subject:
            self.envelope['Subject'] = encode_header('Subject', self.subject)
        if self.to:
            self.envelope['To'] = encode_header('To', ','.join(self.to))
        if self.cc:
            self.envelope['Cc'] = encode_header('Cc', ','.join(self.cc))
        if self.bcc:
            self.envelope['Bcc'] = encode_header('Bcc', ','.join(self.bcc))

        # get missing From header
        if not 'From' in self.envelope.headers:
            accounts = ui.accountman.get_accounts()
            if len(accounts) == 1:
                a = accounts[0]
                fromstring = "%s <%s>" % (a.realname, a.address)
                self.envelope['From'] = encode_header('From', fromstring)
            else:
                cmpl = AccountCompleter(ui.accountman)
                fromaddress = yield ui.prompt(prefix='From>', completer=cmpl,
                                              tab=1)
                if fromaddress is None:
                    ui.notify('canceled')
                    return
                a = ui.accountman.get_account_by_address(fromaddress)
                if a is not None:
                    fromstring = "%s <%s>" % (a.realname, a.address)
                    self.envelope['From'] = encode_header('From', fromstring)
                else:
                    self.envelope.headers['From'] = fromaddress

        # get missing To header
        if 'To' not in self.envelope.headers:
            sender = decode_header(self.envelope.headers.get('From'))
            name, addr = email.Utils.parseaddr(sender)
            a = ui.accountman.get_account_by_address(addr)

            allbooks = not settings.config.getboolean('general',
                                'complete_matching_abook_only')
            ui.logger.debug(allbooks)
            abooks = ui.accountman.get_addressbooks(order=[a],
                                                    append_remaining=allbooks)
            ui.logger.debug(abooks)
            to = yield ui.prompt(prefix='To>',
                                 completer=ContactsCompleter(abooks))
            if to == None:
                ui.notify('canceled')
                return
            self.envelope.headers['To'] = encode_header('to', to)
        if settings.config.getboolean('general', 'ask_subject') and \
           not 'Subject' in self.envelope.headers:
            subject = yield ui.prompt(prefix='Subject>')
            if subject == None:
                ui.notify('canceled')
                return
            self.envelope['Subject'] = encode_header('subject', subject)
        cmd = commands.envelope.EditCommand(envelope=self.envelope)
        ui.apply_command(cmd)


@registerCommand(MODE, 'move', help='move focus', arguments=[
    (['key'], {'nargs':'+', 'help':'direction'})])
@registerCommand(MODE, 'cancel', help='send cancel event',
                 forced={'key': 'cancel'})
@registerCommand(MODE, 'select', help='send select event',
                 forced={'key': 'select'})
class SendKeypressCommand(Command):
    def __init__(self, key, **kwargs):
        Command.__init__(self, **kwargs)
        if isinstance(key, list):
            key = ' '.join(key)
        self.key = key

    def apply(self, ui):
        ui.keypress(self.key)
