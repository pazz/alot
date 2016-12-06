# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import re
import code
from twisted.internet import threads
import subprocess
import email
import urwid
from twisted.internet.defer import inlineCallbacks
import logging
import argparse
import glob
from StringIO import StringIO

from alot.commands import Command, registerCommand
from alot.completion import CommandLineCompleter
from alot.commands import CommandCanceled
from alot.commands.utils import get_keys
from alot import buffers
from alot.widgets.utils import DialogBox
from alot import helper
from alot.db.errors import DatabaseLockedError
from alot.completion import ContactsCompleter
from alot.completion import AccountCompleter
from alot.completion import TagsCompleter
from alot.db.envelope import Envelope
from alot import commands
from alot.settings import settings
from alot.helper import split_commandstring
from alot.helper import mailto_to_envelope
from alot.utils.booleanaction import BooleanAction

MODE = 'global'


@registerCommand(MODE, 'exit')
class ExitCommand(Command):

    """shut down cleanly"""
    @inlineCallbacks
    def apply(self, ui):
        if settings.get('bug_on_exit'):
            msg = 'really quit?'
            if (yield ui.choice(msg, select='yes', cancel='no',
                                msg_position='left')) == 'no':
                return

        for b in ui.buffers:
            b.cleanup()
        ui.apply_command(FlushCommand(callback=ui.exit))

        if ui.db_was_locked:
            msg = 'Database locked. Exit without saving?'
            if (yield ui.choice(msg, select='yes', cancel='no',
                                msg_position='left')) == 'no':
                return
            ui.exit()


