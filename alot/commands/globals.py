# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import code
import email
import email.utils
import glob
import logging
import os
import subprocess
from io import BytesIO
import asyncio
import shlex

import urwid

from . import Command, registerCommand
from . import CommandCanceled
from .utils import update_keys
from .. import commands

from .. import buffers
from .. import helper
from ..helper import split_commandstring
from ..helper import mailto_to_envelope
from ..completion.commandline import CommandLineCompleter
from ..completion.contacts import ContactsCompleter
from ..completion.accounts import AccountCompleter
from ..completion.tags import TagsCompleter
from ..widgets.utils import DialogBox
from ..db.errors import DatabaseLockedError
from ..db.envelope import Envelope
from ..settings.const import settings
from ..settings.errors import ConfigError, NoMatchingAccount
from ..utils import argparse as cargparse

MODE = 'global'


@registerCommand(MODE, 'exit', help="shut down cleanly")
class ExitCommand(Command):
    """Shut down cleanly."""

    def __init__(self, _prompt=True, **kwargs):
        """
        :param _prompt: For internal use only, used to control prompting to
                        close without sending, and is used by the
                        BufferCloseCommand if settings change after yielding to
                        the UI.
        :type _prompt: bool
        """
        super(ExitCommand, self).__init__(**kwargs)
        self.prompt_to_send = _prompt

    async def apply(self, ui):
        if settings.get('bug_on_exit'):
            msg = 'really quit?'
            if (await ui.choice(msg, select='yes', cancel='no',
                                msg_position='left')) == 'no':
                return

        # check if there are any unsent messages
        if self.prompt_to_send:
            for buffer in ui.buffers:
                if (isinstance(buffer, buffers.EnvelopeBuffer) and
                        not buffer.envelope.sent_time):
                    msg = 'quit without sending message?'
                    if (await ui.choice(msg, cancel='no',
                                        msg_position='left')) == 'no':
                        raise CommandCanceled()

        for b in ui.buffers:
            b.cleanup()
        await ui.apply_command(FlushCommand(callback=ui.exit))
        ui.cleanup()

        if ui.db_was_locked:
            msg = 'Database locked. Exit without saving?'
            response = await ui.choice(msg, msg_position='left', cancel='no')
            if response == 'no':
                return
            ui.exit()


@registerCommand(MODE, 'search', usage='search query', arguments=[
    (['--sort'], {'help': 'sort order', 'choices': [
        'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['query'], {'nargs': argparse.REMAINDER, 'help': 'search string'})])
class SearchCommand(Command):

    """open a new search buffer. Search obeys the notmuch
    :ref:`search.exclude_tags <search.exclude_tags>` setting."""
    repeatable = True

    def __init__(self, query, sort=None, **kwargs):
        """
        :param query: notmuch querystring
        :type query: str
        :param sort: how to order results. Must be one of
                     'oldest_first', 'newest_first', 'message_id' or
                     'unsorted'.
        :type sort: str
        """
        self.query = ' '.join(query)
        self.order = sort
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.query:
            open_searches = ui.get_buffers_of_type(buffers.SearchBuffer)
            to_be_focused = None
            for sb in open_searches:
                if sb.querystring == self.query:
                    to_be_focused = sb
            if to_be_focused:
                if ui.current_buffer != to_be_focused:
                    ui.buffer_focus(to_be_focused)
                else:
                    # refresh an already displayed search
                    ui.current_buffer.rebuild()
                    ui.update()
            else:
                ui.buffer_open(buffers.SearchBuffer(ui, self.query,
                                                    sort_order=self.order))
        else:
            ui.notify('empty query string')


@registerCommand(MODE, 'prompt', arguments=[
    (['startwith'], {'nargs': '?', 'default': '', 'help': 'initial content'})])
class PromptCommand(Command):

    """prompts for commandline and interprets it upon select"""
    def __init__(self, startwith='', **kwargs):
        """
        :param startwith: initial content of the prompt widget
        :type startwith: str
        """
        self.startwith = startwith
        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        logging.info('open command shell')
        mode = ui.mode or 'global'
        cmpl = CommandLineCompleter(ui.dbman, mode, ui.current_buffer)
        cmdline = await ui.prompt(
            '',
            text=self.startwith,
            completer=cmpl,
            history=ui.commandprompthistory)
        logging.debug('CMDLINE: %s', cmdline)

        # interpret and apply commandline
        if cmdline:
            # save into prompt history
            ui.commandprompthistory.append(cmdline)
            await ui.apply_commandline(cmdline)
        else:
            raise CommandCanceled()


@registerCommand(MODE, 'refresh')
class RefreshCommand(Command):

    """refresh the current buffer"""
    repeatable = True

    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


@registerCommand(
    MODE, 'shellescape', arguments=[
        (['--spawn'], {'action': cargparse.BooleanAction, 'default': None,
                       'help': 'run in terminal window'}),
        (['--thread'], {'action': cargparse.BooleanAction, 'default': None,
                        'help': 'run in separate thread'}),
        (['--refocus'], {'action': cargparse.BooleanAction,
                         'help': 'refocus current buffer after command '
                                 'has finished'}),
        (['cmd'], {'help': 'command line to execute'})],
    forced={'shell': True},
)
class ExternalCommand(Command):

    """run external command"""
    repeatable = True

    def __init__(self, cmd, stdin=None, shell=False, spawn=False,
                 refocus=True, thread=False, on_success=None, **kwargs):
        """
        :param cmd: the command to call
        :type cmd: list or str
        :param stdin: input to pipe to the process
        :type stdin: file or str
        :param spawn: run command in a new terminal
        :type spawn: bool
        :param shell: let shell interpret command string
        :type shell: bool
        :param thread: run asynchronously, don't block alot
        :type thread: bool
        :param refocus: refocus calling buffer after cmd termination
        :type refocus: bool
        :param on_success: code to execute after command successfully exited
        :type on_success: callable
        """
        logging.debug({'spawn': spawn})
        # make sure cmd is a list of str
        if isinstance(cmd, str):
            # convert cmdstring to list: in case shell==True,
            # Popen passes only the first item in the list to $SHELL
            cmd = [cmd] if shell else split_commandstring(cmd)

        # determine complete command list to pass
        touchhook = settings.get_hook('touch_external_cmdlist')
        # filter cmd, shell and thread through hook if defined
        if touchhook is not None:
            logging.debug('calling hook: touch_external_cmdlist')
            res = touchhook(cmd, shell=shell, spawn=spawn, thread=thread)
            logging.debug('got: %s', res)
            cmd, shell, self.in_thread = res
        # otherwise if spawn requested and X11 is running
        elif spawn:
            if 'DISPLAY' in os.environ:
                term_cmd = settings.get('terminal_cmd', '')
                logging.info('spawn in terminal: %s', term_cmd)
                termcmdlist = split_commandstring(term_cmd)
                cmd = termcmdlist + cmd
            else:
                thread = False

        self.cmdlist = cmd
        self.stdin = stdin
        self.shell = shell
        self.refocus = refocus
        self.in_thread = thread
        self.on_success = on_success
        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        logging.debug('cmdlist: %s', self.cmdlist)
        callerbuffer = ui.current_buffer

        # set standard input for subcommand
        stdin = None
        if self.stdin is not None:
            # wrap strings in StrinIO so that they behaves like a file
            if isinstance(self.stdin, str):
                # XXX: is utf-8 always safe to use here, or do we need to check
                # the terminal encoding first?
                stdin = BytesIO(self.stdin.encode('utf-8'))
            else:
                stdin = self.stdin

        logging.info('calling external command: %s', self.cmdlist)

        ret = ''
        # TODO: these can probably be refactored in terms of helper.call_cmd
        # and helper.call_cmd_async
        if self.in_thread:
            try:
                if self.shell:
                    _cmd = asyncio.create_subprocess_shell
                    # The shell function wants a single string or bytestring,
                    # we could just join it, but lets be extra safe and use
                    # shlex.quote to avoid suprises.
                    cmdlist = [shlex.quote(' '.join(self.cmdlist))]
                else:
                    _cmd = asyncio.create_subprocess_exec
                    cmdlist = self.cmdlist
                proc = await _cmd(
                    *cmdlist,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE if stdin else None)
            except OSError as e:
                ret = str(e)
            else:
                _, err = await proc.communicate(stdin.read() if stdin else None)
                if proc.returncode == 0:
                    ret = 'success'
                elif err:
                    ret = err.decode(urwid.util.detected_encoding)
        else:
            with ui.paused():
                try:
                    proc = subprocess.Popen(
                        self.cmdlist, shell=self.shell,
                        stdin=subprocess.PIPE if stdin else None,
                        stderr=subprocess.PIPE)
                except OSError as e:
                    ret = str(e)
                else:
                    _, err = proc.communicate(stdin.read() if stdin else None)
                if proc.returncode == 0:
                    ret = 'success'
                elif err:
                    ret = err.decode(urwid.util.detected_encoding)

        if ret == 'success':
            if self.on_success is not None:
                self.on_success()
        else:
            ui.notify(ret, priority='error')
        if self.refocus and callerbuffer in ui.buffers:
            logging.info('refocussing')
            ui.buffer_focus(callerbuffer)


class EditCommand(ExternalCommand):

    """edit a file"""
    def __init__(self, path, spawn=None, thread=None, **kwargs):
        """
        :param path: path to the file to be edited
        :type path: str
        :param spawn: force running edtor in a new terminal
        :type spawn: bool
        :param thread: run asynchronously, don't block alot
        :type thread: bool
        """
        self.spawn = spawn
        if spawn is None:
            self.spawn = settings.get('editor_spawn')
        self.thread = thread
        if thread is None:
            self.thread = settings.get('editor_in_thread')

        editor_cmdstring = None
        if os.path.isfile('/usr/bin/editor'):
            editor_cmdstring = '/usr/bin/editor'
        editor_cmdstring = os.environ.get('EDITOR', editor_cmdstring)
        editor_cmdstring = settings.get('editor_cmd') or editor_cmdstring
        logging.debug('using editor_cmd: %s', editor_cmdstring)

        self.cmdlist = None
        if '%s' in editor_cmdstring:
            cmdstring = editor_cmdstring.replace('%s',
                                                 helper.shell_quote(path))
            self.cmdlist = split_commandstring(cmdstring)
        else:
            self.cmdlist = split_commandstring(editor_cmdstring) + [path]

        logging.debug({'spawn: ': self.spawn, 'in_thread': self.thread})
        ExternalCommand.__init__(self, self.cmdlist,
                                 spawn=self.spawn, thread=self.thread,
                                 **kwargs)

    async def apply(self, ui):
        if self.cmdlist is None:
            ui.notify('no editor set', priority='error')
        else:
            return await ExternalCommand.apply(self, ui)


@registerCommand(MODE, 'pyshell')
class PythonShellCommand(Command):

    """open an interactive python shell for introspection"""
    repeatable = True

    def apply(self, ui):
        with ui.paused():
            code.interact(local=locals())


@registerCommand(MODE, 'repeat')
class RepeatCommand(Command):

    """repeat the command executed last time"""
    def __init__(self, **kwargs):
        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        if ui.last_commandline is not None:
            await ui.apply_commandline(ui.last_commandline)
        else:
            ui.notify('no last command')


@registerCommand(MODE, 'call', arguments=[
    (['command'], {'help': 'python command string to call'})])
class CallCommand(Command):

    """execute python code"""
    repeatable = True

    def __init__(self, command, **kwargs):
        """
        :param command: python command string to call
        :type command: str
        """
        Command.__init__(self, **kwargs)
        self.command = command

    async def apply(self, ui):
        try:
            hooks = settings.hooks
            if hooks:
                env = {'ui': ui, 'settings': settings}
                for k, v in env.items():
                    if not getattr(hooks, k, None):
                        setattr(hooks, k, v)

            t = eval(self.command)
            if asyncio.iscoroutine(t):
                await t
        except Exception as e:
            logging.exception(e)
            msg = 'an error occurred during execution of "%s":\n%s'
            ui.notify(msg % (self.command, e), priority='error')


@registerCommand(MODE, 'bclose', arguments=[
    (['--redraw'],
     {'action': cargparse.BooleanAction,
      'help': 'redraw current buffer after command has finished'}),
    (['--force'],
     {'action': 'store_true', 'help': 'never ask for confirmation'})])
class BufferCloseCommand(Command):

    """close a buffer"""
    repeatable = True

    def __init__(self, buffer=None, force=False, redraw=True, **kwargs):
        """
        :param buffer: the buffer to close or None for current
        :type buffer: `alot.buffers.Buffer`
        :param force: force buffer close
        :type force: bool
        """
        self.buffer = buffer
        self.force = force
        self.redraw = redraw
        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        async def one_buffer(prompt=True):
            """Helper to handle the case on only one buffer being opened.

            prompt is a boolean that is passed to ExitCommand() as the _prompt
            keyword argument.
            """
            # If there is only one buffer and the settings don't allow using
            # closebuffer to exit, then just stop.
            if not settings.get('quit_on_last_bclose'):
                msg = ('not closing last remaining buffer as '
                       'global.quit_on_last_bclose is set to False')
                logging.info(msg)
                ui.notify(msg, priority='error')
            # Otherwise pass directly to exit command, which also prommpts for
            # 'close without sending'
            else:
                logging.info('closing the last buffer, exiting')
                await ui.apply_command(ExitCommand(_prompt=prompt))

        if self.buffer is None:
            self.buffer = ui.current_buffer

        if len(ui.buffers) == 1:
            await one_buffer()
            return

        if (isinstance(self.buffer, buffers.EnvelopeBuffer) and
                not self.buffer.envelope.sent_time):
            msg = 'close without sending?'
            if (not self.force and (await ui.choice(msg, cancel='no',
                                                    msg_position='left')) ==
                    'no'):
                raise CommandCanceled()

        # Because we await above it is possible that the settings or the number
        # of buffers chould change, so retest.
        if len(ui.buffers) == 1:
            await one_buffer(prompt=False)
        else:
            ui.buffer_close(self.buffer, self.redraw)


@registerCommand(MODE, 'bprevious', forced={'offset': -1},
                 help='focus previous buffer')
@registerCommand(MODE, 'bnext', forced={'offset': +1},
                 help='focus next buffer')
@registerCommand(
    MODE, 'buffer',
    arguments=[(['index'], {'type': int, 'help': 'buffer index to focus'})],
    help='focus buffer with given index')
class BufferFocusCommand(Command):

    """focus a :class:`~alot.buffers.Buffer`"""
    repeatable = True

    def __init__(self, buffer=None, index=None, offset=0, **kwargs):
        """
        :param buffer: the buffer to focus or None
        :type buffer: `alot.buffers.Buffer`
        :param index: index (in bufferlist) of the buffer to focus.
        :type index: int
        :param offset: position of the buffer to focus relative to the
                       currently focussed one. This is used only if `buffer`
                       is set to `None`
        :type offset: int
        """
        self.buffer = buffer
        self.index = index
        self.offset = offset
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.buffer is None:
            if self.index is not None:
                try:
                    self.buffer = ui.buffers[self.index]
                except IndexError:
                    ui.notify('no buffer exists at index %d' % self.index)
                    return
            else:
                self.index = ui.buffers.index(ui.current_buffer)
            num = len(ui.buffers)
            self.buffer = ui.buffers[(self.index + self.offset) % num]
        ui.buffer_focus(self.buffer)


@registerCommand(MODE, 'bufferlist')
class OpenBufferlistCommand(Command):

    """open a list of active buffers"""
    def __init__(self, filtfun=lambda x: x, **kwargs):
        """
        :param filtfun: filter to apply to displayed list
        :type filtfun: callable (str->bool)
        """
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        blists = ui.get_buffers_of_type(buffers.BufferlistBuffer)
        if blists:
            ui.buffer_focus(blists[0])
        else:
            bl = buffers.BufferlistBuffer(ui, self.filtfun)
            ui.buffer_open(bl)


@registerCommand(MODE, 'taglist', arguments=[
    (['--tags'], {'nargs': '+', 'help': 'tags to display'}),
])
class TagListCommand(Command):

    """opens taglist buffer"""
    def __init__(self, filtfun=lambda x: x, tags=None, **kwargs):
        """
        :param filtfun: filter to apply to displayed list
        :type filtfun: callable (str->bool)
        """
        self.filtfun = filtfun
        self.tags = tags
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        tags = self.tags or ui.dbman.get_all_tags()
        blists = ui.get_buffers_of_type(buffers.TagListBuffer)
        if blists:
            buf = blists[0]
            buf.tags = tags
            buf.rebuild()
            ui.buffer_focus(buf)
        else:
            ui.buffer_open(buffers.TagListBuffer(ui, tags, self.filtfun))


@registerCommand(MODE, 'namedqueries')
class NamedQueriesCommand(Command):
    """opens named queries buffer"""
    def __init__(self, filtfun=bool, **kwargs):
        """
        :param filtfun: filter to apply to displayed list
        :type filtfun: callable (str->bool)
        """
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.buffer_open(buffers.NamedQueriesBuffer(ui, self.filtfun))


@registerCommand(MODE, 'flush')
class FlushCommand(Command):

    """flush write operations or retry until committed"""
    repeatable = True

    def __init__(self, callback=None, silent=False, **kwargs):
        """
        :param callback: function to call after successful writeout
        :type callback: callable
        """
        Command.__init__(self, **kwargs)
        self.callback = callback
        self.silent = silent

    def apply(self, ui):
        try:
            ui.dbman.flush()
            if callable(self.callback):
                self.callback()
            logging.debug('flush complete')
            if ui.db_was_locked:
                if not self.silent:
                    ui.notify('changes flushed')
                ui.db_was_locked = False
            ui.update()

        except DatabaseLockedError:
            timeout = settings.get('flush_retry_timeout')

            if timeout > 0:
                def f(*_):
                    self.apply(ui)
                ui.mainloop.set_alarm_in(timeout, f)
                if not ui.db_was_locked:
                    if not self.silent:
                        ui.notify('index locked, will try again in %d secs'
                                  % timeout)
                    ui.db_was_locked = True
            ui.update()
            return


# TODO: choices
@registerCommand(MODE, 'help', arguments=[
    (['commandname'], {'help': 'command or \'bindings\''})])
class HelpCommand(Command):

    """display help for a command (use \'bindings\' to display all keybindings
    interpreted in current mode)"""
    def __init__(self, commandname='', **kwargs):
        """
        :param commandname: command to document
        :type commandname: str
        """
        Command.__init__(self, **kwargs)
        self.commandname = commandname

    def apply(self, ui):
        logging.debug('HELP')
        if self.commandname == 'bindings':
            text_att = settings.get_theming_attribute('help', 'text')
            title_att = settings.get_theming_attribute('help', 'title')
            section_att = settings.get_theming_attribute('help', 'section')
            # get mappings
            globalmaps, modemaps = settings.get_keybindings(ui.mode)

            # build table
            maxkeylength = len(
                max(list(modemaps.keys()) + list(globalmaps.keys()), key=len))
            keycolumnwidth = maxkeylength + 2

            linewidgets = []
            # mode specific maps
            if modemaps:
                txt = (section_att, '\n%s-mode specific maps' % ui.mode)
                linewidgets.append(urwid.Text(txt))
                for (k, v) in modemaps.items():
                    line = urwid.Columns([('fixed', keycolumnwidth,
                                           urwid.Text((text_att, k))),
                                          urwid.Text((text_att, v))])
                    linewidgets.append(line)

            # global maps
            linewidgets.append(urwid.Text((section_att, '\nglobal maps')))
            for (k, v) in globalmaps.items():
                if k not in modemaps:
                    line = urwid.Columns(
                        [('fixed', keycolumnwidth, urwid.Text((text_att, k))),
                         urwid.Text((text_att, v))])
                    linewidgets.append(line)

            body = urwid.ListBox(linewidgets)
            titletext = 'Bindings Help (escape cancels)'

            box = DialogBox(body, titletext,
                            bodyattr=text_att,
                            titleattr=title_att)

            # put promptwidget as overlay on main widget
            overlay = urwid.Overlay(box, ui.root_widget, 'center',
                                    ('relative', 70), 'middle',
                                    ('relative', 70))
            ui.show_as_root_until_keypress(overlay, 'esc')
        else:
            logging.debug('HELP %s', self.commandname)
            parser = commands.lookup_parser(self.commandname, ui.mode)
            if parser:
                ui.notify(parser.format_help(), block=True)
            else:
                ui.notify('command not known: %s' % self.commandname,
                          priority='error')


@registerCommand(MODE, 'compose', arguments=[
    (['--sender'], {'nargs': '?', 'help': 'sender'}),
    (['--template'], {'nargs': '?',
                      'help': 'path to a template message file'}),
    (['--tags'], {'nargs': '?',
                  'help': 'comma-separated list of tags to apply to message'}),
    (['--subject'], {'nargs': '?', 'help': 'subject line'}),
    (['--to'], {'nargs': '+', 'help': 'recipients'}),
    (['--cc'], {'nargs': '+', 'help': 'copy to'}),
    (['--bcc'], {'nargs': '+', 'help': 'blind copy to'}),
    (['--attach'], {'nargs': '+', 'help': 'attach files'}),
    (['--omit_signature'], {'action': 'store_true',
                            'help': 'do not add signature'}),
    (['--spawn'], {'action': cargparse.BooleanAction, 'default': None,
                   'help': 'spawn editor in new terminal'}),
    (['rest'], {'nargs': '*'}),
])
class ComposeCommand(Command):

    """compose a new email"""
    def __init__(
            self,
            envelope=None, headers=None, template=None, sender=u'',
            tags=None, subject=u'', to=None, cc=None, bcc=None, attach=None,
            omit_signature=False, spawn=None, rest=None, encrypt=False,
            **kwargs):
        """
        :param envelope: use existing envelope
        :type envelope: :class:`~alot.db.envelope.Envelope`
        :param headers: forced header values
        :type headers: dict (str->str)
        :param template: name of template to parse into the envelope after
                         creation. This should be the name of a file in your
                         template_dir
        :type template: str
        :param sender: From-header value
        :type sender: str
        :param tags: Comma-separated list of tags to apply to message
        :type tags: list(str)
        :param subject: Subject-header value
        :type subject: str
        :param to: To-header value
        :type to: str
        :param cc: Cc-header value
        :type cc: str
        :param bcc: Bcc-header value
        :type bcc: str
        :param attach: Path to files to be attached (globable)
        :type attach: str
        :param omit_signature: do not attach/append signature
        :type omit_signature: bool
        :param spawn: force spawning of editor in a new terminal
        :type spawn: bool
        :param rest: remaining parameters. These can start with
                     'mailto' in which case it is interpreted as mailto string.
                     Otherwise it will be interpreted as recipients (to) header
        :type rest: list(str)
        :param encrypt: if the email should be encrypted
        :type encrypt: bool
        """

        Command.__init__(self, **kwargs)

        self.envelope = envelope
        self.template = template
        self.headers = headers or {}
        self.sender = sender
        self.subject = subject
        self.to = to or []
        self.cc = cc or []
        self.bcc = bcc or []
        self.attach = attach
        self.omit_signature = omit_signature
        self.force_spawn = spawn
        self.rest = ' '.join(rest or [])
        self.encrypt = encrypt
        self.tags = tags

    class ApplyError(Exception):
        pass

    def _get_template(self, ui):
        # get location of tempsdir, containing msg templates
        tempdir = settings.get('template_dir')

        path = os.path.expanduser(self.template)
        if not os.path.dirname(path):  # use tempsdir
            if not os.path.isdir(tempdir):
                ui.notify('no templates directory: %s' % tempdir,
                          priority='error')
                raise self.ApplyError()
            path = os.path.join(tempdir, path)

        if not os.path.isfile(path):
            ui.notify('could not find template: %s' % path,
                      priority='error')
            raise self.ApplyError()
        try:
            with open(path, 'rb') as f:
                template = helper.try_decode(f.read())
            self.envelope.parse_template(template)
        except Exception as e:
            ui.notify(str(e), priority='error')
            raise self.ApplyError()

    async def _get_sender_details(self, ui):
        # find out the right account, if possible yet
        account = self.envelope.account
        if account is None:
            accounts = settings.get_accounts()
            if not accounts:
                ui.notify('no accounts set.', priority='error')
                return
            elif len(accounts) == 1:
                account = accounts[0]

        # get missing From header
        if 'From' not in self.envelope.headers:
            if account is not None:
                fromstring = email.utils.formataddr(
                    (account.realname, str(account.address)))
                self.envelope.add('From', fromstring)
            else:
                cmpl = AccountCompleter()
                fromaddress = await ui.prompt('From', completer=cmpl,
                                              tab=1, history=ui.senderhistory)
                if fromaddress is None:
                    raise CommandCanceled()

                ui.senderhistory.append(fromaddress)
                self.envelope.add('From', fromaddress)
        else:
            fromaddress = self.envelope.get("From")

        # try to find the account again
        if account is None:
            try:
                account = settings.account_matching_address(fromaddress)
            except NoMatchingAccount:
                msg = 'Cannot compose mail - ' \
                      'no account found for `%s`' % fromaddress
                logging.error(msg)
                ui.notify(msg, priority='error')
                raise CommandCanceled()
        if self.envelope.account is None:
            self.envelope.account = account

    async def _set_signature(self, ui):
        account = self.envelope.account
        if not self.omit_signature and account.signature:
            logging.debug('has signature')
            sig = os.path.expanduser(account.signature)
            if os.path.isfile(sig):
                logging.debug('is file')
                if account.signature_as_attachment:
                    name = account.signature_filename or None
                    self.envelope.attach(sig, filename=name)
                    logging.debug('attached')
                else:
                    with open(sig, 'rb') as f:
                        sigcontent = f.read()
                    mimetype = helper.guess_mimetype(sigcontent)
                    if mimetype.startswith('text'):
                        sigcontent = helper.try_decode(sigcontent)
                        self.envelope.body += '\n' + sigcontent
            else:
                ui.notify('could not locate signature: %s' % sig,
                          priority='error')
                if (await ui.choice('send without signature?', 'yes',
                                    'no')) == 'no':
                    raise self.ApplyError

    async def apply(self, ui):
        try:
            await self.__apply(ui)
        except self.ApplyError:
            return

    def _get_account(self, ui):
        # find out the right account
        sender = self.envelope.get('From')
        _, addr = email.utils.parseaddr(sender)
        try:
            account = settings.get_account_by_address(addr)
        except NoMatchingAccount:
            msg = 'Cannot compose mail - no account found for `%s`' % addr
            logging.error(msg)
            ui.notify(msg, priority='error')
            raise CommandCanceled()

        if account is None:
            accounts = settings.get_accounts()
            if not accounts:
                ui.notify('no accounts set.', priority='error')
                raise self.ApplyError
            account = accounts[0]

        return account

    def _set_envelope(self):
        if self.envelope is None:
            if self.rest:
                if self.rest.startswith('mailto'):
                    self.envelope = mailto_to_envelope(self.rest)
                else:
                    self.envelope = Envelope()
                    self.envelope.add('To', self.rest)
            else:
                self.envelope = Envelope()

    def _set_gpg_sign(self, ui):
        account = self.envelope.account
        if account.sign_by_default:
            if account.gpg_key:
                self.envelope.sign = account.sign_by_default
                self.envelope.sign_key = account.gpg_key
            else:
                msg = 'Cannot find gpg key for account {}'
                msg = msg.format(account.address)
                logging.warning(msg)
                ui.notify(msg, priority='error')

    async def _set_to(self, ui):
        account = self.envelope.account
        if 'To' not in self.envelope.headers:
            allbooks = not settings.get('complete_matching_abook_only')
            logging.debug(allbooks)
            abooks = settings.get_addressbooks(order=[account],
                                               append_remaining=allbooks)
            logging.debug(abooks)
            completer = ContactsCompleter(abooks)
            to = await ui.prompt('To', completer=completer,
                                 history=ui.recipienthistory)
            if to is None:
                raise CommandCanceled()

            to = to.strip(' \t\n,')
            ui.recipienthistory.append(to)
            self.envelope.add('To', to)

    async def _set_gpg_encrypt(self, ui):
        account = self.envelope.account
        if self.encrypt or account.encrypt_by_default == u"all":
            logging.debug("Trying to encrypt message because encrypt=%s and "
                          "encrypt_by_default=%s", self.encrypt,
                          account.encrypt_by_default)
            await update_keys(ui, self.envelope, block_error=self.encrypt)
        elif account.encrypt_by_default == u"trusted":
            logging.debug("Trying to encrypt message because "
                          "account.encrypt_by_default=%s",
                          account.encrypt_by_default)
            await update_keys(ui, self.envelope, block_error=self.encrypt,
                              signed_only=True)
        else:
            logging.debug("No encryption by default, encrypt_by_default=%s",
                          account.encrypt_by_default)

    def _set_base_attributes(self):
        # set forced headers
        for key, value in self.headers.items():
            self.envelope.add(key, value)

        # set forced headers for separate parameters
        if self.sender:
            self.envelope.add('From', self.sender)
        if self.subject:
            self.envelope.add('Subject', self.subject)
        if self.to:
            self.envelope.add('To', ','.join(self.to))
        if self.cc:
            self.envelope.add('Cc', ','.join(self.cc))
        if self.bcc:
            self.envelope.add('Bcc', ','.join(self.bcc))
        if self.tags:
            self.envelope.tags = [t for t in self.tags.split(',') if t]

    async def _set_subject(self, ui):
        if settings.get('ask_subject') and \
                'Subject' not in self.envelope.headers:
            subject = await ui.prompt('Subject')
            logging.debug('SUBJECT: "%s"', subject)
            if subject is None:
                raise CommandCanceled()

            self.envelope.add('Subject', subject)

    async def _set_compose_tags(self, ui):
        if settings.get('compose_ask_tags'):
            comp = TagsCompleter(ui.dbman)
            tags = ','.join(self.tags) if self.tags else ''
            tagsstring = await ui.prompt('Tags', text=tags, completer=comp)
            tags = [t for t in tagsstring.split(',') if t]
            if tags is None:
                raise CommandCanceled()

            self.envelope.tags = tags

    def _set_attachments(self):
        if self.attach:
            for gpath in self.attach:
                for a in glob.glob(gpath):
                    self.envelope.attach(a)
                    logging.debug('attaching: %s', a)

    async def __apply(self, ui):
        self._set_envelope()
        if self.template is not None:
            self._get_template(ui)
        # Set headers and tags
        self._set_base_attributes()
        # set account and missing From header
        await self._get_sender_details(ui)

        # add signature
        await self._set_signature(ui)
        # Figure out whether we should GPG sign messages by default
        # and look up key if so
        self._set_gpg_sign(ui)
        # get missing To header
        await self._set_to(ui)
        # Set subject
        await self._set_subject(ui)
        # Add additional tags
        await self._set_compose_tags(ui)
        # Set attachments
        self._set_attachments()
        # set encryption if needed
        await self._set_gpg_encrypt(ui)

        cmd = commands.envelope.EditCommand(envelope=self.envelope,
                                            spawn=self.force_spawn,
                                            refocus=False)
        await ui.apply_command(cmd)



@registerCommand(
    MODE, 'move', help='move focus in current buffer',
    arguments=[
        (['movement'],
         {'nargs': argparse.REMAINDER,
          'help': 'up, down, [half]page up, [half]page down, first, last'})])
class MoveCommand(Command):

    """move in widget"""
    def __init__(self, movement=None, **kwargs):
        if movement is None:
            self.movement = ''
        else:
            self.movement = ' '.join(movement)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.movement in ['up', 'down', 'page up', 'page down']:
            ui.mainloop.process_input([self.movement])
        elif self.movement in ['halfpage down', 'halfpage up']:
            ui.mainloop.process_input(
                ui.mainloop.screen_size[1] // 2 * [self.movement.split()[-1]])
        elif self.movement == 'first':
            if hasattr(ui.current_buffer, "focus_first"):
                ui.current_buffer.focus_first()
                ui.update()
        elif self.movement == 'last':
            if hasattr(ui.current_buffer, "focus_last"):
                ui.current_buffer.focus_last()
                ui.update()
        else:
            ui.notify('unknown movement: ' + self.movement,
                      priority='error')


@registerCommand(MODE, 'reload', help='reload all configuration files')
class ReloadCommand(Command):

    """Reload configuration."""

    def apply(self, ui):
        try:
            settings.reload()
        except ConfigError as e:
            ui.notify('Error when reloading config files:\n {}'.format(e),
                      priority='error')


@registerCommand(
    MODE, 'savequery',
    arguments=[
        (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                          'default': 'True',
                          'help': 'postpone a writeout to the index'}),
        (['alias'], {'help': 'alias to use for query string'}),
        (['query'], {'help': 'query string to store',
                     'nargs': '+'})
    ],
    help='store query string as a "named query" in the database')
class SaveQueryCommand(Command):

    """save alias for query string"""
    repeatable = False

    def __init__(self, alias, query=None, flush=True, **kwargs):
        """
        :param alias: name to use for query string
        :type alias: str
        :param query: query string to save
        :type query: str or None
        :param flush: immediately write out to the index
        :type flush: bool
        """
        self.alias = alias
        if query is None:
            self.query = ''
        else:
            self.query = ' '.join(query)
        self.flush = flush
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        msg = 'saved alias "%s" for query string "%s"' % (self.alias,
                                                          self.query)

        try:
            ui.dbman.save_named_query(self.alias, self.query)
            logging.debug(msg)
            ui.notify(msg)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        if self.flush:
            ui.apply_command(commands.globals.FlushCommand())


@registerCommand(
    MODE, 'removequery',
    arguments=[
        (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                          'default': 'True',
                          'help': 'postpone a writeout to the index'}),
        (['alias'], {'help': 'alias to remove'}),
    ],
    help='removes a "named query" from the database')
class RemoveQueryCommand(Command):

    """remove named query string for given alias"""
    repeatable = False

    def __init__(self, alias, flush=True, **kwargs):
        """
        :param alias: name to use for query string
        :type alias: str
        :param flush: immediately write out to the index
        :type flush: bool
        """
        self.alias = alias
        self.flush = flush
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        msg = 'removed alias "%s"' % (self.alias)

        try:
            ui.dbman.remove_named_query(self.alias)
            logging.debug(msg)
            ui.notify(msg)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        if self.flush:
            ui.apply_command(commands.globals.FlushCommand())