@registerCommand(MODE, 'search', usage='search query', arguments=[
    (['--sort'], {'help': 'sort order', 'choices': [
                  'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['query'], {'nargs': argparse.REMAINDER, 'help': 'search string'})])
class SearchCommand(Command):

    """open a new search buffer"""
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

    @inlineCallbacks
    def apply(self, ui):
        logging.info('open command shell')
        mode = ui.mode or 'global'
        cmpl = CommandLineCompleter(ui.dbman, mode, ui.current_buffer)
        cmdline = yield ui.prompt('',
                                  text=self.startwith,
                                  completer=cmpl,
                                  history=ui.commandprompthistory,
                                  )
        logging.debug('CMDLINE: %s' % cmdline)

        # interpret and apply commandline
        if cmdline:
            # save into prompt history
            ui.commandprompthistory.append(cmdline)
            ui.apply_commandline(cmdline)
        else:
            raise CommandCanceled()


@registerCommand(MODE, 'refresh')
class RefreshCommand(Command):

    """refresh the current buffer"""
    repeatable = True

    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


@registerCommand(MODE, 'shellescape', arguments=[
    (['--spawn'], {'action': BooleanAction, 'default': None,
                   'help': 'run in terminal window'}),
    (['--thread'], {'action': BooleanAction, 'default': None,
                    'help': 'run in separate thread'}),
    (['--refocus'], {'action': BooleanAction, 'help': 'refocus current buffer \
                     after command has finished'}),
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
        if isinstance(cmd, unicode):
            # convert cmdstring to list: in case shell==True,
            # Popen passes only the first item in the list to $SHELL
            cmd = [cmd] if shell else split_commandstring(cmd)

        # determine complete command list to pass
        touchhook = settings.get_hook('touch_external_cmdlist')
        # filter cmd, shell and thread through hook if defined
        if touchhook is not None:
            logging.debug('calling hook: touch_external_cmdlist')
            res = touchhook(cmd, shell=shell, spawn=spawn, thread=thread)
            logging.debug('got: %s' % res)
            cmd, shell, self.in_thread = res
        # otherwise if spawn requested and X11 is running
        elif spawn:
            if 'DISPLAY' in os.environ:
                term_cmd = settings.get('terminal_cmd', '')
                logging.info('spawn in terminal: %s' % term_cmd)
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

    def apply(self, ui):
        logging.debug('cmdlist: %s' % self.cmdlist)
        callerbuffer = ui.current_buffer

        # set standard input for subcommand
        stdin = None
        if self.stdin is not None:
            # wrap strings in StrinIO so that they behaves like a file
            if isinstance(self.stdin, unicode):
                stdin = StringIO(self.stdin)
            else:
                stdin = self.stdin

        def afterwards(data):
            if data == 'success':
                if callable(self.on_success):
                    self.on_success()
            else:
                ui.notify(data, priority='error')
            if self.refocus and callerbuffer in ui.buffers:
                logging.info('refocussing')
                ui.buffer_focus(callerbuffer)

        logging.info('calling external command: %s' % self.cmdlist)

        def thread_code(*args):
            try:
                if stdin is None:
                    proc = subprocess.Popen(self.cmdlist, shell=self.shell,
                                            stderr=subprocess.PIPE)
                    ret = proc.wait()
                    err = proc.stderr.read()
                else:
                    proc = subprocess.Popen(self.cmdlist, shell=self.shell,
                                            stdin=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
                    out, err = proc.communicate(stdin.read())
                    ret = proc.wait()
                if ret == 0:
                    return 'success'
                else:
                    return err.strip()
            except OSError as e:
                return str(e)

        if self.in_thread:
            d = threads.deferToThread(thread_code)
            d.addCallback(afterwards)
        else:
            ui.mainloop.screen.stop()
            ret = thread_code()
            ui.mainloop.screen.start()

            # make sure urwid renders its canvas at the correct size
            ui.mainloop.screen_size = None
            ui.mainloop.draw_screen()

            afterwards(ret)


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
        logging.debug('using editor_cmd: %s' % editor_cmdstring)

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

    def apply(self, ui):
        if self.cmdlist is None:
            ui.notify('no editor set', priority='error')
        else:
            return ExternalCommand.apply(self, ui)


@registerCommand(MODE, 'pyshell')
class PythonShellCommand(Command):

    """open an interactive python shell for introspection"""
    repeatable = True

    def apply(self, ui):
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()


@registerCommand(MODE, 'repeat')
class RepeatCommand(Command):

    """Repeats the command executed last time"""
    def __init__(self, **kwargs):
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if ui.last_commandline is not None:
            ui.apply_commandline(ui.last_commandline)
        else:
            ui.notify('no last command')


@registerCommand(MODE, 'call', arguments=[
    (['command'], {'help': 'python command string to call'})])
class CallCommand(Command):

    """ Executes python code """
    repeatable = True

    def __init__(self, command, **kwargs):
        """
        :param command: python command string to call
        :type command: str
        """
        Command.__init__(self, **kwargs)
        self.command = command

    def apply(self, ui):
        try:
            hooks = settings.hooks
            if hooks:
                env = {'ui': ui, 'settings': settings}
                for k, v in env.items():
                    if k not in hooks.__dict__:
                        hooks.__dict__[k] = v

            exec(self.command)
        except Exception as e:
            logging.exception(e)
            msg = 'an error occurred during execution of "%s":\n%s'
            ui.notify(msg % (self.command, e), priority='error')


@registerCommand(MODE, 'bclose', arguments=[
    (['--redraw'], {'action': BooleanAction, 'help': 'redraw current buffer \
                     after command has finished'}),
    (['--force'], {'action': 'store_true',
                   'help': 'never ask for confirmation'})])
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

    @inlineCallbacks
    def apply(self, ui):
        if self.buffer is None:
            self.buffer = ui.current_buffer

        if (isinstance(self.buffer, buffers.EnvelopeBuffer) and
                not self.buffer.envelope.sent_time):
            if (not self.force and (yield ui.choice('close without sending?',
                                                    select='yes', cancel='no',
                                                    msg_position='left')) ==
                    'no'):
                raise CommandCanceled()

        if len(ui.buffers) == 1:
            if settings.get('quit_on_last_bclose'):
                logging.info('closing the last buffer, exiting')
                ui.apply_command(ExitCommand())
            else:
                logging.info('not closing last remaining buffer as '
                             'global.quit_on_last_bclose is set to False')
        else:
            ui.buffer_close(self.buffer, self.redraw)


@registerCommand(MODE, 'bprevious', forced={'offset': -1},
                 help='focus previous buffer')
@registerCommand(MODE, 'bnext', forced={'offset': +1},
                 help='focus next buffer')
@registerCommand(MODE, 'buffer', arguments=[
    (['index'], {'type': int, 'help': 'buffer index to focus'}), ],
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
    def __init__(self, filtfun=None, **kwargs):
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
    def __init__(self, filtfun=None, tags=None, **kwargs):
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
                def f(*args):
                    self.apply(ui)
                ui.mainloop.set_alarm_in(timeout, f)
                if not ui.db_was_locked:
                    if not self.silent:
                        ui.notify(
                            'index locked, will try again in %d secs' % timeout)
                    ui.db_was_locked = True
            ui.update()
            return


# TODO: choices
@registerCommand(MODE, 'help', arguments=[
    (['commandname'], {'help': 'command or \'bindings\''})])
class HelpCommand(Command):

    """
    display help for a command. Use \'bindings\' to
    display all keybings interpreted in current mode.'
    """
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
            maxkeylength = len(max((modemaps).keys() + globalmaps.keys(),
                                   key=len))
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
            logging.debug('HELP %s' % self.commandname)
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
    (['--subject'], {'nargs': '?', 'help': 'subject line'}),
    (['--to'], {'nargs': '+', 'help': 'recipients'}),
    (['--cc'], {'nargs': '+', 'help': 'copy to'}),
    (['--bcc'], {'nargs': '+', 'help': 'blind copy to'}),
    (['--attach'], {'nargs': '+', 'help': 'attach files'}),
    (['--omit_signature'], {'action': 'store_true',
                            'help': 'do not add signature'}),
    (['--spawn'], {'action': BooleanAction, 'default': None,
                   'help': 'spawn editor in new terminal'}),
    (['rest'], {'nargs': '*'}),
])
class ComposeCommand(Command):

    """compose a new email"""
    def __init__(self, envelope=None, headers={}, template=None,
                 sender=u'', subject=u'', to=[], cc=[], bcc=[], attach=None,
                 omit_signature=False, spawn=None, rest=[],
                 encrypt=False, **kwargs):
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
        self.headers = headers
        self.sender = sender
        self.subject = subject
        self.to = to
        self.cc = cc
        self.bcc = bcc
        self.attach = attach
        self.omit_signature = omit_signature
        self.force_spawn = spawn
        self.rest = ' '.join(rest)
        self.encrypt = encrypt

    @inlineCallbacks
    def apply(self, ui):
        if self.envelope is None:
            if self.rest:
                if self.rest.startswith('mailto'):
                    self.envelope = mailto_to_envelope(self.rest)
                else:
                    self.envelope = Envelope()
                    self.envelope.add('To', self.rest)
            else:
                self.envelope = Envelope()
        if self.template is not None:
            # get location of tempsdir, containing msg templates
            tempdir = settings.get('template_dir')
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
            except Exception as e:
                ui.notify(str(e), priority='error')
                return

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

        # get missing From header
        if 'From' not in self.envelope.headers:
            accounts = settings.get_accounts()
            if len(accounts) == 1:
                a = accounts[0]
                fromstring = "%s <%s>" % (a.realname, a.address)
                self.envelope.add('From', fromstring)
            else:
                cmpl = AccountCompleter()
                fromaddress = yield ui.prompt('From', completer=cmpl,
                                              tab=1)
                if fromaddress is None:
                    raise CommandCanceled()

                self.envelope.add('From', fromaddress)

        # find out the right account
        sender = self.envelope.get('From')
        name, addr = email.Utils.parseaddr(sender)
        account = settings.get_account_by_address(addr)
        if account is None:
            accounts = settings.get_accounts()
            if not accounts:
                ui.notify('no accounts set.', priority='error')
                return
            account = accounts[0]

        # add signature
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
                    sigcontent = open(sig).read()
                    enc = helper.guess_encoding(sigcontent)
                    mimetype = helper.guess_mimetype(sigcontent)
                    if mimetype.startswith('text'):
                        sigcontent = helper.string_decode(sigcontent, enc)
                        self.envelope.body += '\n' + sigcontent
            else:
                ui.notify('could not locate signature: %s' % sig,
                          priority='error')
                if (yield ui.choice('send without signature?', 'yes',
                                    'no')) == 'no':
                    return

        # Figure out whether we should GPG sign messages by default
        # and look up key if so
        self.envelope.sign = account.sign_by_default
        self.envelope.sign_key = account.gpg_key

        # get missing To header
        if 'To' not in self.envelope.headers:
            allbooks = not settings.get('complete_matching_abook_only')
            logging.debug(allbooks)
            abooks = settings.get_addressbooks(order=[account],
                                               append_remaining=allbooks)
            logging.debug(abooks)
            completer = ContactsCompleter(abooks)
            to = yield ui.prompt('To',
                                 completer=completer)
            if to is None:
                raise CommandCanceled()

            self.envelope.add('To', to.strip(' \t\n,'))

        if settings.get('ask_subject') and \
                'Subject' not in self.envelope.headers:
            subject = yield ui.prompt('Subject')
            logging.debug('SUBJECT: "%s"' % subject)
            if subject is None:
                raise CommandCanceled()

            self.envelope.add('Subject', subject)

        if settings.get('compose_ask_tags'):
            comp = TagsCompleter(ui.dbman)
            tagsstring = yield ui.prompt('Tags', completer=comp)
            tags = filter(lambda x: x, tagsstring.split(','))
            if tags is None:
                raise CommandCanceled()

            self.envelope.tags = tags

        if self.attach:
            for gpath in self.attach:
                for a in glob.glob(gpath):
                    self.envelope.attach(a)
                    logging.debug('attaching: ' + a)

        # set encryption if needed
        if self.encrypt or account.encrypt_by_default == u"all":
            logging.debug("Trying to encrypt message because encrypt={} and "
                          "encrypt_by_default={}".format(
                              self.encrypt, account.encrypt_by_default))
            yield self._set_encrypt(ui, self.envelope)
        elif account.encrypt_by_default == u"trusted":
            logging.debug("Trying to encrypt message because "
                          "account.encrypt_by_default={}".format(
                              account.encrypt_by_default))
            yield self._set_encrypt(ui, self.envelope, trusted_only=True)
        else:
            logging.debug(
                    "No encryption by default, encrypt_by_default={}".format(
                        account.encrypt_by_default))

        cmd = commands.envelope.EditCommand(envelope=self.envelope,
                                            spawn=self.force_spawn,
                                            refocus=False)
        ui.apply_command(cmd)

    @inlineCallbacks
    def _set_encrypt(self, ui, envelope, trusted_only=False):
        """Find and set the encryption keys in an envolope.

        :param ui: the main user interface object
        :type ui: alot.ui.UI
        :param envolope: the envolope buffer object
        :type envolope: alot.buffers.EnvelopeBuffer
        :param trusted_only: only add keys to the list of encryption
            keys whose uid is signed (trusted to belong to the key)
        :type trusted_only: bool

        """
        encrypt_keys = []
        for recipient in envelope.headers['To'][0].split(','):
            recipient = recipient.strip()
            if not recipient:
                continue
            match = re.search("<(.*@.*)>", recipient)
            if match:
                recipient = match.group(1)
            encrypt_keys.append(recipient)

        logging.debug("encryption keys: " + str(encrypt_keys))
        keys = yield get_keys(ui, encrypt_keys, block_error=self.encrypt,
                              signed_only=trusted_only)
        if keys:
            envelope.encrypt_keys.update(keys)
            envelope.encrypt = True
        else:
            envelope.encrypt = False


@registerCommand(MODE, 'move', help='move focus in current buffer',
                 arguments=[(['movement'], {
                             'nargs': argparse.REMAINDER,
                             'help': 'up, down, [half]page up, '
                                     '[half]page down, first'})])
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
                ui.mainloop.screen_size[1] / 2 * [self.movement.split()[-1]])
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
